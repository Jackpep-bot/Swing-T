"""``build_panel``: the one entry point other modules call (``docs/api-contract.md``).

Takes the long bars frame from ``data.store.Store.read_bars`` and returns the same frame with every column of
``docs/feature-contract.md`` appended. All features are computed per symbol with only past data, so the
panel is point-in-time: truncating the input at date ``T`` never changes a value at or before ``T``.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
import structlog

from ._common import ADJ_CLOSE, OHLCV, SYMBOL_COL, TS_COL, VWAP, require_columns, symbol_codes
from .cross_section import CROSS_SECTION_COLUMNS, add_cross_section
from .indicators import INDICATOR_COLUMNS, add_indicators
from .levels import LEVEL_COLUMNS, add_levels
from .patterns import PATTERN_COLUMNS, add_patterns
from .regime import MARKET_REGIME_COLUMNS, REGIME_COLUMNS, add_market_regime, add_regime

log = structlog.get_logger(__name__)

REQUIRED_BAR_COLUMNS: tuple[str, ...] = (SYMBOL_COL, TS_COL, *OHLCV)
OPTIONAL_BAR_COLUMNS: tuple[str, ...] = (VWAP, ADJ_CLOSE)
FEATURE_COLUMNS: tuple[str, ...] = (
    *INDICATOR_COLUMNS,
    *CROSS_SECTION_COLUMNS,
    *LEVEL_COLUMNS,
    *PATTERN_COLUMNS,
    *REGIME_COLUMNS,
    *MARKET_REGIME_COLUMNS,
)
MS_PER_S = 1000.0


def build_panel(bars: pd.DataFrame, market: pd.DataFrame | None = None) -> pd.DataFrame:
    """Append every feature column to ``bars`` (long format ``symbol, ts, open, high, low, close, volume, vwap,
    adj_close``) and return the result sorted by ``symbol, ts`` with a fresh ``RangeIndex``.

    ``market`` is an optional bars frame for one symbol (SPY); its regime is broadcast by session into
    ``market_trend_state`` / ``market_vol_regime`` (NaN when omitted). Duplicate ``(symbol, ts)`` rows keep
    the last one and are logged. OHLCV columns are cast to ``float64``; ``vwap`` / ``adj_close`` are added as
    NaN when absent. Pure pandas/numpy, deterministic, no network.
    """
    t0 = time.perf_counter()
    require_columns(bars, REQUIRED_BAR_COLUMNS, "build_panel")
    df = bars.sort_values([SYMBOL_COL, TS_COL], kind="mergesort").reset_index(drop=True)
    dup = df.duplicated([SYMBOL_COL, TS_COL], keep="last")
    if dup.any():
        log.warning("features.duplicate_bars_dropped", rows=int(dup.sum()))
        df = df.loc[~dup].reset_index(drop=True)
    df = df.assign(**{c: df[c].astype("float64") for c in OHLCV})
    df = df.assign(**{c: np.nan for c in OPTIONAL_BAR_COLUMNS if c not in df.columns})
    key = symbol_codes(df)
    df = add_indicators(df, key)
    df = add_cross_section(df, key)
    df = add_levels(df)
    df = add_patterns(df, key)
    df = add_regime(df, key)
    df = add_market_regime(df, market)
    missing = [c for c in FEATURE_COLUMNS if c not in df.columns]
    if missing:
        raise RuntimeError(f"build_panel: feature contract columns not produced: {missing}")
    log.info(
        "features.panel_built",
        rows=len(df),
        symbols=int(key.nunique()),
        columns=len(FEATURE_COLUMNS),
        elapsed_ms=round((time.perf_counter() - t0) * MS_PER_S, 1),
    )
    return df
