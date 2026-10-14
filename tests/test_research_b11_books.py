from datetime import date

import pandas as pd
import pytest

from swing_engine.data.calendar import trading_days
from swing_engine.research import b11_books as b11

SESSIONS = trading_days("2016-01-04", "2019-12-31")
POS = {d: i for i, d in enumerate(SESSIONS)}


def test_calendar_helpers_and_book():
    assert b11.recon_day(2025, trading_days("2025-06-01", "2025-07-10")) == date(2025, 6, 30)  # last Friday 06-27
    assert date(2017, 4, 28) in b11.last_session_of_month(SESSIONS, 4)
    assert date(2016, 1, 8) in b11.week_ends(SESSIONS) and date(2016, 1, 7) not in b11.week_ends(SESSIONS)
    book = b11.capped_book(["A", "B"], 0.04)
    assert book.to_dict() == pytest.approx({"A": 0.04, "B": 0.04, "SPY": 0.92})
    assert b11.capped_book([], 0.04).to_dict() == {"SPY": 1.0}
    assert sum(b11.capped_book([f"s{i}" for i in range(40)], 0.04)) == pytest.approx(1.0)  # 40 x 2.5%: no SPY


def test_dividend_events():
    def row(sym, day, rate, special=False):
        return {"store_symbol": sym, "ex_date": pd.Timestamp(day), "rate_adj": rate, "special": special, "foreign": False}

    div = pd.DataFrame([
        row("UP", "2016-03-01", 1.0), row("UP", "2016-06-01", 1.12),  # +12%: an increase
        row("BIG", "2016-03-01", 1.0), row("BIG", "2016-06-01", 3.5),  # 3.5x: a data error, ignored
        row("SPC", "2016-03-01", 1.0), row("SPC", "2016-06-01", 2.0, special=True),  # specials never count
        row("NEW", "2017-09-01", 0.5),  # started after 400+ sessions of bars, after 2017-08-01: an initiation
        row("EARLY", "2017-06-01", 0.5),  # an initiation before 2017-08-01: not counted
        row("YOUNG", "2017-09-01", 0.5),  # its bars start too late
    ])
    first = {"UP": 0, "BIG": 0, "SPC": 0, "NEW": 0, "EARLY": 0, "YOUNG": POS[date(2017, 1, 3)]}
    ev = b11.dividend_events(div, SESSIONS, first)
    assert set(map(tuple, ev[["symbol", "kind"]].to_numpy())) == {("UP", "increase"), ("NEW", "initiation")}
    orders = b11.dividend_orders(ev, lambda day: {"UP", "NEW"}, SESSIONS)
    held = {d: set(w.index) - {"SPY"} for d, w in orders.items()}
    assert held[date(2016, 6, 6)] == {"UP"} and held[date(2016, 9, 12)] == set()  # 63 sessions later: gone
    assert held[date(2017, 9, 5)] == {"NEW"} and orders[date(2017, 9, 5)]["SPY"] == pytest.approx(0.96)


def test_migrant_cohorts_and_routes():
    april = b11.last_session_of_month(SESSIONS, 4)
    ranks = {april[0]: pd.Series({"FELL": 900.0, "STAYED": 100.0, "ROSE": 1200.0}),
             april[1]: pd.Series({"FELL": 1100.0, "STAYED": 120.0, "ROSE": 800.0})}
    orders, counts = b11.migrant_orders(lambda d: ranks.get(d, pd.Series(dtype=float)), SESSIONS)
    day = b11.recon_day(2017, SESSIONS)
    assert orders[SESSIONS[0]].to_dict() == {"SPY": 1.0} and set(orders[day].index) == {"FELL", "SPY"}
    assert counts[2017] == 1
    promoted, _ = b11.migrant_orders(lambda d: ranks.get(d, pd.Series(dtype=float)), SESSIONS, promoted=True)
    assert set(promoted[day].index) == {"ROSE", "SPY"}

    def res(a_t, b_t, p_t, a_alpha=0.01, b_alpha=0.01):
        mk = lambda t, al: {"stats": {"haircut_sharpe": 0.5}, "vs": {"alpha_ann": al, "alpha_t": t}}  # noqa: E731
        return {"A": mk(a_t, a_alpha), "B": mk(b_t, b_alpha), "pooled": mk(p_t, 0.01)}

    assert b11.verdict(res(3.0, 3.0, 1.0))[1] == "PASS"  # route 1
    assert b11.verdict(res(1.5, 1.6, 2.5))[1] == "PASS"  # route 2
    assert b11.verdict(res(1.5, 1.6, 2.5, b_alpha=-0.01))[1] == "FAIL"  # pooled, but one half negative
