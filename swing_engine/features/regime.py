"""Trend and volatility regime states, per symbol and for the market (SPY) broadcast to every row.

Columns produced by :func:`add_regime` / :func:`add_market_regime`::

    trend_state          1 up:   close > sma_50 > sma_200 and sma_50 above its value 5 bars earlier
                        -1 down: close < sma_50 < sma_200 and sma_50 below its value 5 bars earlier
                         0 otherwise; NaN while the SMAs warm up
    vol_regime           0 low / 1 normal / 2 high: rolling percentile rank of vol_21d within the trailing
                         252 bars, <= 0.25 low, >= 0.75 high; NaN while warming up
    market_trend_state   trend_state of the ``market`` frame on the same session (NaN when no market given)
    market_vol_regime    vol_regime of the ``market`` frame on the same session (NaN when no market given)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ._common import (
    CLOSE,
    SYMBOL_COL,
    TS_COL,
    per_symbol,
    require_columns,
    session_key,
    shift_per_symbol,
    symbol_codes,
)
from .cross_section import VOL_WINDOWS, realized_vol
from .indicators import sma

TREND_FAST_WINDOW = 50
TREND_SLOW_WINDOW = 200
TREND_SLOPE_LOOKBACK = 5
VOL_REGIME_SOURCE_WINDOW = VOL_WINDOWS[0]  # vol_21d
VOL_REGIME_LOOKBACK = 252
VOL_REGIME_LOW_PCT = 0.25
VOL_REGIME_HIGH_PCT = 0.75
TREND_UP = 1.0
TREND_FLAT = 0.0
TREND_DOWN = -1.0
VOL_LOW = 0.0
VOL_NORMAL = 1.0
VOL_HIGH = 2.0
_SESSION = "_session"

REGIME_COLUMNS: tuple[str, ...] = ("trend_state", "vol_regime")
MARKET_REGIME_COLUMNS: tuple[str, ...] = ("market_trend_state", "market_vol_regime")


def trend_state_from(
    close: pd.Series, sma_fast: pd.Series, sma_slow: pd.Series, sma_fast_lagged: pd.Series
) -> pd.Series:
    """Element-wise trend state from precomputed averages: ``1`` when ``close > sma_fast > sma_slow`` and
    ``sma_fast > sma_fast_lagged``; ``-1`` on the mirror; else ``0``; NaN where any input is NaN.
    """
    slope = sma_fast - sma_fast_lagged
    up = (close > sma_fast) & (sma_fast > sma_slow) & (slope > 0)
    down = (close < sma_fast) & (sma_fast < sma_slow) & (slope < 0)
    out = pd.Series(np.where(up, TREND_UP, np.where(down, TREND_DOWN, TREND_FLAT)), index=close.index)
    valid = close.notna() & sma_fast.notna() & sma_slow.notna() & sma_fast_lagged.notna()
    return out.where(valid)


def trend_state(
    close: pd.Series,
    fast: int = TREND_FAST_WINDOW,
    slow: int = TREND_SLOW_WINDOW,
    slope_lookback: int = TREND_SLOPE_LOOKBACK,
) -> pd.Series:
    """Trend state for one symbol's closes: ``trend_state_from(close, sma(close, fast), sma(close, slow),
    sma(close, fast).shift(slope_lookback))``. Defaults 50 / 200 / 5 bars.
    """
    fast_sma = sma(close, fast)
    return trend_state_from(close, fast_sma, sma(close, slow), fast_sma.shift(slope_lookback))


def vol_regime(
    vol: pd.Series,
    lookback: int = VOL_REGIME_LOOKBACK,
    low_pct: float = VOL_REGIME_LOW_PCT,
    high_pct: float = VOL_REGIME_HIGH_PCT,
) -> pd.Series:
    """``pct = percentile rank of vol[t] within vol[t-lookback+1 .. t]``; ``0`` when ``pct <= low_pct``,
    ``2`` when ``pct >= high_pct``, else ``1``; NaN until ``lookback`` observations. Defaults 252 / 0.25 / 0.75.
    """
    pct = vol.rolling(lookback, min_periods=lookback).rank(pct=True)
    out = pd.Series(
        np.where(pct <= low_pct, VOL_LOW, np.where(pct >= high_pct, VOL_HIGH, VOL_NORMAL)), index=vol.index
    )
    return out.where(pct.notna())


def _regime_inputs(df: pd.DataFrame, key: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """``(sma_fast, sma_slow, vol)`` taken from the panel when present, otherwise computed per symbol."""
    close = df[CLOSE]
    fast_col, slow_col, vol_col = (
        f"sma_{TREND_FAST_WINDOW}",
        f"sma_{TREND_SLOW_WINDOW}",
        f"vol_{VOL_REGIME_SOURCE_WINDOW}d",
    )
    fast = df[fast_col] if fast_col in df else per_symbol(close, key, sma, TREND_FAST_WINDOW)
    slow = df[slow_col] if slow_col in df else per_symbol(close, key, sma, TREND_SLOW_WINDOW)
    vol = df[vol_col] if vol_col in df else per_symbol(close, key, realized_vol, VOL_REGIME_SOURCE_WINDOW)
    return fast, slow, vol


def add_regime(df: pd.DataFrame, key: pd.Series | None = None) -> pd.DataFrame:
    """Return ``df`` with ``trend_state`` and ``vol_regime`` appended (per symbol; ``df`` sorted by symbol, ts).
    Uses ``sma_50``, ``sma_200`` and ``vol_21d`` from the frame when present, else computes them.
    """
    require_columns(df, (CLOSE,), "add_regime")
    key = symbol_codes(df) if key is None else key
    fast, slow, vol = _regime_inputs(df, key)
    return df.assign(
        trend_state=trend_state_from(
            df[CLOSE], fast, slow, shift_per_symbol(fast, key, TREND_SLOPE_LOOKBACK)
        ),
        vol_regime=per_symbol(
            vol, key, vol_regime, VOL_REGIME_LOOKBACK, VOL_REGIME_LOW_PCT, VOL_REGIME_HIGH_PCT
        ),
    )


def market_regime(market: pd.DataFrame) -> pd.DataFrame:
    """Per-session ``market_trend_state`` / ``market_vol_regime`` for a single-symbol bars frame (e.g. SPY).

    Returns one row per session keyed by ``_session`` (naive New York midnight), last row kept on duplicates.
    """
    require_columns(market, (TS_COL, CLOSE), "market_regime")
    if SYMBOL_COL in market and market[SYMBOL_COL].nunique() > 1:
        raise ValueError("market_regime expects bars for exactly one symbol")
    m = market.sort_values(TS_COL, kind="mergesort").reset_index(drop=True)
    close = m[CLOSE].astype("float64")
    out = pd.DataFrame(
        {
            _SESSION: session_key(m[TS_COL]),
            MARKET_REGIME_COLUMNS[0]: trend_state(close),
            MARKET_REGIME_COLUMNS[1]: vol_regime(realized_vol(close, VOL_REGIME_SOURCE_WINDOW)),
        }
    )
    return out.drop_duplicates(_SESSION, keep="last")


def add_market_regime(df: pd.DataFrame, market: pd.DataFrame | None) -> pd.DataFrame:
    """Return ``df`` with the market regime columns broadcast onto every row by session.

    Both columns are NaN when ``market`` is ``None`` or empty, so the panel schema is stable.
    """
    if market is None or len(market) == 0:
        return df.assign(**{c: np.nan for c in MARKET_REGIME_COLUMNS})
    require_columns(df, (TS_COL,), "add_market_regime")
    mk = market_regime(market)
    left = df.assign(**{_SESSION: session_key(df[TS_COL])})
    out = left.merge(mk, on=_SESSION, how="left", sort=False).drop(columns=[_SESSION])
    out.index = df.index
    return out
