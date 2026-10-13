"""research.costs: point-in-time spread estimate and the gate 1 floors."""
from __future__ import annotations

import numpy as np
import pandas as pd

from swing_engine.research import costs


def bars(symbol: str, n: int, price: float, volume: float, spread: float, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    mid = price * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    half = mid * spread / 2.0
    side = rng.choice([-1.0, 1.0], n)  # closes bounce between bid and ask
    close = mid + side * half
    return pd.DataFrame({"symbol": symbol, "ts": pd.bdate_range("2024-01-02", periods=n),
                         "high": np.maximum(mid * 1.01, close), "low": np.minimum(mid * 0.99, close),
                         "close": close, "volume": volume})


def test_floors_and_wide_spread() -> None:
    b = pd.concat([bars("BIG", 120, 100.0, 1_000_000, 0.0), bars("TINY", 120, 3.0, 100_000, 0.0, 1),
                   bars("WIDE", 120, 3.0, 100_000, 0.04, 2)])
    t = costs.cost_table(b).groupby("symbol").tail(1).set_index("symbol")
    assert t.loc["BIG", "cost_bps"] >= costs.LARGE_CAP_SLIPPAGE_BPS
    assert t.loc["TINY", "cost_bps"] >= costs.SMALL_CAP_SLIPPAGE_BPS
    assert t.loc["WIDE", "cost_bps"] > t.loc["TINY", "cost_bps"]  # a 4% bid-ask bounce shows up as cost


def test_point_in_time() -> None:
    b = bars("WIDE", 120, 3.0, 100_000, 0.04, 2)
    full = costs.cost_table(b).set_index("as_of")["cost_bps"]
    cut = costs.cost_table(b.iloc[:80]).set_index("as_of")["cost_bps"]
    pd.testing.assert_series_equal(full.loc[cut.index], cut)
