"""Deterministic geometric-Brownian-motion bar generator for the feature tests (no network, no data package)."""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252
NY_TZ = "America/New_York"


def gbm_bars(
    symbols: list[str],
    n_bars: int = 300,
    seed: int = 0,
    start: str = "2021-01-04",
    s0: float = 50.0,
    mu: float = 0.08,
    sigma: float = 0.35,
) -> pd.DataFrame:
    """Long frame ``symbol, ts, open, high, low, close, volume, vwap, adj_close`` on NYSE-like business days."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=n_bars, tz=NY_TZ)
    frames = []
    for i, sym in enumerate(symbols):
        drift = (mu - 0.5 * sigma**2) / TRADING_DAYS
        step = sigma / np.sqrt(TRADING_DAYS)
        close = s0 * (1.0 + 0.5 * i) * np.exp(np.cumsum(rng.normal(drift, step, n_bars)))
        prev = np.concatenate([[close[0]], close[:-1]])
        open_ = prev * np.exp(rng.normal(0.0, 0.004, n_bars))
        wick = np.abs(rng.normal(0.0, 0.006, (2, n_bars)))
        high = np.maximum(open_, close) * (1.0 + wick[0])
        low = np.minimum(open_, close) * (1.0 - wick[1])
        volume = np.round(np.exp(rng.normal(np.log(1.5e6), 0.5, n_bars)))
        frames.append(
            pd.DataFrame(
                {
                    "symbol": sym,
                    "ts": idx,
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                    "vwap": (high + low + close) / 3.0,
                    "adj_close": close,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def intraday_bars(symbols: list[str], sessions: list[str], minutes: list[int], seed: int = 0) -> pd.DataFrame:
    """Minute bars at the given minutes-from-midnight (NY) on each session date, with random volumes."""
    rng = np.random.default_rng(seed)
    rows = []
    for sym in symbols:
        for day in sessions:
            base = pd.Timestamp(day, tz=NY_TZ)
            for m in minutes:
                rows.append(
                    {
                        "symbol": sym,
                        "ts": base + pd.Timedelta(minutes=m),
                        "volume": float(rng.integers(1_000, 50_000)),
                    }
                )
    return pd.DataFrame(rows)
