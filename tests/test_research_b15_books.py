from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing_engine.research import b15_books as b15


def test_quality_signs_and_standardisation():
    rng = np.random.default_rng(3)
    v = pd.DataFrame(rng.normal(size=(60, 3)), columns=list(b15.INPUTS), index=[f"s{i}" for i in range(60)])
    v.loc["s0"] = [5.0, -5.0, -5.0]  # high ROE, low accruals, low leverage: best
    v.loc["s1"] = [-5.0, 5.0, 5.0]
    q = b15.quality(v)
    assert q.idxmax() == "s0" and q.idxmin() == "s1"
    assert q.mean() == pytest.approx(0.0, abs=1e-9) and q.std() == pytest.approx(1.0)


def test_target_caps_and_spy_rest():
    mcap = pd.Series(np.r_[[5000.0], np.linspace(100, 1, 499)], index=[f"s{i}" for i in range(500)])
    q = pd.Series(np.linspace(2, -2, 500), index=mcap.index)
    w = b15.target(mcap, q, list(mcap.index[:100]))
    assert w.sum() == pytest.approx(1.0) and w.drop("SPY", errors="ignore").max() <= 0.05 + 1e-12


def test_plan_starts_in_spy_and_keeps_holders_in_the_buffer():
    names = [f"s{i}" for i in range(200)]
    rng = np.random.default_rng(4)
    u = pd.DataFrame(rng.normal(size=(200, 3)), columns=list(b15.INPUTS), index=names).assign(mcap_pit=100.0)
    days = [date(2017, 6, 19), date(2017, 12, 18)]
    orders = b15.plan({days[0]: u, days[1]: u}, date(2016, 1, 4))
    assert orders[date(2016, 1, 4)].to_dict() == {"SPY": 1.0}
    held = [set(orders[d].index) - {"SPY"} for d in days]
    assert len(held[0]) == 100 and held[0] == held[1]
