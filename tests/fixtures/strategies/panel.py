"""Tiny deterministic feature-panel generator for strategy tests.

Mirrors the column names and definitions in docs/feature-contract.md closely enough for the strategies
to be exercised without the real `features` package. No network, seedable, pure pandas.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from datetime import date

import numpy as np
import pandas as pd

TZ = "America/New_York"
START = "2024-01-02"
PIVOT_LOOKBACK = 60
PIVOT_WIDTH = 5
BURST_MIN_VOLUME = 100_000
BREAKOUT_VOL_MULT = 1.5
BURST_RATIO = 1.04
WEEK_52 = 252
WEEK_52_MIN_PERIODS = 20
ANNUALIZE = math.sqrt(252)

BAR_COLUMNS = ["symbol", "ts", "open", "high", "low", "close", "volume", "vwap", "adj_close"]


def business_days(n: int, start: str = START) -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="B", tz=TZ)


def make_bars(
    symbols: Iterable[str],
    n_days: int = 320,
    seed: int = 7,
    start_price: float = 100.0,
    drift: float = 0.0004,
    vol: float = 0.015,
    base_volume: float = 1_000_000.0,
) -> pd.DataFrame:
    """Seeded GBM-ish daily bars, long format, one block per symbol."""
    rng = np.random.default_rng(seed)
    frames = []
    for sym in symbols:
        rets = rng.normal(drift, vol, n_days)
        close = start_price * np.exp(np.cumsum(rets))
        open_ = np.concatenate([[start_price], close[:-1]]) * (1 + rng.normal(0, vol / 4, n_days))
        spread = np.abs(rng.normal(0, vol / 2, n_days))
        high = np.maximum(open_, close) * (1 + spread)
        low = np.minimum(open_, close) * (1 - spread)
        volume = base_volume * np.exp(rng.normal(0, 0.3, n_days))
        frames.append(_frame(sym, open_, high, low, close, volume))
    return pd.concat(frames, ignore_index=True)


def bars_from_ohlc(symbol: str, rows: Sequence[Sequence[float]], start: str = START) -> pd.DataFrame:
    """Hand-constructed bars from (open, high, low, close, volume) tuples."""
    arr = np.asarray(rows, dtype=float)
    return _frame(symbol, arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3], arr[:, 4], start=start)


def bars_from_closes(
    symbol: str, closes: Sequence[float], volume: float = 1_000_000.0, spread: float = 0.005, start: str = START
) -> pd.DataFrame:
    """Bars whose open is the prior close and whose high/low wrap open/close by `spread`."""
    c = np.asarray(closes, dtype=float)
    o = np.concatenate([[c[0]], c[:-1]])
    h = np.maximum(o, c) * (1 + spread)
    lo = np.minimum(o, c) * (1 - spread)
    return _frame(symbol, o, h, lo, c, np.full(len(c), float(volume)), start=start)


def _frame(sym, o, h, lo, c, v, start: str = START) -> pd.DataFrame:
    n = len(c)
    return pd.DataFrame(
        {
            "symbol": sym,
            "ts": business_days(n, start),
            "open": o,
            "high": h,
            "low": lo,
            "close": c,
            "volume": v,
            "vwap": (h + lo + c) / 3,
            "adj_close": c,
        }
    )


def _rsi(close: pd.Series, n: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    return rsi.where(loss > 0, 100.0).where(delta.notna())


def pivot_levels(
    high: pd.Series, low: pd.Series, close: pd.Series, lookback: int = PIVOT_LOOKBACK, width: int = PIVOT_WIDTH
) -> tuple[pd.Series, pd.Series]:
    """Nearest confirmed pivot level below / above the PRIOR close (as in features/levels.py)."""
    h, lo, c = high.to_numpy(), low.to_numpy(), close.to_numpy()
    n = len(c)
    piv_hi = [i for i in range(width, n - width) if h[i] == h[i - width : i + width + 1].max()]
    piv_lo = [i for i in range(width, n - width) if lo[i] == lo[i - width : i + width + 1].min()]
    sup = np.full(n, np.nan)
    res = np.full(n, np.nan)
    for t in range(1, n):
        prev_close = c[t - 1]
        lo_bound = t - 1 - lookback
        levels = [h[i] for i in piv_hi if lo_bound <= i and i + width <= t - 1]
        levels += [lo[i] for i in piv_lo if lo_bound <= i and i + width <= t - 1]
        below = [x for x in levels if x < prev_close]
        above = [x for x in levels if x > prev_close]
        if below:
            sup[t] = max(below)
        if above:
            res[t] = min(above)
    return pd.Series(sup, index=close.index), pd.Series(res, index=close.index)


def _features_one(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("ts").reset_index(drop=True)
    o, h, lo, c, v = df["open"], df["high"], df["low"], df["close"], df["volume"]
    prev_close = c.shift(1)
    f = pd.DataFrame(index=df.index)
    f["prev_close"] = prev_close
    f["ret_1d"] = c / prev_close - 1
    for n in (5, 21, 63, 126, 252):
        f[f"ret_{n}d"] = c / c.shift(n) - 1
    f["mom_12_1"] = c.shift(21) / c.shift(252) - 1
    for n in (10, 20, 50, 200):
        f[f"sma_{n}"] = c.rolling(n).mean()
    for n in (9, 21):
        f[f"ema_{n}"] = c.ewm(span=n, adjust=False).mean()
    f["rsi_2"] = _rsi(c, 2)
    f["rsi_14"] = _rsi(c, 14)
    tr = pd.concat([h - lo, (h - prev_close).abs(), (lo - prev_close).abs()], axis=1).max(axis=1)
    f["atr_14"] = tr.ewm(alpha=1 / 14, adjust=False).mean().where(prev_close.notna())
    f["atr_pct_14"] = f["atr_14"] / c
    f["avg_vol_20d"] = v.rolling(20).mean()
    f["avg_vol_50d"] = v.rolling(50).mean()
    f["rvol_day"] = v / f["avg_vol_20d"]
    f["dollar_vol_20d"] = (v * c).rolling(20).mean()
    f["vol_21d"] = f["ret_1d"].rolling(21).std() * ANNUALIZE
    f["high_52w"] = h.rolling(WEEK_52, min_periods=WEEK_52_MIN_PERIODS).max()
    f["low_52w"] = lo.rolling(WEEK_52, min_periods=WEEK_52_MIN_PERIODS).min()
    f["dist_52w_high"] = c / f["high_52w"] - 1
    f["gap_pct"] = o / prev_close - 1
    f["range_pct"] = (h - lo) / c
    f["close_pos"] = ((c - lo) / (h - lo)).where(h > lo)
    up = (c > prev_close).astype(int)
    f["up_days_3"] = up.rolling(3).sum()
    f["burst_4pct"] = ((c / prev_close >= BURST_RATIO) & (v > v.shift(1)) & (v >= BURST_MIN_VOLUME)).astype(int)
    f["breakout_52w"] = ((c > f["high_52w"].shift(1)) & (v >= BREAKOUT_VOL_MULT * f["avg_vol_50d"])).astype(int)
    f["inside_day"] = ((h < h.shift(1)) & (lo > lo.shift(1))).astype(int)
    f["key_reversal"] = 0
    sup, res = pivot_levels(h, lo, c)
    f["support_1"], f["resistance_1"] = sup, res
    f["range_width"] = res - sup
    f["level_touch_pct"] = (lo - sup) / c
    f["level_break"] = (c > res).fillna(False).astype(int)
    f["vcp_contraction"] = np.nan
    f["base_len"] = np.nan
    sma50, sma200 = f["sma_50"], f["sma_200"]
    rising = sma50 > sma50.shift(1)
    trend = pd.Series(0.0, index=df.index)
    trend[(c > sma50) & (sma50 > sma200) & rising] = 1.0
    trend[(c < sma50) & (sma50 < sma200) & ~rising] = -1.0
    f["trend_state"] = trend.where(sma200.notna())
    f["vol_regime"] = 1
    return pd.concat([df, f], axis=1)


def add_features(bars: pd.DataFrame) -> pd.DataFrame:
    """Append contract feature columns per symbol (past-only rolling windows)."""
    parts = [_features_one(g) for _, g in bars.groupby("symbol", sort=False)]
    return pd.concat(parts, ignore_index=True)


def make_panel(symbols: Iterable[str] = ("AAA", "BBB", "CCC"), n_days: int = 320, seed: int = 7) -> pd.DataFrame:
    return add_features(make_bars(symbols, n_days=n_days, seed=seed))


def set_last(panel: pd.DataFrame, symbol: str, **values: float) -> pd.DataFrame:
    """Return a copy with `values` written onto the last row of `symbol` (hand-constructed cases)."""
    out = panel.copy()
    idx = out.index[out["symbol"] == symbol][-1]
    for col, val in values.items():
        if col not in out.columns:
            out[col] = np.nan
        elif not np.issubdtype(out[col].dtype, np.floating):
            out[col] = out[col].astype(float)
        out.loc[idx, col] = float(val)
    return out


def last_date(panel: pd.DataFrame) -> date:
    return panel["ts"].max().date()


def trend_rows(n: int = 100, start: float = 80.0, step: float = 0.4, volume: float = 1_000_000.0) -> list[list[float]]:
    """Straight-line uptrend bars (open=prior close, high=close+0.3, low=open-0.3)."""
    rows = []
    for i in range(n):
        c = start + step * i
        o = c - step if i else c
        rows.append([o, c + 0.3, o - 0.3, c, volume])
    return rows


def range_closes(n: int = 119, low: float = 100.0, high: float = 110.0, period: int = 24) -> list[float]:
    """Sine-wave closes oscillating between `low` and `high` so pivots form at both edges."""
    mid, amp = (high + low) / 2, (high - low) / 2
    return [mid + amp * math.sin(2 * math.pi * i / period) for i in range(n)]
