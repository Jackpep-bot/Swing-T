"""Per-symbol, point-in-time return, volatility, liquidity and bar-shape features.

"Cross-section" because these are the columns the ranker compares across symbols on a given date; each one
is still computed within a symbol using only the current and earlier bars. Columns produced by
:func:`add_cross_section` (see ``docs/feature-contract.md``)::

    ret_1d ret_5d ret_21d ret_63d ret_126d ret_252d mom_12_1 rev_5d rev_21d vol_21d vol_63d dollar_vol_20d
    avg_vol_20d avg_vol_50d amihud_21d high_52w low_52w dist_52w_high rvol_day gap_pct range_pct close_pos
    up_days_3 prev_close
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ._common import (
    CLOSE,
    HIGH,
    LOW,
    OPEN,
    TRADING_DAYS_PER_YEAR,
    VOLUME,
    per_symbol,
    require_columns,
    shift_per_symbol,
    symbol_codes,
)

RETURN_WINDOWS: tuple[int, ...] = (1, 5, 21, 63, 126, 252)
MOM_LONG_WINDOW = 252
MOM_SKIP = 21
REVERSAL_WINDOWS: tuple[int, ...] = (5, 21)
VOL_WINDOWS: tuple[int, ...] = (21, 63)
DOLLAR_VOL_WINDOW = 20
AVG_VOL_WINDOWS: tuple[int, ...] = (20, 50)
AMIHUD_WINDOW = 21
AMIHUD_SCALE = 1e6
WINDOW_52W = 252
RVOL_AVG_WINDOW = 20
UP_DAYS_WINDOW = 3
CLOSE_POS_MIDPOINT = 0.5

CROSS_SECTION_COLUMNS: tuple[str, ...] = (
    *(f"ret_{n}d" for n in RETURN_WINDOWS),
    "mom_12_1",
    *(f"rev_{n}d" for n in REVERSAL_WINDOWS),
    *(f"vol_{n}d" for n in VOL_WINDOWS),
    f"dollar_vol_{DOLLAR_VOL_WINDOW}d",
    *(f"avg_vol_{n}d" for n in AVG_VOL_WINDOWS),
    f"amihud_{AMIHUD_WINDOW}d",
    "high_52w",
    "low_52w",
    "dist_52w_high",
    "rvol_day",
    "gap_pct",
    "range_pct",
    "close_pos",
    f"up_days_{UP_DAYS_WINDOW}",
    "prev_close",
)


def pct_return(close: pd.Series, periods: int) -> pd.Series:
    """``close[t] / close[t - periods] - 1``. NaN for the first ``periods`` bars.

    Panel defaults: 1, 5, 21, 63, 126 and 252 bars (``ret_<n>d``).
    """
    return close / close.shift(periods) - 1.0


def momentum_12_1(close: pd.Series, long_window: int = MOM_LONG_WINDOW, skip: int = MOM_SKIP) -> pd.Series:
    """Jegadeesh-Titman 12-1 momentum: ``close[t - skip] / close[t - long_window] - 1``, i.e. the
    252-bar return that skips the most recent 21 bars (defaults 252 / 21). NaN for the first ``long_window`` bars.
    """
    return close.shift(skip) / close.shift(long_window) - 1.0


def reversal(close: pd.Series, periods: int) -> pd.Series:
    """Short-term reversal signal ``-pct_return(close, periods)``: higher means a larger recent decline.
    Panel defaults: 5 and 21 bars (``rev_5d``, ``rev_21d``).
    """
    return -pct_return(close, periods)


def log_returns(close: pd.Series) -> pd.Series:
    """``ln(close[t]) - ln(close[t-1])``."""
    return np.log(close).diff()


def realized_vol(close: pd.Series, window: int, periods_per_year: int = TRADING_DAYS_PER_YEAR) -> pd.Series:
    """Annualised realised volatility ``std(log_returns over window, ddof=1) * sqrt(periods_per_year)``.
    NaN for the first ``window`` bars. Panel defaults: 21 and 63 bars (``vol_21d``, ``vol_63d``).
    """
    return log_returns(close).rolling(window, min_periods=window).std(ddof=1) * np.sqrt(periods_per_year)


def rolling_mean(x: pd.Series, window: int) -> pd.Series:
    """``mean(x[t-window+1 .. t])``; NaN for the first ``window - 1`` bars."""
    return x.rolling(window, min_periods=window).mean()


def rolling_max(x: pd.Series, window: int) -> pd.Series:
    """``max(x[t-window+1 .. t])`` (includes the current bar); NaN for the first ``window - 1`` bars."""
    return x.rolling(window, min_periods=window).max()


def rolling_min(x: pd.Series, window: int) -> pd.Series:
    """``min(x[t-window+1 .. t])`` (includes the current bar); NaN for the first ``window - 1`` bars."""
    return x.rolling(window, min_periods=window).min()


def _amihud_from(abs_ret: pd.Series, dollar_volume: pd.Series, window: int, scale: float) -> pd.Series:
    ratio = (abs_ret / dollar_volume).replace([np.inf, -np.inf], np.nan)
    return rolling_mean(ratio, window) * scale


def amihud(
    close: pd.Series, volume: pd.Series, window: int = AMIHUD_WINDOW, scale: float = AMIHUD_SCALE
) -> pd.Series:
    """Amihud (2002) illiquidity ``mean(|ret_1d| / (close * volume)) * scale`` over ``window`` bars
    (defaults 21 / 1e6). NaN while warming up and whenever a bar in the window had zero dollar volume.
    """
    return _amihud_from(pct_return(close, 1).abs(), close * volume, window, scale)


def gap_pct(open_: pd.Series, prev_close: pd.Series) -> pd.Series:
    """Overnight gap ``open / prev_close - 1``."""
    return open_ / prev_close - 1.0


def range_pct(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Bar range as a fraction of the close ``(high - low) / close``."""
    return (high - low) / close


def close_position(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Where the close sits in the bar ``(close - low) / (high - low)``; 0.5 when ``high == low``."""
    rng = high - low
    pos = (close - low) / rng
    return pos.where(rng != 0, CLOSE_POS_MIDPOINT)


def up_days(close: pd.Series, window: int = UP_DAYS_WINDOW) -> pd.Series:
    """Count of bars in the trailing ``window`` whose close exceeded the prior close (0..window, default 3).
    NaN until ``window`` close-to-close changes are available.
    """
    delta = close.diff()
    up = (delta > 0).astype(float).where(delta.notna())
    return up.rolling(window, min_periods=window).sum()


def add_cross_section(df: pd.DataFrame, key: pd.Series | None = None) -> pd.DataFrame:
    """Return ``df`` with every column in :data:`CROSS_SECTION_COLUMNS` appended, computed within each symbol.

    Definitions not covered by the pure functions above:
    ``dollar_vol_20d = mean(close * volume, 20)``; ``avg_vol_<n>d = mean(volume, n)`` (includes the current bar);
    ``high_52w / low_52w = max(high) / min(low)`` over 252 bars; ``dist_52w_high = close / high_52w - 1``;
    ``rvol_day = volume / avg_vol_20d.shift(1)`` (today's volume against the average of the *prior* 20
    bars, the practitioner definition, so the bar does not dilute its own benchmark);
    ``prev_close = close.shift(1)``. ``df`` must be sorted by ``symbol, ts``.
    """
    require_columns(df, (OPEN, HIGH, LOW, CLOSE, VOLUME), "add_cross_section")
    key = symbol_codes(df) if key is None else key
    close, volume = df[CLOSE], df[VOLUME]
    new: dict[str, pd.Series] = {}
    for n in RETURN_WINDOWS:
        new[f"ret_{n}d"] = per_symbol(close, key, pct_return, n)
    new["mom_12_1"] = per_symbol(close, key, momentum_12_1, MOM_LONG_WINDOW, MOM_SKIP)
    for n in REVERSAL_WINDOWS:
        new[f"rev_{n}d"] = -new[f"ret_{n}d"]
    for n in VOL_WINDOWS:
        new[f"vol_{n}d"] = per_symbol(close, key, realized_vol, n)
    dollar_volume = close * volume
    new[f"dollar_vol_{DOLLAR_VOL_WINDOW}d"] = per_symbol(dollar_volume, key, rolling_mean, DOLLAR_VOL_WINDOW)
    for n in AVG_VOL_WINDOWS:
        new[f"avg_vol_{n}d"] = per_symbol(volume, key, rolling_mean, n)
    ratio = (new["ret_1d"].abs() / dollar_volume).replace([np.inf, -np.inf], np.nan)
    new[f"amihud_{AMIHUD_WINDOW}d"] = per_symbol(ratio, key, rolling_mean, AMIHUD_WINDOW) * AMIHUD_SCALE
    new["high_52w"] = per_symbol(df[HIGH], key, rolling_max, WINDOW_52W)
    new["low_52w"] = per_symbol(df[LOW], key, rolling_min, WINDOW_52W)
    new["dist_52w_high"] = close / new["high_52w"] - 1.0
    prior_avg = shift_per_symbol(new[f"avg_vol_{RVOL_AVG_WINDOW}d"], key, 1)
    new["rvol_day"] = volume / prior_avg
    prev_close = shift_per_symbol(close, key, 1)
    new["gap_pct"] = gap_pct(df[OPEN], prev_close)
    new["range_pct"] = range_pct(df[HIGH], df[LOW], close)
    new["close_pos"] = close_position(df[HIGH], df[LOW], close)
    new[f"up_days_{UP_DAYS_WINDOW}"] = per_symbol(close, key, up_days, UP_DAYS_WINDOW)
    new["prev_close"] = prev_close
    return df.assign(**new)
