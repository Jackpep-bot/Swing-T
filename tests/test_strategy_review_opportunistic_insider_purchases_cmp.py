"""Review fix: opportunistic_insider_purchases_cmp signals only on the session a filing becomes public
(card: opp_buy_flag = 1 if a filing landed on as_of), not on every session the 21-session sum stays >= $25k."""
from __future__ import annotations

from swing_engine.strategies.opportunistic_insider_purchases_cmp import OpportunisticInsiderPurchases
from tests.fixtures.strategies.panel import last_date, make_panel, set_last


def test_stale_filing_in_rolling_sum_does_not_resignal():
    p = make_panel(("AAA", "BBB"), n_days=320, seed=5).assign(opp_buy_value_21d=0.0, opp_buy_flag=0.0)
    s = OpportunisticInsiderPurchases({"min_trend_state": -1})
    as_of = last_date(p)
    # filing landed earlier: value still in the 21-session sum, but no new filing on as_of
    stale = set_last(p, "AAA", opp_buy_value_21d=50_000, trend_state=1.0)
    assert s.signals(stale, as_of) == []
    fresh = set_last(stale, "AAA", opp_buy_flag=1.0)
    assert [x.symbol for x in s.signals(fresh, as_of)] == ["AAA"]
    # no flag column at all -> no signals (cannot tell a fresh filing from a stale one)
    assert s.signals(fresh.drop(columns="opp_buy_flag"), as_of) == []
