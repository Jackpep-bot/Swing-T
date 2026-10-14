from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing_engine.data.calendar import trading_days
from swing_engine.research import b12_books as b12


def test_trend_weights_on_off_cap_and_bills():
    days = trading_days("2016-01-04", "2017-03-31")
    k = np.arange(len(days))
    wiggle = np.where(k % 2 == 0, 1.0, -1.0)
    data = {}
    for j, a in enumerate(b12.ASSETS):
        drift = 0.0005 if j < 6 else -0.0005  # the last three trend down: OFF
        vol = 0.002 if a == "IEF" else 0.01  # IEF so calm its weight hits the 30% cap
        data[a] = 100.0 * np.cumprod(1.0 + drift + vol * wiggle)
    closes = pd.DataFrame(data, index=days)
    assert b12.trend_weights(closes, 251).empty  # 2016 has 252 sessions: no 252-session return before 2017
    w = b12.trend_weights(closes, len(days) - 1)
    assert set(w.index) == {"SPY", "EFA", "EEM", "VNQ", "IEF", "TLT", "BIL"} and w["IEF"] == pytest.approx(0.30)
    sigma = closes["SPY"].pct_change().iloc[-63:].std(ddof=1) * np.sqrt(252)
    assert w["SPY"] == pytest.approx(0.10 / 9 / sigma) and w.sum() == pytest.approx(1.0) and w["BIL"] > 0
    orders = b12.trend_orders(closes, list(days))
    assert min(orders) == date(2017, 2, 1)  # first signal 2017-01-31, traded at the next open


def test_industry_scores_pool_small_industries():
    raw = pd.Series({"a1": 0.1, "a2": 0.2, "a3": 0.3, "a4": 0.4, "a5": 0.5, "b1": 0.9, "b2": -0.1, "z": 0.0})
    ind = pd.Series({"a1": 36.0, "a2": 36.0, "a3": 36.0, "a4": 36.0, "a5": 36.0, "b1": 60.0, "b2": 60.0})  # z: no SIC
    s = b12.industry_scores(raw, ind)
    assert s["a5"] == pytest.approx(0.2) and s["b1"] == pytest.approx(0.9) and s["z"] == pytest.approx(0.0)  # b1, b2, z: "other"
    assert b12._after_third_friday(date(2025, 5, 30), trading_days("2025-05-01", "2025-07-31")) == date(2025, 6, 23)
