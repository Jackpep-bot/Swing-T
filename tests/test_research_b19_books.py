from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing_engine.research import b19_books as b19


def test_plan_top_and_bottom_books_with_buffer_and_ineligible_names():
    names = [f"s{i}" for i in range(300)]
    s1 = pd.Series(np.linspace(1.0, -1.0, 300), index=names)
    s2 = s1.copy()
    s2["s0"] = np.nan  # no fresh filing: not eligible, leaves
    s2["s50"] = s1.iloc[140]  # drops to rank ~140: stays
    u = {date(2017, 4, 3): pd.DataFrame({"mcap_pit": 1.0, "surprise": s1}),
         date(2017, 6, 1): pd.DataFrame({"mcap_pit": 1.0, "surprise": s2})}
    o = b19.plan(u, date(2016, 1, 4))
    assert set(o[date(2017, 4, 3)].index) == set(names[:100])
    h2 = set(o[date(2017, 6, 1)].index)
    assert "s0" not in h2 and "s50" in h2 and len(h2) == 100
    assert o[date(2017, 4, 3)].sum() == pytest.approx(1.0)
    low = b19.plan(u, date(2016, 1, 4), sign=-1.0)
    assert set(low[date(2017, 4, 3)].index) == set(names[200:])
