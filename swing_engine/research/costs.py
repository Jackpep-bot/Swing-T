"""Per-signal trading cost from our own daily bars (docs/methods.md, "Spread and slippage dominate").

Spread: Abdi-Ranaldo (2017, RFS 30(12)) close-high-low estimator, made point-in-time by pairing day t-1 with day t
(the published form pairs t with t+1): ``s^2 = 4 E[(c_{t-1} - eta_{t-1})(c_{t-1} - eta_t)]`` with c the log close and
eta the log mid-range, averaged over SPREAD_WINDOW sessions, negative estimates set to 0.

Cost per side = max(half the estimated spread, the gate 1 floor): 10 bps for names trading at least
LARGE_CAP_MIN_DOLLAR_VOLUME a day on average (a liquidity proxy for "large cap"; the store has no market caps),
20 bps otherwise (docs/gates.md, research.backtest constants).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from swing_engine.research.backtest import LARGE_CAP_SLIPPAGE_BPS, SMALL_CAP_SLIPPAGE_BPS

SPREAD_WINDOW = 21
#: 20-day average dollar volume above which the large-cap floor applies (proxy; no market-cap history)
LARGE_CAP_MIN_DOLLAR_VOLUME = 50_000_000.0
BPS = 1e4


def cost_table(bars: pd.DataFrame) -> pd.DataFrame:
    """``symbol, as_of, spread_bps, dollar_volume, cost_bps`` per bar, using only bars up to that day."""
    b = bars.sort_values(["symbol", "ts"])[["symbol", "ts", "high", "low", "close", "volume"]].copy()
    c = np.log(b["close"].astype(float))
    eta = (np.log(b["high"].astype(float)) + np.log(b["low"].astype(float))) / 2.0
    prod = (c.groupby(b["symbol"]).shift(1) - eta.groupby(b["symbol"]).shift(1)) * (c.groupby(b["symbol"]).shift(1) - eta)
    s2 = 4.0 * prod.groupby(b["symbol"]).transform(lambda x: x.rolling(SPREAD_WINDOW, min_periods=SPREAD_WINDOW).mean())
    b["spread_bps"] = np.sqrt(s2.clip(lower=0.0)) * BPS
    dv = b["close"].astype(float) * b["volume"].astype(float)
    b["dollar_volume"] = dv.groupby(b["symbol"]).transform(lambda x: x.rolling(SPREAD_WINDOW - 1, min_periods=1).mean())
    floor = np.where(b["dollar_volume"] >= LARGE_CAP_MIN_DOLLAR_VOLUME, LARGE_CAP_SLIPPAGE_BPS, SMALL_CAP_SLIPPAGE_BPS)
    b["cost_bps"] = np.maximum(floor, (b["spread_bps"] / 2.0).fillna(0.0))
    b["as_of"] = pd.to_datetime(b["ts"]).dt.date
    return b[["symbol", "as_of", "spread_bps", "dollar_volume", "cost_bps"]]


def attach_costs(frame: pd.DataFrame, table: pd.DataFrame) -> pd.DataFrame:
    """``frame`` (shadow rows: symbol, as_of) plus ``cost_bps`` and ``dollar_volume`` from the signal day's row of ``table``."""
    left = frame.assign(as_of=pd.to_datetime(frame["as_of"]).dt.date)
    return left.merge(table[["symbol", "as_of", "cost_bps", "dollar_volume"]], on=["symbol", "as_of"], how="left")


__all__ = ["attach_costs", "cost_table"]
