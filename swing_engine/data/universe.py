"""Point-in-time universe construction.

`build_universe(provider, settings, as_of)` applies `UniverseConfig` to the provider's symbol list and to
the trailing liquidity window ending at `as_of`. Names that were listed at `as_of` stay in the universe
even if they delisted later (survivorship-bias discipline); names delisted before `as_of` drop out.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import structlog

from swing_engine.core.config import Settings, UniverseConfig
from swing_engine.core.interfaces import BarProvider

from ._common import as_date, session_ts
from .calendar import trading_days

log = structlog.get_logger(__name__)

LIQUIDITY_LOOKBACK_SESSIONS = 20  # matches avg_vol_20d / dollar_vol_20d in the feature contract
MIN_SESSIONS_FOR_SCREEN = 10  # a name needs at least this many bars in the window to be screened in
LOOKBACK_CALENDAR_PAD_DAYS = 15  # calendar days of slack so the window always holds enough sessions

COMMON_STOCK_TYPES = frozenset({"CS", "COMMON STOCK", "COMMON", "ADRC", "ADR", "STOCK", "US_EQUITY"})
ETF_TYPES = frozenset({"ETF", "ETN", "ETV", "ETS", "FUND", "INDEX"})
OTC_EXCHANGES = frozenset({"OTC", "OTCM", "OTCB", "OTCQ", "OTCQB", "OTCQX", "PINX", "OOTC", "XOTC", "PINK"})


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


def liquidity_screen(bars: pd.DataFrame, cfg: UniverseConfig, as_of: date) -> pd.DataFrame:
    """Per-symbol stats over the last `LIQUIDITY_LOOKBACK_SESSIONS` bars at or before `as_of`:
    columns symbol, last_close, avg_volume, avg_dollar_volume, sessions, passes."""
    cols = ["symbol", "last_close", "avg_volume", "avg_dollar_volume", "sessions", "passes"]
    if bars.empty:
        return pd.DataFrame(columns=cols)
    window = bars[bars["ts"] <= session_ts(as_of)].sort_values(["symbol", "ts"])
    window = window.groupby("symbol", sort=False).tail(LIQUIDITY_LOOKBACK_SESSIONS)
    if window.empty:
        return pd.DataFrame(columns=cols)
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


def build_universe(
    provider: BarProvider,
    settings: Settings,
    as_of: date | str,
    *,
    bars: pd.DataFrame | None = None,
) -> list[str]:
    """Symbols that pass `settings.universe` at `as_of`, ranked by average dollar volume, capped at
    `max_symbols`. `static_symbols` overrides the screen. Pass `bars` (e.g. from the store) to avoid
    re-fetching the liquidity window from the provider."""
    cfg = settings.universe
    as_of_d = as_date(as_of)
    if cfg.static_symbols:
        return sorted({s.upper() for s in cfg.static_symbols})
    symbols = provider.list_symbols(include_delisted=True)
    candidates = filter_symbols(symbols, cfg, as_of_d)
    if candidates.empty:
        log.warning("universe_empty_after_reference_filters", as_of=str(as_of_d))
        return []
    names = sorted(candidates["symbol"].tolist())
    if bars is None:
        bars = provider.daily_bars(names, _lookback_start(as_of_d), as_of_d)
    else:
        bars = bars[bars["symbol"].isin(names)]
    stats = liquidity_screen(bars, cfg, as_of_d)
    passed = stats[stats["passes"]].sort_values(["avg_dollar_volume", "symbol"], ascending=[False, True])
    universe = passed["symbol"].head(cfg.max_symbols).tolist()
    log.info(
        "universe_built", as_of=str(as_of_d), candidates=len(names), screened=len(stats),
        passed=int(stats["passes"].sum()) if len(stats) else 0, size=len(universe),
    )
    return sorted(universe)
