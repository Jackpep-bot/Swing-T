"""Single-series technical indicators.

Every public function is pure (``Series`` in, ``Series`` out, index preserved) and uses only the current and
earlier rows, so ``per_symbol(values, key, fn)`` yields a point-in-time panel column. Warm-up rows are NaN:
an indicator with lookback ``n`` is NaN for the first ``n - 1`` bars (``n`` bars for diff-based ones).

Columns produced by :func:`add_indicators` (see ``docs/feature-contract.md``)::

    sma_10 sma_20 sma_50 sma_200 ema_9 ema_21 rsi_2 rsi_14 macd macd_signal macd_hist
    bb_upper_20 bb_lower_20 bb_width_20 atr_14 atr_pct_14
"""

from __future__ import annotations

import pandas as pd

from ._common import CLOSE, HIGH, LOW, per_symbol, require_columns, shift_per_symbol, symbol_codes

SMA_WINDOWS: tuple[int, ...] = (10, 20, 50, 200)
EMA_SPANS: tuple[int, ...] = (9, 21)
RSI_PERIODS: tuple[int, ...] = (2, 14)
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BB_WINDOW = 20
BB_STD_MULT = 2.0
ATR_PERIOD = 14
RSI_MAX = 100.0
RSI_NEUTRAL = 50.0

INDICATOR_COLUMNS: tuple[str, ...] = (
    *(f"sma_{w}" for w in SMA_WINDOWS),
    *(f"ema_{s}" for s in EMA_SPANS),
    *(f"rsi_{p}" for p in RSI_PERIODS),
    "macd",
    "macd_signal",
    "macd_hist",
    f"bb_upper_{BB_WINDOW}",
    f"bb_lower_{BB_WINDOW}",
    f"bb_width_{BB_WINDOW}",
    f"atr_{ATR_PERIOD}",
    f"atr_pct_{ATR_PERIOD}",
)


def sma(close: pd.Series, window: int) -> pd.Series:
    """Simple moving average ``mean(close[t-window+1 .. t])``. NaN for the first ``window - 1`` bars.

    Panel defaults: windows 10, 20, 50 and 200.
    """
    return close.rolling(window, min_periods=window).mean()


def rolling_std(x: pd.Series, window: int, ddof: int = 0) -> pd.Series:
    """Rolling standard deviation over ``window`` bars (population, ``ddof=0``, as Bollinger bands use)."""
    return x.rolling(window, min_periods=window).std(ddof=ddof)


def ema(x: pd.Series, span: int) -> pd.Series:
    """Exponential moving average with ``alpha = 2 / (span + 1)`` in recursive form (``adjust=False``):
    ``ema[t] = alpha * x[t] + (1 - alpha) * ema[t-1]``, seeded with the first non-NaN value.
    NaN until ``span`` observations have been seen. Panel defaults: spans 9 and 21.
    """
    return x.ewm(span=span, adjust=False, min_periods=span).mean()


def wilder_smooth(x: pd.Series, period: int) -> pd.Series:
    """Wilder's smoothing (``alpha = 1 / period``): ``s[t] = s[t-1] + (x[t] - s[t-1]) / period``, seeded with
    the first non-NaN value; NaN until ``period`` observations have been seen. Used by RSI and ATR.
    """
    return x.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder). ``gain = max(diff, 0)``, ``loss = max(-diff, 0)``,
    ``RS = wilder(gain, period) / wilder(loss, period)``, ``RSI = 100 - 100 / (1 + RS)``.

    RSI is 100 when the smoothed loss is zero and 50 when both smoothed gain and loss are zero (flat
    prices). NaN for the first ``period`` bars. Default period 14; the panel also carries ``rsi_2`` (Connors).
    """
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = wilder_smooth(gain, period)
    avg_loss = wilder_smooth(loss, period)
    rs = avg_gain / avg_loss
    out = RSI_MAX - RSI_MAX / (1.0 + rs)
    out = out.where(~((avg_loss == 0) & (avg_gain == 0)), RSI_NEUTRAL)
    return out.where(avg_gain.notna() & avg_loss.notna())


def macd_line(close: pd.Series, fast: int = MACD_FAST, slow: int = MACD_SLOW) -> pd.Series:
    """``ema(close, fast) - ema(close, slow)``; defaults 12 / 26. NaN until the slow EMA has warmed up."""
    return ema(close, fast) - ema(close, slow)


def macd(
    close: pd.Series, fast: int = MACD_FAST, slow: int = MACD_SLOW, signal: int = MACD_SIGNAL
) -> pd.DataFrame:
    """MACD triple: ``macd = ema_fast - ema_slow``, ``macd_signal = ema(macd, signal)``,
    ``macd_hist = macd - macd_signal``. Defaults 12 / 26 / 9.
    """
    line = macd_line(close, fast, slow)
    sig = ema(line, signal)
    return pd.DataFrame({"macd": line, "macd_signal": sig, "macd_hist": line - sig})


def _bands(mid: pd.Series, sd: pd.Series, n_std: float) -> tuple[pd.Series, pd.Series, pd.Series]:
    upper = mid + n_std * sd
    lower = mid - n_std * sd
    return upper, lower, (upper - lower) / mid


def bollinger(close: pd.Series, window: int = BB_WINDOW, n_std: float = BB_STD_MULT) -> pd.DataFrame:
    """Bollinger bands: ``mid = sma(close, window)``, ``sd = population std over window``,
    ``upper / lower = mid +/- n_std * sd``, ``width = (upper - lower) / mid``. Defaults 20 / 2.0.
    """
    upper, lower, width = _bands(sma(close, window), rolling_std(close, window), n_std)
    return pd.DataFrame(
        {f"bb_upper_{window}": upper, f"bb_lower_{window}": lower, f"bb_width_{window}": width}
    )


def true_range(high: pd.Series, low: pd.Series, prev_close: pd.Series) -> pd.Series:
    """``max(high - low, |high - prev_close|, |low - prev_close|)``; ``high - low`` where ``prev_close`` is NaN."""
    parts = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1)
    return parts.max(axis=1)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = ATR_PERIOD) -> pd.Series:
    """Average True Range: Wilder smoothing of :func:`true_range` over ``period`` (default 14)."""
    return wilder_smooth(true_range(high, low, close.shift(1)), period)


def add_indicators(df: pd.DataFrame, key: pd.Series | None = None) -> pd.DataFrame:
    """Return ``df`` with every column in :data:`INDICATOR_COLUMNS` appended, computed within each symbol.

    ``df`` must be sorted by ``symbol, ts`` (``panel.build_panel`` does this). ``key`` is the optional
    pre-factorised symbol key from :func:`_common.symbol_codes`. ``atr_pct_14 = atr_14 / close``.
    """
    require_columns(df, (HIGH, LOW, CLOSE), "add_indicators")
    key = symbol_codes(df) if key is None else key
    close = df[CLOSE]
    new: dict[str, pd.Series] = {}
    for w in SMA_WINDOWS:
        new[f"sma_{w}"] = per_symbol(close, key, sma, w)
    for s in EMA_SPANS:
        new[f"ema_{s}"] = per_symbol(close, key, ema, s)
    for p in RSI_PERIODS:
        new[f"rsi_{p}"] = per_symbol(close, key, rsi, p)
    line = per_symbol(close, key, macd_line, MACD_FAST, MACD_SLOW)
    sig = per_symbol(line, key, ema, MACD_SIGNAL)
    new["macd"], new["macd_signal"], new["macd_hist"] = line, sig, line - sig
    mid = new.get(f"sma_{BB_WINDOW}")
    if mid is None:
        mid = per_symbol(close, key, sma, BB_WINDOW)
    upper, lower, width = _bands(mid, per_symbol(close, key, rolling_std, BB_WINDOW), BB_STD_MULT)
    new[f"bb_upper_{BB_WINDOW}"], new[f"bb_lower_{BB_WINDOW}"], new[f"bb_width_{BB_WINDOW}"] = (
        upper,
        lower,
        width,
    )
    tr = true_range(df[HIGH], df[LOW], shift_per_symbol(close, key, 1))
    atr_s = per_symbol(tr, key, wilder_smooth, ATR_PERIOD)
    new[f"atr_{ATR_PERIOD}"] = atr_s
    new[f"atr_pct_{ATR_PERIOD}"] = atr_s / close
    return df.assign(**new)
