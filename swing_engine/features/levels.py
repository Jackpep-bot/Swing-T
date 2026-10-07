"""Pivot-based support / resistance levels.

A *pivot high* is a bar whose high is the maximum of the ``2 * width + 1`` bars centred on it (pivot lows
mirror this on the low). A pivot at bar ``i`` is only *confirmed* once the ``width`` bars after it have
printed, i.e. at bar ``i + width``; before that it is not known and must not be used. Levels in force at
bar ``t`` are therefore the pivots with ``t - lookback <= i <= t - 1 - width`` (confirmed by the prior close
and inside the lookback), which keeps every column point-in-time.

Columns produced by :func:`add_levels` (defaults: lookback 60 bars, pivot width 5)::

    support_1       nearest confirmed pivot-low level below the prior close
    resistance_1    nearest confirmed pivot-high level above the prior close
    range_width     resistance_1 - support_1
    level_touch_pct (low - support_1) / close   (negative when the low pierced support)
    level_break     1 if close > resistance_1 else 0
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from ._common import CLOSE, HIGH, LOW, group_positions, require_columns

LEVEL_LOOKBACK = 60
PIVOT_WIDTH = 5

LEVEL_COLUMNS: tuple[str, ...] = (
    "support_1",
    "resistance_1",
    "range_width",
    "level_touch_pct",
    "level_break",
)


def _pivots(x: np.ndarray, width: int, highs: bool) -> np.ndarray:
    """Boolean mask of bars that are the extreme of the ``2 * width + 1`` bars centred on them."""
    n = len(x)
    span = 2 * width + 1
    out = np.zeros(n, dtype=bool)
    if n < span:
        return out
    windows = sliding_window_view(x, span)
    ext = windows.max(axis=1) if highs else windows.min(axis=1)
    centre = x[width : n - width]
    out[width : n - width] = (centre >= ext) if highs else (centre <= ext)
    return out


def pivot_highs(high: pd.Series, width: int = PIVOT_WIDTH) -> pd.Series:
    """True where ``high[i] == max(high[i-width .. i+width])``. Note the mask at ``i`` is only knowable at
    ``i + width``; :func:`support_resistance` applies that delay."""
    return pd.Series(_pivots(high.to_numpy(dtype=float), width, highs=True), index=high.index)


def pivot_lows(low: pd.Series, width: int = PIVOT_WIDTH) -> pd.Series:
    """True where ``low[i] == min(low[i-width .. i+width])`` (same confirmation delay as :func:`pivot_highs`)."""
    return pd.Series(_pivots(low.to_numpy(dtype=float), width, highs=False), index=low.index)


def _trailing_windows(level: np.ndarray, lookback: int, win: int) -> np.ndarray:
    """Row ``t`` holds ``level[t - lookback .. t - 1 - width]`` (NaN-padded before the first bar)."""
    padded = np.concatenate([np.full(lookback, np.nan), level])
    return sliding_window_view(padded, win)[: len(level)]


def _nearest(level: np.ndarray, ref: np.ndarray, lookback: int, win: int, above: bool) -> np.ndarray:
    windows = _trailing_windows(level, lookback, win)
    ref_col = ref[:, None]
    if above:
        out = np.where(windows > ref_col, windows, np.inf).min(axis=1)
    else:
        out = np.where(windows < ref_col, windows, -np.inf).max(axis=1)
    out = out.astype(float)
    out[~np.isfinite(out)] = np.nan
    return out


def support_resistance_arrays(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    lookback: int = LEVEL_LOOKBACK,
    width: int = PIVOT_WIDTH,
) -> tuple[np.ndarray, np.ndarray]:
    """``(support_1, resistance_1)`` for one symbol's bars in time order (numpy core of the module)."""
    win = lookback - width
    if win <= 0:
        raise ValueError("lookback must exceed the pivot width")
    n = len(close)
    if n == 0:
        return np.empty(0), np.empty(0)
    ph_level = np.where(_pivots(high, width, highs=True), high, np.nan)
    pl_level = np.where(_pivots(low, width, highs=False), low, np.nan)
    prev_close = np.empty(n, dtype=float)
    prev_close[0] = np.nan
    prev_close[1:] = close[:-1]
    support = _nearest(pl_level, prev_close, lookback, win, above=False)
    resistance = _nearest(ph_level, prev_close, lookback, win, above=True)
    return support, resistance


def support_resistance(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    lookback: int = LEVEL_LOOKBACK,
    width: int = PIVOT_WIDTH,
) -> pd.DataFrame:
    """Nearest confirmed pivot-low below / pivot-high above the prior close, for one symbol in time order.

    Columns ``support_1`` and ``resistance_1``; NaN when no qualifying pivot exists in the lookback.
    Defaults: lookback 60 bars, pivot width 5.
    """
    sup, res = support_resistance_arrays(
        high.to_numpy(dtype=float), low.to_numpy(dtype=float), close.to_numpy(dtype=float), lookback, width
    )
    return pd.DataFrame({"support_1": sup, "resistance_1": res}, index=close.index)


def add_levels(df: pd.DataFrame, lookback: int = LEVEL_LOOKBACK, width: int = PIVOT_WIDTH) -> pd.DataFrame:
    """Return ``df`` with every column in :data:`LEVEL_COLUMNS` appended (per symbol; ``df`` sorted by symbol, ts)."""
    require_columns(df, (HIGH, LOW, CLOSE), "add_levels")
    high = df[HIGH].to_numpy(dtype=float)
    low = df[LOW].to_numpy(dtype=float)
    close = df[CLOSE].to_numpy(dtype=float)
    support = np.full(len(df), np.nan)
    resistance = np.full(len(df), np.nan)
    for idx in group_positions(df).values():
        support[idx], resistance[idx] = support_resistance_arrays(
            high[idx], low[idx], close[idx], lookback, width
        )
    with np.errstate(invalid="ignore"):
        level_break = (close > resistance).astype(np.int64)
    return df.assign(
        support_1=support,
        resistance_1=resistance,
        range_width=resistance - support,
        level_touch_pct=(low - support) / close,
        level_break=level_break,
    )
