"""Deterministic synthetic panels for research tests: no network, no vendor data.

- ``make_panel``: GBM panel with an optional planted edge. When ``flag == 1`` at the close of day t, the next
  ``drift_days`` bars carry extra log-return drift totalling ``edge``; ``edge=0`` is a pure random walk.
- ``make_ranker_panel``: feature-contract columns filled with noise plus one feature that predicts the
  forward-return rank with a chosen strength.
- ``make_bars``: hand-scripted OHLC bars for one symbol (for exact-fill tests).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from swing_engine.research.ranker import RANKER_FEATURES

TZ = "America/New_York"
BASE_PRICE = 100.0
DEFAULT_START = "2022-01-03"
GAP_VOL_FRACTION = 0.3  # overnight gap volatility as a fraction of daily volatility
WICK_VOL_FRACTION = 0.5
VOLUME_RANGE = (500_000, 5_000_000)
ATR_WINDOW = 14
FLAG_COLUMN = "flag"
PLANTED_FEATURE = "mom_12_1"
PLANTED_NEGATIVE_FEATURE = "rev_5d"


def trading_dates(n_days: int, start: str = DEFAULT_START) -> pd.DatetimeIndex:
    return pd.bdate_range(start, periods=n_days, tz=TZ)


def _bars_from_close(close: np.ndarray, rng: np.random.Generator, daily_vol: float) -> dict[str, np.ndarray]:
    n = close.size
    prev = np.concatenate([[BASE_PRICE], close[:-1]])
    open_ = prev * np.exp(rng.normal(0.0, daily_vol * GAP_VOL_FRACTION, n))
    wick = np.abs(rng.normal(0.0, daily_vol * WICK_VOL_FRACTION, (2, n)))
    high = np.maximum(open_, close) * np.exp(wick[0])
    low = np.minimum(open_, close) * np.exp(-wick[1])
    volume = rng.integers(VOLUME_RANGE[0], VOLUME_RANGE[1], n).astype(float)
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev), np.abs(low - prev)))
    atr = pd.Series(tr).rolling(ATR_WINDOW, min_periods=1).mean().to_numpy()
    return {
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "vwap": (high + low + close) / 3.0,
        "adj_close": close,
        "atr_14": atr,
    }


def make_panel(
    n_symbols: int = 20,
    n_days: int = 400,
    seed: int = 0,
    edge: float = 0.0,
    flag_prob: float = 0.05,
    daily_vol: float = 0.015,
    drift_days: int = 5,
    start: str = DEFAULT_START,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = trading_dates(n_days, start)
    frames = []
    for k in range(n_symbols):
        r = rng.normal(0.0, daily_vol, n_days)
        flag = (rng.random(n_days) < flag_prob).astype(int)
        if edge:
            boost = np.zeros(n_days)
            for t in np.flatnonzero(flag):
                boost[t + 1 : min(t + 1 + drift_days, n_days)] += edge / drift_days
            r = r + boost
        close = BASE_PRICE * np.exp(np.cumsum(r))
        cols = _bars_from_close(close, rng, daily_vol)
        frames.append(pd.DataFrame({"symbol": f"SYM{k:03d}", "ts": dates, **cols, FLAG_COLUMN: flag}))
    return pd.concat(frames, ignore_index=True)


def make_ranker_panel(
    n_symbols: int = 40,
    n_days: int = 300,
    seed: int = 1,
    strength: float = 0.6,
    horizon: int = 10,
    daily_vol: float = 0.02,
    start: str = DEFAULT_START,
) -> pd.DataFrame:
    """Noise features plus ``mom_12_1`` (positively) and ``rev_5d`` (negatively) tied to the forward return."""
    rng = np.random.default_rng(seed)
    dates = trading_dates(n_days, start)
    frames = []
    for k in range(n_symbols):
        r = rng.normal(0.0, daily_vol, n_days)
        close = BASE_PRICE * np.exp(np.cumsum(r))
        fwd = np.full(n_days, np.nan)
        fwd[:-horizon] = close[horizon:] / close[:-horizon] - 1.0
        z = np.nan_to_num(fwd / (daily_vol * np.sqrt(horizon)))
        cols = _bars_from_close(close, rng, daily_vol)
        feats = {f: rng.normal(0.0, 1.0, n_days) for f in RANKER_FEATURES}
        feats[PLANTED_FEATURE] = strength * z + rng.normal(0.0, 1.0, n_days)
        feats[PLANTED_NEGATIVE_FEATURE] = -strength * z + rng.normal(0.0, 1.0, n_days)
        cols.pop("atr_14")
        frames.append(pd.DataFrame({"symbol": f"RNK{k:03d}", "ts": dates, **cols, **feats}))
    return pd.concat(frames, ignore_index=True)


def make_bars(
    symbol: str,
    ohlc: list[tuple[float, float, float, float]],
    start: str = "2024-01-02",
    volume: float = 1_000_000.0,
) -> pd.DataFrame:
    arr = np.asarray(ohlc, dtype=float)
    dates = trading_dates(len(arr), start)
    prev = np.concatenate([[arr[0, 3]], arr[:-1, 3]])
    tr = np.maximum(arr[:, 1] - arr[:, 2], np.maximum(np.abs(arr[:, 1] - prev), np.abs(arr[:, 2] - prev)))
    return pd.DataFrame(
        {
            "symbol": symbol,
            "ts": dates,
            "open": arr[:, 0],
            "high": arr[:, 1],
            "low": arr[:, 2],
            "close": arr[:, 3],
            "volume": volume,
            "vwap": arr[:, 1:].mean(axis=1),
            "adj_close": arr[:, 3],
            "atr_14": pd.Series(tr).rolling(ATR_WINDOW, min_periods=1).mean().to_numpy(),
            FLAG_COLUMN: 0,
        }
    )
