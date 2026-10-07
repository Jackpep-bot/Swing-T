"""Market breadth: one row per session aggregated across the panel's symbols (the participation dial).

``market_breadth(panel)`` turns the long feature panel into a per-session breadth vector. Every value on
session ``T`` is computed from the rows dated ``T`` only (and, through the per-symbol features, from each
symbol's own earlier bars), so truncating the panel at ``T`` never changes a row at or before ``T``.
Rationale, thresholds and sources: ``docs/methods/06-breadth-regime-filters.md`` (sections C and D) and
``docs/methods.md`` section 2a.

Columns (index ``session``: naive New York midnight ``Timestamp`` per session, ascending)::

    pct_above_50   0-100: share of symbols whose close is above their sma_50 (symbols with a warm sma_50 only;
                   NaN when none is warm). Keller's fast participation line (doc 06, C)
    pct_above_200  0-100: same with sma_200 (Hill's 60 / 40 hysteresis line, doc 06, C)
    up4_count      Stockbee 4% up: close / prev_close >= 1.04 and volume > prev volume and volume >= 100,000
                   (identical to ``features.patterns.burst_4pct``; doc 06, D)
    down4_count    the mirror: close / prev_close <= 0.96 with the same volume conditions (doc 06, D)
    ratio_10d      Stockbee 10-day ratio: 10-session sum of up4_count / 10-session sum of down4_count. The
                   denominator is floored at 1 (a window with no 4% decliners is not infinite); NaN until 10
                   sessions exist and when the window holds no 4% move at all (a quiet tape is not bearish)
    new_highs      symbols whose high equals or exceeds their 52-week high (``high >= high_52w``; 252 bars)
    new_lows       symbols whose low equals or undercuts their 52-week low (``low <= low_52w``)
    n_symbols      symbols with a finite close on the session (the breadth population)

The population is whatever the panel holds: build it from the point-in-time universe (delisted names included,
doc 06 pitfall 4) and pass ``exclude=("SPY",)`` to keep the index ETF out of a stock breadth reading.

Stored volume is split-adjusted and rewritten by every later split, so a fixed share floor would select names by
their future corporate actions. Pass the store's ``splits`` table (symbol, ex_date, ratio = split_to /
split_from) and the 100,000-share floor is applied to as-traded volume (adjusted volume x the product of the
ratios of the symbol's splits with ex_date after the bar, as ``data.universe.as_traded``); the
``volume > prev volume`` test stays on adjusted volume, which is consistent across a split.
Pure pandas, deterministic, no network.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd
import structlog

from ._common import (
    CLOSE,
    HIGH,
    LOW,
    NY_TZ,
    SYMBOL_COL,
    TS_COL,
    VOLUME,
    per_symbol,
    require_columns,
    session_key,
    shift_per_symbol,
    symbol_codes,
)
from .cross_section import WINDOW_52W, rolling_max, rolling_min
from .indicators import sma
from .patterns import BURST_CLOSE_RATIO, BURST_MIN_VOLUME

log = structlog.get_logger(__name__)

#: Fast and slow participation lines: % of stocks above the 50- / 200-day SMA (doc 06, section C).
FAST_MA_WINDOW = 50
SLOW_MA_WINDOW = 200
#: Stockbee 4% up / down day: 100*(C-C1)/C1 >= 4 (up) or <= -4 (down), V >= 100k and V > V1
#: (doc 06, section D).
UP4_CLOSE_RATIO = BURST_CLOSE_RATIO  # 1.04
DOWN4_CLOSE_RATIO = 0.96
FOUR_PCT_MIN_VOLUME = BURST_MIN_VOLUME  # 100,000 shares (TC2000 `V >= 1000` in hundreds)
#: Stockbee 10-day ratio window: sum of 4%-up counts over 10 sessions / sum of 4%-down counts
#: (doc 06, section D).
RATIO_WINDOW = 10
#: Floor for the ratio's denominator so a window without any 4% decliner gives a finite (large) reading.
RATIO_MIN_DENOMINATOR = 1.0
PCT_SCALE = 100.0
SESSION_INDEX = "session"

BREADTH_COLUMNS: tuple[str, ...] = (
    "pct_above_50",
    "pct_above_200",
    "up4_count",
    "down4_count",
    "ratio_10d",
    "new_highs",
    "new_lows",
    "n_symbols",
)
_COUNT_COLUMNS: tuple[str, ...] = ("up4_count", "down4_count", "new_highs", "new_lows", "n_symbols")
_SESSION = "_session"


def empty_breadth() -> pd.DataFrame:
    """A zero-row breadth frame with the contract columns and dtypes."""
    idx = pd.DatetimeIndex([], name=SESSION_INDEX)
    out = pd.DataFrame({c: pd.Series(dtype="float64") for c in BREADTH_COLUMNS}, index=idx)
    return out.astype({c: "int64" for c in _COUNT_COLUMNS})


def ratio_10d(up_count: pd.Series, down_count: pd.Series, window: int = RATIO_WINDOW) -> pd.Series:
    """Stockbee ratio: ``rolling(window) sum(up) / max(rolling sum(down), 1)``; NaN before ``window`` sessions
    and where the window holds no 4% move in either direction.
    """
    up = up_count.astype("float64").rolling(window, min_periods=window).sum()
    down = down_count.astype("float64").rolling(window, min_periods=window).sum()
    ratio = up / down.clip(lower=RATIO_MIN_DENOMINATOR)
    return ratio.where((up + down) > 0)


def split_factor_per_row(df: pd.DataFrame, splits: pd.DataFrame | None) -> pd.Series:
    """Per row: product of the symbol's split ratios with ex_date AFTER the bar's session (1.0 without splits);
    as-traded volume = adjusted volume / factor (``data.universe.as_traded``)."""
    ones = pd.Series(1.0, index=df.index)
    if splits is None or len(splits) == 0 or df.empty or not {"symbol", "ex_date", "ratio"} <= set(splits.columns):
        return ones
    sp = pd.DataFrame({
        "_sym": splits["symbol"].astype(str).str.upper(),
        "_ex": pd.to_datetime(splits["ex_date"]).dt.normalize(),
        "_ratio": pd.to_numeric(splits["ratio"], errors="coerce"),
    })
    sp = sp.loc[(sp["_ratio"] > 0) & sp["_sym"].isin(set(df[SYMBOL_COL].astype(str).str.upper()))]
    if sp.empty:
        return ones
    if getattr(sp["_ex"].dt, "tz", None) is not None:
        sp["_ex"] = sp["_ex"].dt.tz_localize(None)
    sp["_ex"] = sp["_ex"].astype("datetime64[ns]")  # merge_asof needs one datetime unit on both sides
    sp = sp.groupby(["_sym", "_ex"], as_index=False)["_ratio"].prod()
    sp = sp.sort_values(["_sym", "_ex"], ascending=[True, False], kind="mergesort")
    sp["_factor"] = sp.groupby("_sym", sort=False)["_ratio"].cumprod()  # product over this and every later split
    rows = pd.DataFrame({"_sym": df[SYMBOL_COL].astype(str).str.upper(),
                         "_day": session_key(df[TS_COL]).astype("datetime64[ns]"),
                         "_pos": np.arange(len(df))}).sort_values("_day", kind="mergesort")
    merged = pd.merge_asof(rows, sp.sort_values("_ex", kind="mergesort")[["_sym", "_ex", "_factor"]],
                           left_on="_day", right_on="_ex", by="_sym", direction="forward",
                           allow_exact_matches=False)  # first split strictly after the bar
    factor = np.ones(len(df))
    factor[merged["_pos"].to_numpy()] = merged["_factor"].fillna(1.0).to_numpy(dtype="float64")
    return pd.Series(factor, index=df.index)


def _per_row_flags(df: pd.DataFrame, splits: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per-row 0/1 (or NaN) flags that the session aggregation averages or sums."""
    key = symbol_codes(df)
    close = df[CLOSE].astype("float64")
    high = df[HIGH].astype("float64")
    low = df[LOW].astype("float64")
    volume = df[VOLUME].astype("float64")
    traded_volume = volume / split_factor_per_row(df, splits)

    def ma(window: int) -> pd.Series:
        col = f"sma_{window}"
        return df[col].astype("float64") if col in df.columns else per_symbol(close, key, sma, window)

    sma_fast, sma_slow = ma(FAST_MA_WINDOW), ma(SLOW_MA_WINDOW)
    prev_close = (
        df["prev_close"].astype("float64") if "prev_close" in df.columns else shift_per_symbol(close, key, 1)
    )
    prev_volume = shift_per_symbol(volume, key, 1)
    high_52w = (
        df["high_52w"].astype("float64")
        if "high_52w" in df.columns
        else per_symbol(high, key, rolling_max, WINDOW_52W)
    )
    low_52w = (
        df["low_52w"].astype("float64")
        if "low_52w" in df.columns
        else per_symbol(low, key, rolling_min, WINDOW_52W)
    )

    has_close = close.notna()
    above_fast = (close > sma_fast).astype("float64").where(has_close & sma_fast.notna())
    above_slow = (close > sma_slow).astype("float64").where(has_close & sma_slow.notna())
    change = close / prev_close
    vol_ok = (volume > prev_volume) & (traded_volume >= FOUR_PCT_MIN_VOLUME)
    up4 = (change >= UP4_CLOSE_RATIO) & vol_ok
    down4 = (change <= DOWN4_CLOSE_RATIO) & vol_ok
    new_high = high_52w.notna() & (high >= high_52w)
    new_low = low_52w.notna() & (low <= low_52w)
    return pd.DataFrame(
        {
            _SESSION: session_key(df[TS_COL]),
            "pct_above_50": above_fast * PCT_SCALE,
            "pct_above_200": above_slow * PCT_SCALE,
            "up4_count": up4.astype("int64"),
            "down4_count": down4.astype("int64"),
            "new_highs": new_high.astype("int64"),
            "new_lows": new_low.astype("int64"),
            "n_symbols": has_close.astype("int64"),
        },
        index=df.index,
    )


def market_breadth(
    panel: pd.DataFrame, *, exclude: Iterable[str] = (), splits: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Per-session breadth vector from the long feature panel (see the module docstring for every column).

    Reads ``sma_50``, ``sma_200``, ``prev_close``, ``high_52w`` and ``low_52w`` from the panel when present
    and computes them per symbol from the bars otherwise, so a bare bars frame also works. ``exclude`` drops
    symbols (e.g. the SPY market proxy) from the population. ``splits`` (the store's splits table) puts the
    4% days' share floor on as-traded volume. One row per symbol and session is kept (the last).
    """
    require_columns(panel, (SYMBOL_COL, TS_COL, HIGH, LOW, CLOSE, VOLUME), "market_breadth")
    drop = set(exclude)
    df = panel.loc[~panel[SYMBOL_COL].isin(drop)] if drop else panel
    if df.empty:
        return empty_breadth()
    df = df.sort_values([SYMBOL_COL, TS_COL], kind="mergesort").reset_index(drop=True)
    dup = pd.MultiIndex.from_arrays([df[SYMBOL_COL], session_key(df[TS_COL])]).duplicated(keep="last")
    if dup.any():
        log.warning("features.breadth_duplicate_rows_dropped", rows=int(dup.sum()))
        df = df.loc[~dup].reset_index(drop=True)
    flags = _per_row_flags(df, splits)
    grouped = flags.groupby(_SESSION, sort=True)
    out = grouped[["pct_above_50", "pct_above_200"]].mean()
    counts = grouped[list(_COUNT_COLUMNS)].sum().astype("int64")
    out = out.join(counts)
    out["ratio_10d"] = ratio_10d(out["up4_count"], out["down4_count"])
    out.index = pd.DatetimeIndex(out.index, name=SESSION_INDEX)
    out = out[list(BREADTH_COLUMNS)]
    log.debug(
        "features.breadth_built",
        sessions=len(out),
        symbols=int(df[SYMBOL_COL].nunique()),
        excluded=sorted(drop),
    )
    return out


def breadth_as_of(breadth: pd.DataFrame | None, as_of: object) -> pd.Series | None:
    """The breadth row of the last session on or before ``as_of`` (a date / datetime / Timestamp), else None.

    Accepts an index of naive or tz-aware timestamps or ``datetime.date`` objects.
    """
    if breadth is None or len(breadth) == 0:
        return None
    idx = pd.to_datetime(pd.Index(breadth.index))
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert(NY_TZ).tz_localize(None)
    idx = idx.normalize()
    cutoff = pd.Timestamp(as_of)  # type: ignore[arg-type]
    if cutoff.tzinfo is not None:
        cutoff = cutoff.tz_convert(NY_TZ).tz_localize(None)
    mask = np.asarray(idx <= cutoff.normalize())
    if not mask.any():
        return None
    pos = int(np.flatnonzero(mask)[np.argmax(idx[mask].to_numpy())])
    row = breadth.iloc[pos].copy()
    row.name = idx[pos]
    return row


__all__ = [
    "BREADTH_COLUMNS",
    "RATIO_WINDOW",
    "breadth_as_of",
    "empty_breadth",
    "market_breadth",
    "ratio_10d",
    "split_factor_per_row",
]
