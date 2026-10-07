"""Extra causal features for the method-driven strategies (docs/methods.md section 7a item 3 and section 7b).

Columns produced by :func:`add_patterns2` (per symbol unless noted, point-in-time, NaN while warming up)::

    ema_20              20-bar EMA of close (Holy Grail's 20 EMA; methods.md 6.1, 7b #1)
    adx_14              Wilder ADX(14); plus_di_14 / minus_di_14 its directional indicators (methods.md 7a #3)
    adr_pct_20          mean(high / low over 20 bars) - 1, Kullamagi's ADR% as a fraction (methods.md 2b, doc 05)
    atr_40              Wilder ATR(40) (Morales/Kacher buyable-gap-up benchmark; methods.md 6.13)
    avg_vol_50d_prev    mean volume of the 50 bars BEFORE this bar (methods.md 7a #3 `avg_vol_50d_prev`)
    vol_ratio_50d_prev  volume / avg_vol_50d_prev
    gap_atr40           (open - prev_close) / atr_40 of the prior bar (BGU gap size, doc 13)
    run_up_42           high / min(low over the last 42 bars) - 1: the move into this bar within ~2 months
                        (Qullamaggie "prior move", methods.md 2b / 7b #4)
    rs_63d_rank         cross-sectional percentile (0-1] of the 63-bar return among symbols with a bar on the
                        same session (methods.md 2b `rank_ret_63d`); depends only on same-session rows

Geometry detectors (:func:`flat_base`, :func:`cup_with_handle`, :func:`flag`, :func:`gap_consolidation`) work
on one symbol's numpy arrays and only look at indices ``<= end``; strategies call them with ``end`` = the bar
before the as-of bar, so they are causal by construction. :func:`as_of_view` slices a panel to the bars on or
before ``as_of`` and attaches these columns (computing them once per panel object when the panel lacks them).
"""

from __future__ import annotations

import weakref
from dataclasses import dataclass, field
from datetime import date
from typing import Any, NamedTuple

import numpy as np
import pandas as pd
import structlog

from ._common import (
    CLOSE,
    HIGH,
    LOW,
    OPEN,
    SYMBOL_COL,
    TS_COL,
    VOLUME,
    per_symbol,
    require_columns,
    session_key,
    shift_per_symbol,
    symbol_codes,
)
from .cross_section import pct_return, rolling_mean, rolling_min
from .indicators import ema, true_range, wilder_smooth

log = structlog.get_logger(__name__)

EMA_SHORT_SPAN = 20  # Holy Grail 20 EMA (methods.md 6.1; doc 01 "price retraces to touch the 20 EMA")
ADX_PERIOD = 14  # Raschke/Connors 14-period ADX (doc 01)
ADR_WINDOW = 20  # Kullamagi ADR% formula over 20 bars (doc 05 FAQ)
ATR_LONG_PERIOD = 40  # Morales/Kacher BGU gap >= 0.75 x ATR(40) (doc 13)
AVG_VOL_PRIOR_WINDOW = 50  # prior-bar 50-day average volume (methods.md 7a #3, doc 13 caveat)
RUN_UP_WINDOW = 42  # "prior move ... in <= 2 months" ~ 42 sessions (methods.md 2b, 7b #4)
RS_RETURN_WINDOW = 63  # 3-month return for the RS percentile (methods.md 2b `rank_ret_63d`)
DI_SCALE = 100.0

PATTERNS2_COLUMNS: tuple[str, ...] = (
    f"ema_{EMA_SHORT_SPAN}",
    f"adx_{ADX_PERIOD}",
    f"plus_di_{ADX_PERIOD}",
    f"minus_di_{ADX_PERIOD}",
    f"adr_pct_{ADR_WINDOW}",
    f"atr_{ATR_LONG_PERIOD}",
    f"avg_vol_{AVG_VOL_PRIOR_WINDOW}d_prev",
    f"vol_ratio_{AVG_VOL_PRIOR_WINDOW}d_prev",
    f"gap_atr{ATR_LONG_PERIOD}",
    f"run_up_{RUN_UP_WINDOW}",
    f"rs_{RS_RETURN_WINDOW}d_rank",
)
_INPUT_COLUMNS: tuple[str, ...] = (SYMBOL_COL, TS_COL, OPEN, HIGH, LOW, CLOSE, VOLUME)


# ----------------------------------------------------------------------------------------------- columns
def directional_movement(
    high: pd.Series, low: pd.Series, prev_high: pd.Series, prev_low: pd.Series
) -> tuple[pd.Series, pd.Series]:
    """Wilder +DM / -DM: ``up = high - prev_high``, ``down = prev_low - low``; +DM = up when up > down and up > 0
    (else 0), -DM mirrors it. NaN where the previous bar is missing (first bar of a symbol)."""
    up = high - prev_high
    down = prev_low - low
    plus = up.where((up > down) & (up > 0), 0.0).where(prev_high.notna())
    minus = down.where((down > up) & (down > 0), 0.0).where(prev_low.notna())
    return plus, minus


def _di(dm_smooth: pd.Series, atr_s: pd.Series) -> pd.Series:
    return (DI_SCALE * dm_smooth / atr_s).where(atr_s > 0)


def _dx(plus_di: pd.Series, minus_di: pd.Series) -> pd.Series:
    total = plus_di + minus_di
    return (DI_SCALE * (plus_di - minus_di).abs() / total).where(total > 0, 0.0).where(total.notna())


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = ADX_PERIOD) -> pd.DataFrame:
    """Single-symbol Wilder ADX: columns ``adx``, ``plus_di``, ``minus_di`` (same smoothing helper as ATR/RSI)."""
    plus_dm, minus_dm = directional_movement(high, low, high.shift(1), low.shift(1))
    prev_close = close.shift(1)
    tr = true_range(high, low, prev_close).where(prev_close.notna())
    atr_s = wilder_smooth(tr, period)
    pdi = _di(wilder_smooth(plus_dm, period), atr_s)
    mdi = _di(wilder_smooth(minus_dm, period), atr_s)
    return pd.DataFrame({"adx": wilder_smooth(_dx(pdi, mdi), period), "plus_di": pdi, "minus_di": mdi})


def adr_pct(high: pd.Series, low: pd.Series, window: int = ADR_WINDOW) -> pd.Series:
    """Kullamagi ADR% as a fraction: ``mean(high / low over window) - 1`` (doc 05 FAQ formula / 100)."""
    return rolling_mean((high / low).where(low > 0), window) - 1.0


def add_patterns2(df: pd.DataFrame, key: pd.Series | None = None) -> pd.DataFrame:
    """Return ``df`` with every column in :data:`PATTERNS2_COLUMNS` appended (needs only symbol, ts and OHLCV).

    ``df`` must be sorted by ``symbol, ts``. Every column uses the current and earlier bars of its own symbol,
    except ``rs_63d_rank``, which ranks the same session's 63-bar returns across symbols (no look-ahead).
    """
    require_columns(df, _INPUT_COLUMNS, "add_patterns2")
    key = symbol_codes(df) if key is None else key
    o, h, lo, c, v = df[OPEN], df[HIGH], df[LOW], df[CLOSE], df[VOLUME]
    prev_close = shift_per_symbol(c, key, 1)
    plus_dm, minus_dm = directional_movement(h, lo, shift_per_symbol(h, key, 1), shift_per_symbol(lo, key, 1))
    tr_dm = true_range(h, lo, prev_close).where(prev_close.notna())
    atr_dm = per_symbol(tr_dm, key, wilder_smooth, ADX_PERIOD)
    pdi = _di(per_symbol(plus_dm, key, wilder_smooth, ADX_PERIOD), atr_dm)
    mdi = _di(per_symbol(minus_dm, key, wilder_smooth, ADX_PERIOD), atr_dm)
    adx_s = per_symbol(_dx(pdi, mdi), key, wilder_smooth, ADX_PERIOD)
    atr_long = per_symbol(true_range(h, lo, prev_close), key, wilder_smooth, ATR_LONG_PERIOD)
    avg_prev = shift_per_symbol(per_symbol(v, key, rolling_mean, AVG_VOL_PRIOR_WINDOW), key, 1)
    prior_atr = shift_per_symbol(atr_long, key, 1)
    ret = per_symbol(c, key, pct_return, RS_RETURN_WINDOW)
    rank = ret.groupby(session_key(df[TS_COL]), sort=False).rank(pct=True)
    new = {
        f"ema_{EMA_SHORT_SPAN}": per_symbol(c, key, ema, EMA_SHORT_SPAN),
        f"adx_{ADX_PERIOD}": adx_s,
        f"plus_di_{ADX_PERIOD}": pdi,
        f"minus_di_{ADX_PERIOD}": mdi,
        f"adr_pct_{ADR_WINDOW}": per_symbol((h / lo).where(lo > 0), key, rolling_mean, ADR_WINDOW) - 1.0,
        f"atr_{ATR_LONG_PERIOD}": atr_long,
        f"avg_vol_{AVG_VOL_PRIOR_WINDOW}d_prev": avg_prev,
        f"vol_ratio_{AVG_VOL_PRIOR_WINDOW}d_prev": (v / avg_prev).where(avg_prev > 0),
        f"gap_atr{ATR_LONG_PERIOD}": ((o - prev_close) / prior_atr).where(prior_atr > 0),
        f"run_up_{RUN_UP_WINDOW}": (h / per_symbol(lo, key, rolling_min, RUN_UP_WINDOW)).where(lo > 0) - 1.0,
        f"rs_{RS_RETURN_WINDOW}d_rank": rank,
    }
    return df.assign(**new)


# ----------------------------------------------------------------------------------------------- cache
_CACHE: dict[str, Any] = {}


def _fingerprint(panel: pd.DataFrame) -> tuple[Any, ...]:
    close = panel[CLOSE].to_numpy(dtype=float, na_value=np.nan)
    vol = panel[VOLUME].to_numpy(dtype=float, na_value=np.nan)
    return (len(panel), float(np.nansum(close)), float(np.nansum(vol)), str(panel[TS_COL].iloc[-1]))


def patterns2_frame(panel: pd.DataFrame) -> pd.DataFrame:
    """The :data:`PATTERNS2_COLUMNS` of ``panel``, aligned to ``panel.index``.

    Taken from the panel when it already carries them (e.g. after ``add_patterns2`` in a backtest), otherwise
    computed on the whole panel once and cached for that panel object (several strategies scanning the same
    panel share one computation). Computing on rows after ``as_of`` is harmless: every column is causal.
    """
    cols = list(PATTERNS2_COLUMNS)
    if all(c in panel.columns for c in cols):
        return panel[cols]
    fp = _fingerprint(panel)
    hit = _CACHE.get("entry")
    if hit is not None and hit[0]() is panel and hit[1] == fp:
        return hit[2]
    require_columns(panel, _INPUT_COLUMNS, "patterns2_frame")
    order = panel.sort_values([SYMBOL_COL, TS_COL], kind="mergesort")
    work = order[list(_INPUT_COLUMNS)].reset_index(drop=True)
    out = add_patterns2(work)[cols]
    out.index = order.index
    out = out.reindex(panel.index)
    _CACHE["entry"] = (weakref.ref(panel), fp, out)
    log.debug("features.patterns2_computed", rows=len(panel))
    return out


# ----------------------------------------------------------------------------------------------- as-of view
def local_day(ts: pd.Series) -> pd.Series:
    """Calendar day of each bar in its own timezone as naive midnight Timestamps (same rule as strategies)."""
    s = pd.to_datetime(ts)
    if getattr(s.dt, "tz", None) is not None:
        s = s.dt.tz_localize(None)
    return s.dt.normalize()


@dataclass
class AsOfView:
    """Bars on or before ``as_of`` (sorted by symbol, ts, fresh RangeIndex) plus per-symbol positions.

    ``current`` holds the as-of row of every symbol that has a bar on the latest session (stale symbols are
    dropped, as in ``PanelStrategy.rows_as_of``). ``window(symbol)`` returns that symbol's full history up to
    and including the as-of bar as numpy arrays; the as-of bar is the last element.
    """

    frame: pd.DataFrame
    current: pd.DataFrame
    positions: dict[str, np.ndarray]
    _arrays: dict[str, np.ndarray] = field(default_factory=dict, repr=False)

    def array(self, column: str) -> np.ndarray:
        """Whole-frame float array of ``column`` (converted once, then cached)."""
        arr = self._arrays.get(column)
        if arr is None:
            arr = self.frame[column].to_numpy(dtype=float, na_value=np.nan)
            self._arrays[column] = arr
        return arr

    def window(self, symbol: str, columns: list[str] | tuple[str, ...]) -> dict[str, np.ndarray]:
        pos = self.positions[symbol]
        return {c: self.array(c)[pos] for c in columns}


def as_of_view(panel: pd.DataFrame, as_of: date, columns: list[str] | tuple[str, ...]) -> AsOfView:
    """Slice ``panel`` to bars dated <= ``as_of`` keeping ``columns`` (panel or patterns2 columns).

    Raises KeyError naming any requested column that is neither in the panel nor a patterns2 column.
    """
    wanted = list(dict.fromkeys([SYMBOL_COL, TS_COL, *columns]))
    p2_cols = [c for c in wanted if c in PATTERNS2_COLUMNS and c not in panel.columns]
    missing = [c for c in wanted if c not in panel.columns and c not in p2_cols]
    if missing:
        raise KeyError(f"as_of_view: panel is missing required columns {missing}")
    base = panel if panel.index.is_unique else panel.reset_index(drop=True)
    if base.empty:
        empty = base.iloc[0:0].reindex(columns=wanted)
        return AsOfView(empty, empty, {})
    day = local_day(base[TS_COL])
    mask = (day <= pd.Timestamp(as_of)).to_numpy()
    frame = base.loc[mask, [c for c in wanted if c not in p2_cols]]
    if p2_cols:
        frame = frame.join(patterns2_frame(base).loc[mask, p2_cols])
    frame = frame.sort_values([SYMBOL_COL, TS_COL], kind="mergesort").reset_index(drop=True)
    if frame.empty:
        return AsOfView(frame, frame, {})
    fday = local_day(frame[TS_COL])
    session = fday.max()
    positions = {str(k): v for k, v in frame.groupby(SYMBOL_COL, sort=False).indices.items()}
    last = [p[-1] for p in positions.values() if fday.iloc[p[-1]] == session]
    current = frame.iloc[sorted(last)]
    return AsOfView(frame, current, positions)


# ----------------------------------------------------------------------------------------------- geometry
class Base(NamedTuple):
    """A consolidation ``[start, end]`` (inclusive indices): ``top`` = max high, ``low`` = min low."""

    start: int
    end: int
    top: float
    low: float

    @property
    def length(self) -> int:
        return self.end - self.start + 1

    @property
    def depth(self) -> float:
        return (self.top - self.low) / self.top if self.top > 0 else float("nan")


class CupHandle(NamedTuple):
    """Cup from the left lip ``left`` to the right lip ``right``, handle ``[right, end]``; pivot = high[right]."""

    left: int
    cup_low_idx: int
    right: int
    end: int
    lip: float
    cup_low: float
    pivot: float
    handle_low: float

    @property
    def cup_len(self) -> int:
        return self.right - self.left

    @property
    def depth(self) -> float:
        return (self.lip - self.cup_low) / self.lip

    @property
    def handle_len(self) -> int:
        return self.end - self.right + 1

    @property
    def handle_depth(self) -> float:
        return (self.pivot - self.handle_low) / self.pivot


def flat_base(high: np.ndarray, low: np.ndarray, end: int, max_depth: float, max_bars: int) -> Base | None:
    """Longest window ending at ``end`` (at most ``max_bars``) whose ``(max high - min low) / max high`` stays
    <= ``max_depth``. Scans backwards and stops at the first bar that breaks the depth; None if ``end < 0``.
    """
    if end < 0 or end >= len(high):
        return None
    top, bottom, start = -np.inf, np.inf, end
    for i in range(end, max(-1, end - max_bars), -1):
        if not (np.isfinite(high[i]) and np.isfinite(low[i])):
            break
        new_top, new_low = max(top, high[i]), min(bottom, low[i])
        if new_top <= 0 or (new_top - new_low) / new_top > max_depth:
            break
        top, bottom, start = new_top, new_low, i
    if not np.isfinite(top):
        return None
    return Base(start, end, float(top), float(bottom))


def cup_with_handle(
    high: np.ndarray,
    low: np.ndarray,
    end: int,
    *,
    cup_min_bars: int,
    cup_max_bars: int,
    handle_min_bars: int,
    handle_max_bars: int,
) -> CupHandle | None:
    """Locate a cup with handle whose handle ends at ``end`` (no depth thresholds applied here).

    Right lip = highest high of the last ``handle_max_bars`` bars up to ``end`` (the handle runs from it to
    ``end`` and must last ``handle_min_bars``-``handle_max_bars``); left lip = highest high between
    ``cup_max_bars`` and ``cup_min_bars`` bars before the right lip, and it must top every bar inside the cup;
    cup low = lowest low between the lips. Thresholds (depths, upper-half handle) are the caller's params.
    """
    if end < 0 or end >= len(high):
        return None
    h_lo = max(0, end - handle_max_bars + 1)
    seg = high[h_lo : end + 1]
    if seg.size == 0 or not np.isfinite(seg).all():
        return None
    right = h_lo + int(np.argmax(seg))
    handle_len = end - right + 1
    if handle_len < handle_min_bars or handle_len > handle_max_bars:
        return None
    c_hi, c_lo = right - cup_min_bars, max(0, right - cup_max_bars)
    if c_hi < 0 or c_hi < c_lo:
        return None
    lips = high[c_lo : c_hi + 1]
    if not np.isfinite(lips).all():
        return None
    left = c_lo + int(np.argmax(lips))
    inside_high = high[left + 1 : right]
    inside_low = low[left + 1 : right]
    if inside_low.size == 0 or not (np.isfinite(inside_high).all() and np.isfinite(inside_low).all()):
        return None
    if inside_high.max() > high[left]:
        return None
    cup_low_idx = left + 1 + int(np.argmin(inside_low))
    handle_low = float(np.nanmin(low[right : end + 1]))
    return CupHandle(
        left, cup_low_idx, right, end, float(high[left]), float(low[cup_low_idx]), float(high[right]), handle_low
    )


class Flag(NamedTuple):
    """Flag from the pole top ``top_idx`` to ``end``; ``pivot`` = high[top_idx] (the flag high)."""

    top_idx: int
    end: int
    pivot: float
    low: float
    first_half_low: float
    second_half_low: float

    @property
    def length(self) -> int:
        return self.end - self.top_idx + 1

    @property
    def depth(self) -> float:
        return (self.pivot - self.low) / self.pivot

    @property
    def higher_lows(self) -> bool:
        return self.second_half_low >= self.first_half_low


def flag(high: np.ndarray, low: np.ndarray, end: int, max_bars: int) -> Flag | None:
    """The consolidation since the highest high of the last ``max_bars`` bars up to ``end``.

    ``higher_lows`` compares the lowest low of the second half of the flag with that of the first half (the
    "higher lows, tightening" signature of doc 05). Length thresholds are the caller's params.
    """
    if end < 0 or end >= len(high):
        return None
    lo = max(0, end - max_bars + 1)
    seg_h, seg_l = high[lo : end + 1], low[lo : end + 1]
    if seg_h.size == 0 or not (np.isfinite(seg_h).all() and np.isfinite(seg_l).all()):
        return None
    top = lo + int(np.argmax(seg_h))
    lows = low[top : end + 1]
    half = (len(lows) + 1) // 2
    first, second = lows[:half], lows[half:]
    second_low = float(second.min()) if second.size else float(first.min())
    return Flag(top, end, float(high[top]), float(lows.min()), float(first.min()), second_low)


class GapConsolidation(NamedTuple):
    """Gap day ``gap_idx`` followed by a consolidation ``[gap_idx + 1, end]``; ``pivot`` = its highest high."""

    gap_idx: int
    end: int
    gap_low: float
    pivot: float
    consol_low: float

    @property
    def length(self) -> int:
        return self.end - self.gap_idx


def gap_consolidation(
    gap_day: np.ndarray, high: np.ndarray, low: np.ndarray, end: int, min_bars: int, max_bars: int
) -> GapConsolidation | None:
    """Most recent qualifying gap day followed by ``min_bars``-``max_bars`` bars up to ``end`` that all hold
    above the gap-day low ("holds above the gap-day low", doc 13). ``gap_day`` is a boolean array."""
    if end < 0 or end >= len(high):
        return None
    for g in range(end - min_bars, max(-1, end - max_bars - 1), -1):
        if not bool(gap_day[g]):
            continue
        consol_h, consol_l = high[g + 1 : end + 1], low[g + 1 : end + 1]
        if not (np.isfinite(consol_h).all() and np.isfinite(consol_l).all() and np.isfinite(low[g])):
            return None
        if consol_l.min() <= low[g]:
            return None
        return GapConsolidation(g, end, float(low[g]), float(consol_h.max()), float(consol_l.min()))
    return None


def prior_advance(low: np.ndarray, top: float, start: int, lookback: int) -> float:
    """``top / min(low over the lookback bars before start) - 1`` (the run-up into a base); NaN if no data."""
    seg = low[max(0, start - lookback) : start]
    seg = seg[np.isfinite(seg)]
    if seg.size == 0 or seg.min() <= 0:
        return float("nan")
    return float(top / seg.min() - 1.0)
