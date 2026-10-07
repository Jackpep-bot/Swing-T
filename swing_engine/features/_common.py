"""Shared helpers for the feature modules.

Column names, the per-symbol transform wrapper that turns a pure ``Series -> Series`` function into a
point-in-time panel column, and the session key used to align a market-level frame (SPY) with the
per-symbol panel. Nothing here imports outside ``swing_engine.core``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

import numpy as np
import pandas as pd

SYMBOL_COL = "symbol"
TS_COL = "ts"
OPEN = "open"
HIGH = "high"
LOW = "low"
CLOSE = "close"
VOLUME = "volume"
VWAP = "vwap"
ADJ_CLOSE = "adj_close"
OHLCV: tuple[str, ...] = (OPEN, HIGH, LOW, CLOSE, VOLUME)
NY_TZ = "America/New_York"
TRADING_DAYS_PER_YEAR = 252


def require_columns(df: pd.DataFrame, cols: Iterable[str], where: str) -> None:
    """Raise ``ValueError`` naming every column in ``cols`` that is absent from ``df``."""
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{where}: missing columns {missing}")


def symbol_codes(df: pd.DataFrame) -> pd.Series:
    """Integer group key for ``df[symbol]``, factorised once so that repeated groupbys stay cheap."""
    codes, _ = pd.factorize(df[SYMBOL_COL], sort=False)
    return pd.Series(codes, index=df.index, name="_symbol_code")


def per_symbol(values: pd.Series, key: pd.Series, fn: Callable[..., pd.Series], *args: Any) -> pd.Series:
    """Apply a pure ``Series -> Series`` function to ``values`` separately within each symbol group.

    ``fn`` must use only the current and earlier rows of the series it receives (rolling / ewm / shift),
    which is what makes the result a valid point-in-time feature. The index of ``values`` is preserved.
    """
    return values.groupby(key, sort=False, observed=True).transform(fn, *args)


def shift_per_symbol(values: pd.Series, key: pd.Series, periods: int = 1) -> pd.Series:
    """``values.shift(periods)`` evaluated within each symbol group (no bleed across symbols)."""
    return values.groupby(key, sort=False, observed=True).shift(periods)


def group_positions(df: pd.DataFrame) -> dict[Any, np.ndarray]:
    """Positional row indices of each symbol's rows, in the frame's current (sorted) order."""
    return df.groupby(SYMBOL_COL, sort=False, observed=True).indices


def session_key(ts: pd.Series) -> pd.Series:
    """Naive midnight timestamp of the New York session each bar belongs to (merge key for market frames)."""
    t = ts
    if t.dt.tz is not None:
        t = t.dt.tz_convert(NY_TZ).dt.tz_localize(None)
    return t.dt.normalize()
