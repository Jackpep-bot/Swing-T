import numpy as np
import pandas as pd

from swing_engine.data.calendar import trading_days
from swing_engine.research import b20_books as b20


def test_dual_momentum_picks_and_only_trades_on_a_change():
    days = trading_days("2016-01-04", "2018-12-31")
    n = len(days)
    up, flat = np.linspace(100, 200, n), np.full(n, 100.0)
    closes = pd.DataFrame({"SPY": up, "EFA": np.linspace(100, 150, n), "IEF": flat, "BIL": np.linspace(100, 101, n)},
                          index=days)
    assert b20.holding(closes, 10) is None and b20.holding(closes, 300) == "SPY"
    closes.loc[days[400]:, "EFA"] = closes.loc[days[400]:, "EFA"] * 3  # EFA jumps ahead
    assert b20.holding(closes, 500) == "EFA"
    closes.loc[days[600]:, "SPY"] = 50.0  # SPY's year return below bills: bonds
    assert b20.holding(closes, n - 1) == "IEF"
    orders = b20.orders_for(closes, list(days))
    picks = [str(w.index[0]) for _, w in sorted(orders.items())]
    assert picks[0] == "SPY" and all(a != b for a, b in zip(picks, picks[1:], strict=False)) and "IEF" in picks
