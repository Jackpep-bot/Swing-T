"""Point-in-time universe construction.

`build_universe(provider, settings, as_of)` applies `UniverseConfig` to reference data and to the trailing
liquidity window ending at `as_of`. Names that were listed at `as_of` stay in the universe even if they
delisted later (survivorship-bias discipline); names delisted before `as_of` drop out.

Reference data: a provider with `universe_reference(include_etfs, delisted_since)` (massive) supplies only
common stock (+ ADRs, + ETFs when allowed), active plus the names delisted since the lookback window began;
other providers fall back to `list_symbols(include_delisted=True)`. Rows already in the store's `symbols`
table are added for tickers the provider no longer reports, so a name seen in any earlier snapshot keeps its
type after it delists. Tickers in the bars with no reference row at all are dropped: that removes the
preferreds, warrants, units and rights a grouped-daily feed carries, at the cost of also dropping a common
stock that delisted before the delisted-name paging window and was never seen in a snapshot (or traded
under a ticker it later changed). That residual survivorship gap is accepted and grows smaller the longer
the nightly ingest runs.

Liquidity bars, in order of preference: the `bars` argument, the `store` (grouped ingest keeps the whole
market there), the provider's `grouped_daily` (one call per lookback session), else per-symbol `daily_bars`.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import structlog

from swing_engine.core.config import Settings, UniverseConfig
from swing_engine.core.interfaces import BarProvider

from ._common import TZ, as_date, empty_bars, normalize_symbols, session_ts
from .calendar import trading_days
from .store import Store

log = structlog.get_logger(__name__)

LIQUIDITY_LOOKBACK_SESSIONS = 20  # matches avg_vol_20d / dollar_vol_20d in the feature contract
MIN_SESSIONS_FOR_SCREEN = 10  # a name needs at least this many bars in the window to be screened in
LOOKBACK_CALENDAR_PAD_DAYS = 15  # calendar days of slack so the window always holds enough sessions

COMMON_STOCK_TYPES = frozenset({"CS", "COMMON STOCK", "COMMON", "ADRC", "ADR", "STOCK", "US_EQUITY"})
ETF_TYPES = frozenset({"ETF", "ETN", "ETV", "ETS", "FUND", "INDEX"})
OTC_EXCHANGES = frozenset({"OTC", "OTCM", "OTCB", "OTCQ", "OTCQB", "OTCQX", "PINX", "OOTC", "XOTC", "PINK"})
SYMBOLS_TABLE = "symbols"  # the reference table `data.ingest` maintains


def _is_otc(exchange: object) -> bool:
    if exchange is None or (isinstance(exchange, float) and pd.isna(exchange)):
        return False
    ex = str(exchange).upper()
    return ex in OTC_EXCHANGES or ex.startswith("OTC")


def _type_allowed(kind: object, include_etfs: bool) -> bool:
    if kind is None or (isinstance(kind, float) and pd.isna(kind)):
        return True  # unknown type: let the liquidity screen decide
    k = str(kind).upper()
    if k in ETF_TYPES:
        return include_etfs
    return k in COMMON_STOCK_TYPES


def _naive_dates(values: pd.Series) -> pd.Series:
    """Reference dates as naive Timestamps whether the column holds `date`s, Timestamps or datetime64
    (the store returns datetime64[us]; providers return `date` objects)."""
    out = pd.to_datetime(values, errors="coerce")
    if getattr(out.dt, "tz", None) is not None:
        out = out.dt.tz_localize(None)
    return out.dt.normalize()


def filter_symbols(symbols: pd.DataFrame, cfg: UniverseConfig, as_of: date) -> pd.DataFrame:
    """Reference-data filters: listed at `as_of`, not delisted before it, exchange/type rules."""
    if symbols.empty:
        return symbols
    df = symbols.copy()
    as_of_ts = pd.Timestamp(as_of)
    listed_at = _naive_dates(df["listed_at"])
    delisted_at = _naive_dates(df["delisted_at"])
    listed = listed_at.isna() | (listed_at <= as_of_ts)
    not_yet_delisted = delisted_at.isna() | (delisted_at > as_of_ts)
    df = df[listed & not_yet_delisted]
    if cfg.exclude_otc:
        df = df[~df["exchange"].map(_is_otc)]
    df = df[df["type"].map(lambda t: _type_allowed(t, cfg.include_etfs))]
    return df


SPLITS_TABLE = "splits"  # symbol, ex_date, split_from, split_to, ratio (= split_to / split_from); see data.ingest


def as_traded(window: pd.DataFrame, splits: pd.DataFrame | None) -> pd.DataFrame:
    """Undo split adjustment so each bar shows the price and share volume that actually traded on its date.

    Split-adjusted history is rewritten by every later split: a $0.80 stock that later did a 1:10 reverse split
    shows as $8.00. A screen at a historical date must use as-traded values or it selects names by their future
    corporate actions. For each bar, factor = product of ``ratio`` (split_to / split_from) over the symbol's
    splits with ex_date AFTER the bar; as-traded close = close * factor, volume = volume / factor. Dollar volume
    is invariant. Without a splits table the window is returned unchanged (documented limitation)."""
    if splits is None or len(splits) == 0 or window.empty:
        return window
    sp = splits.copy()
    sp["symbol"] = sp["symbol"].astype(str).str.upper()
    sp["ex_date"] = pd.to_datetime(sp["ex_date"]).dt.date
    sp = sp[sp["symbol"].isin(set(window["symbol"].astype(str).str.upper()))]
    if sp.empty:
        return window
    out = window.copy()
    bar_dates = pd.to_datetime(out["ts"], utc=True).dt.tz_convert(TZ).dt.date
    factor = pd.Series(1.0, index=out.index)
    for row in sp.itertuples(index=False):
        ratio = float(row.ratio) if row.ratio and row.ratio == row.ratio else None
        if not ratio or ratio <= 0:
            continue
        hit = (out["symbol"].astype(str).str.upper() == row.symbol) & (bar_dates < row.ex_date)
        factor[hit] *= ratio
    out["close"] = out["close"] * factor
    out["volume"] = out["volume"] / factor
    return out


def liquidity_screen(
    bars: pd.DataFrame, cfg: UniverseConfig, as_of: date, splits: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Per-symbol stats over the last `LIQUIDITY_LOOKBACK_SESSIONS` bars at or before `as_of`, on as-traded
    prices and volumes when a splits table is given: columns symbol, last_close, avg_volume, avg_dollar_volume,
    sessions, passes."""
    cols = ["symbol", "last_close", "avg_volume", "avg_dollar_volume", "sessions", "passes"]
    if bars.empty:
        return pd.DataFrame(columns=cols)
    window = bars[bars["ts"] <= session_ts(as_of)].sort_values(["symbol", "ts"])
    window = window.groupby("symbol", sort=False).tail(LIQUIDITY_LOOKBACK_SESSIONS)
    if window.empty:
        return pd.DataFrame(columns=cols)
    window = as_traded(window, splits)
    dollar = window["close"] * window["volume"]
    stats = (
        window.assign(_dollar=dollar)
        .groupby("symbol")
        .agg(
            last_close=("close", "last"),
            avg_volume=("volume", "mean"),
            avg_dollar_volume=("_dollar", "mean"),
            sessions=("close", "size"),
            last_ts=("ts", "max"),
        )
        .reset_index()
    )
    # the last bar must be recent: a name whose bars stopped long before as_of is dead
    cutoff = session_ts(as_of) - timedelta(days=LOOKBACK_CALENDAR_PAD_DAYS)
    stats["passes"] = (
        (stats["sessions"] >= MIN_SESSIONS_FOR_SCREEN)
        & (stats["last_ts"] >= cutoff)
        & (stats["last_close"] >= cfg.min_price)
        & (stats["avg_volume"] >= cfg.min_avg_volume)
        & (stats["avg_dollar_volume"] >= cfg.min_avg_dollar_volume)
    )
    return stats[cols]


def _lookback_start(as_of: date) -> date:
    sessions = trading_days(as_of - timedelta(days=LIQUIDITY_LOOKBACK_SESSIONS * 2 + LOOKBACK_CALENDAR_PAD_DAYS), as_of)
    return sessions[-LIQUIDITY_LOOKBACK_SESSIONS] if len(sessions) >= LIQUIDITY_LOOKBACK_SESSIONS else sessions[0]


def lookback_window(as_of: date | str) -> tuple[date, date]:
    """(first, last) session dates of the liquidity window ending at `as_of` (read these bars from a store)."""
    as_of_d = as_date(as_of)
    return _lookback_start(as_of_d), as_of_d


def _stored_reference(store: Store | None) -> pd.DataFrame:
    if store is None or not store.has_table(SYMBOLS_TABLE):
        return pd.DataFrame()
    try:
        return store.read_table(SYMBOLS_TABLE)
    except Exception as exc:  # pragma: no cover - a damaged table must not block the screen
        log.warning("universe_symbols_table_unreadable", error=str(exc))
        return pd.DataFrame()


def reference_symbols(
    provider: BarProvider, cfg: UniverseConfig, delisted_since: date, store: Store | None = None
) -> pd.DataFrame:
    """Reference rows to screen: the provider's typed universe reference when it has one, else its full
    listing; plus store `symbols` rows for tickers the provider did not return (provider rows win)."""
    typed = getattr(provider, "universe_reference", None)
    if callable(typed):
        fresh = typed(include_etfs=cfg.include_etfs, delisted_since=delisted_since)
    else:
        fresh = provider.list_symbols(include_delisted=True)
    stored = _stored_reference(store)
    if stored.empty or "symbol" not in stored.columns:
        return fresh
    if fresh is None or len(fresh) == 0:
        return normalize_symbols(stored)
    extra = stored[~stored["symbol"].astype(str).str.upper().isin(set(fresh["symbol"].astype(str)))]
    if extra.empty:
        return fresh
    return normalize_symbols(pd.concat([extra, fresh], ignore_index=True))


def _window_bars(
    provider: BarProvider, store: Store | None, names: list[str], start: date, as_of: date
) -> pd.DataFrame:
    if store is not None:
        stored = store.read_bars(None, start, as_of)
        if not stored.empty:
            return stored
        log.warning("universe_store_window_empty", start=str(start), as_of=str(as_of))
    grouped = getattr(provider, "grouped_daily", None)
    if callable(grouped):
        frames = [grouped(d) for d in trading_days(start, as_of)]
        frames = [f for f in frames if f is not None and not f.empty]
        return pd.concat(frames, ignore_index=True) if frames else empty_bars()
    return provider.daily_bars(names, start, as_of)


def build_universe(
    provider: BarProvider,
    settings: Settings,
    as_of: date | str,
    *,
    bars: pd.DataFrame | None = None,
    store: Store | None = None,
    splits: pd.DataFrame | None = None,
) -> list[str]:
    """Symbols that pass `settings.universe` at `as_of`, ranked by average dollar volume, capped at
    `max_symbols`. `static_symbols` overrides the screen. Pass `bars` (e.g. a panel) or `store` (a DuckDB
    store filled by grouped ingest) to screen without fetching the liquidity window from the provider."""
    cfg = settings.universe
    as_of_d = as_date(as_of)
    if cfg.static_symbols:
        return sorted({s.upper() for s in cfg.static_symbols})
    start = _lookback_start(as_of_d)
    symbols = reference_symbols(provider, cfg, start, store)
    candidates = filter_symbols(symbols, cfg, as_of_d)
    if candidates.empty:
        log.warning("universe_empty_after_reference_filters", as_of=str(as_of_d))
        return []
    names = sorted(candidates["symbol"].tolist())
    if bars is None:
        bars = _window_bars(provider, store, names, start, as_of_d)
    bars = bars[bars["symbol"].isin(names)]
    if splits is None and store is not None and store.has_table(SPLITS_TABLE):
        splits = store.read_table(SPLITS_TABLE)
    stats = liquidity_screen(bars, cfg, as_of_d, splits)
    passed = stats[stats["passes"]].sort_values(["avg_dollar_volume", "symbol"], ascending=[False, True])
    universe = passed["symbol"].head(cfg.max_symbols).tolist()
    log.info(
        "universe_built", as_of=str(as_of_d), candidates=len(names), screened=len(stats),
        passed=int(stats["passes"].sum()) if len(stats) else 0, size=len(universe),
    )
    return sorted(universe)
