from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing_engine.data.calendar import trading_days
from swing_engine.research import b9_books as b9

SESSIONS = trading_days("2023-01-03", "2025-12-31")


def test_reference_and_rebalance_days():
    refs = b9.reference_days(SESSIONS)
    assert date(2025, 2, 28) in refs and date(2025, 8, 29) in refs and date(2024, 2, 29) in refs and len(refs) == 6
    assert b9.rebalance_day(date(2025, 2, 28), SESSIONS) == date(2025, 3, 24)  # third Friday 2025-03-21
    assert b9.rebalance_day(date(2025, 8, 29), SESSIONS) == date(2025, 9, 22)  # third Friday 2025-09-19


def test_momentum_value_uses_months_13_to_1_and_needs_history():
    days = trading_days("2023-01-03", "2025-02-28")
    k = np.arange(len(days))
    closes = pd.DataFrame({"UP": 100.0 * 1.001 ** k * (1 + 0.01 * (k % 2)), "YOUNG": np.where(k > len(days) - 200, 50.0, np.nan)},
                          index=days)
    last_month = closes.index > date(2025, 1, 28)
    jumped = closes.assign(UP=np.where(last_month, closes["UP"] * 2, closes["UP"]))  # the skipped month never counts
    v = b9.momentum_values(closes, date(2025, 2, 28))
    assert list(v.index) == ["UP"] and v["UP"] > 0
    assert b9.momentum_values(jumped, date(2025, 2, 28))["UP"] == pytest.approx(v["UP"])


def test_scores_select_buffer_and_caps():
    z, s = b9.scores(pd.Series(np.arange(10.0), index=list("abcdefghij")))
    assert s["j"] == pytest.approx(1 + z["j"]) and s["a"] == pytest.approx(1 / (1 - z["a"])) and (s > 0).all()
    z = pd.Series(-np.arange(200.0), index=[f"s{i}" for i in range(200)])  # s0 best ... s199 worst
    picked = b9.select(z, current={"s110", "s150"})
    assert len(picked) == 100 and "s110" in picked and "s150" not in picked  # ranked 111 (kept) and 151 (dropped)
    assert "s99" not in picked and "s98" in picked  # the kept holding takes the last slot
    w = b9.capped_weights(pd.Series([10.0, 1.0, 1.0]), pd.Series([0.5, 0.5, 0.5]))
    assert w.sum() == pytest.approx(1.0) and w.iloc[0] == pytest.approx(0.5) and w.iloc[1] == pytest.approx(0.25)
    caps = b9.caps_for(pd.Series([0.05, 0.02, 0.01] + [0.001] * 97))  # 3 x cap weight holds well under 100%
    assert caps.sum() == pytest.approx(1.0) and caps.max() == pytest.approx(0.09)
    assert (b9.caps_for(pd.Series([0.2] * 5)) == 0.09).all()  # five names cannot reach 100% under 9% each


def test_trend_switch_band_and_orders():
    days = trading_days("2024-01-02", "2025-06-30")
    px = np.full(len(days), 100.0)
    px[220:] = 100.5  # above the average but inside the 1% band: no switch
    px[240:] = 102.0  # through the band: SSO
    px[300:] = 98.0  # through the lower band: BIL
    st = b9.switch_states(pd.Series(px, index=days))
    assert np.isnan(st.iloc[198]) and st.iloc[199] == 0 and st.iloc[230] == 0 and st.iloc[245] == 1 and st.iloc[305] == 0
    orders = b9.switch_orders(st, days[210])
    assert list(orders) == [days[210], days[241], days[301]]
    assert list(orders[days[210]].index) == ["BIL"] and list(orders[days[241]].index) == ["SSO"]
