from datetime import date

import pandas as pd
import pytest

from swing_engine.data.calendar import trading_days
from swing_engine.research import b22_books as b22


def test_plan_holds_recent_opportunistic_buys_at_two_percent():
    sessions = list(trading_days("2016-12-01", "2017-06-30"))
    ev = pd.DataFrame({"symbol": ["A", "B", "C", "D"], "value": [1e6, 2e6, 1e6, 1e6],
                       "filed": [date(2017, 1, 10), date(2017, 1, 20), date(2017, 1, 20), date(2017, 1, 25)],
                       "cmp_class": ["opportunistic", "opportunistic", "routine", "opportunistic"],
                       "member": [True, True, True, False]})
    uni = pd.DataFrame({"mcap_pit": [1e9, 1e9, 1e9, 1e9]}, index=["A", "B", "C", "D"])
    universes = {d: uni for d in sessions}
    orders, names = b22.plan(ev, universes, sessions, "opportunistic")
    feb = orders[date(2017, 2, 1)]
    assert set(feb.index) == {"A", "B", "SPY"} and feb["A"] == pytest.approx(0.02) and feb["SPY"] == pytest.approx(0.96)
    assert set(orders[date(2017, 6, 1)].index) == {"SPY"}  # more than 63 sessions after filing: gone
    placebo, _ = b22.plan(ev, universes, sessions, "routine")
    assert set(placebo[date(2017, 2, 1)].index) == {"C", "SPY"}
