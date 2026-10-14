from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing_engine.research import b17_books as b17


def test_plan_holds_the_calmest_with_a_buffer_and_caps():
    names = [f"s{i}" for i in range(300)]
    v1 = pd.Series(np.linspace(0.10, 0.60, 300), index=names)
    v2 = v1.copy()
    v2["s99"] = 0.40  # a holder drops to rank ~180: out; s5 to rank ~120: stays
    v2["s5"] = v1.iloc[119] + 1e-6
    days = [date(2017, 2, 21), date(2017, 5, 22)]
    o = b17.plan({days[0]: v1, days[1]: v2}, date(2016, 1, 4))
    assert o[date(2016, 1, 4)].to_dict() == {"SPY": 1.0}
    h1, h2 = set(o[days[0]].index), set(o[days[1]].index)
    assert h1 == set(names[:100]) and "s5" in h2 and "s99" not in h2 and len(h2) == 100
    w = o[days[0]]
    assert w.sum() == pytest.approx(1.0) and w.max() <= 0.03 + 1e-12 and w["s0"] >= w["s99"]


def test_target_fewer_names_leave_spy():
    w = b17.target(pd.Series([0.2] * 50, index=[f"s{i}" for i in range(50)]), [f"s{i}" for i in range(50)])
    assert w["SPY"] == pytest.approx(0.5) and w.drop("SPY").sum() == pytest.approx(0.5)
