from __future__ import annotations

from datetime import timedelta

import pytest

from swing_engine.core import registry
from swing_engine.monitor.rules.account_events import AccountEvents
from swing_engine.monitor.rules.eightk_items import EightKItems, parse_items
from swing_engine.monitor.rules.filing_forms import FilingForms
from swing_engine.monitor.rules.form4_buy_and_cluster import Form4BuyAndCluster, cluster_ok
from swing_engine.monitor.rules.halts_luld import HaltsLuld
from swing_engine.monitor.rules.index_inclusion import IndexInclusion
from swing_engine.monitor.rules.market_wide_suppression import (
    CIRCUIT_BREAKER_HIT,
    SUPPRESSED_HIT,
    MarketWideSuppression,
)
from swing_engine.monitor.rules.rvol_gate_triggers import RvolGateTriggers
from swing_engine.monitor.rules.ssr_trigger import SsrTrigger
from swing_engine.monitor.rules.watchlist_hit import WatchlistHit
from tests.monitor_helpers import T0, base_ctx, make_event

EXPECTED_RULES = {
    "watchlist_hit", "eightk_items", "filing_forms", "form4_buy_and_cluster", "halts_luld", "ssr_trigger",
    "index_inclusion", "rvol_gate_triggers", "market_wide_suppression", "account_events",
}


def test_all_rules_registered():
    assert EXPECTED_RULES <= set(registry.names("rule"))
    for n in EXPECTED_RULES:
        assert registry.get("rule", n)().name == n


def test_watchlist_hit():
    r = WatchlistHit()
    e = make_event(symbols=["ACME"])
    assert r.evaluate(e, base_ctx(held={"ACME"})) == ("held_hit", "P2")
    assert r.evaluate(e, base_ctx(watch={"ACME"})) == ("watchlist_hit", "P1")
    assert r.evaluate(e, base_ctx()) is None
    assert r.evaluate(make_event(symbols=[]), base_ctx(held={"ACME"})) is None


@pytest.mark.parametrize(
    "items,held,watch,expected",
    [
        (["4.02", "9.01"], True, False, ("8k:4.02", "P3")),
        (["3.01"], False, True, ("8k:3.01", "P2")),
        (["1.03"], False, False, ("8k:1.03", "P1")),
        (["2.02", "9.01"], False, False, ("8k:2.02", "P1")),
        (["5.02"], True, False, ("8k:5.02", "P2")),
        (["7.01"], False, False, ("8k:7.01", "P0")),
        (["7.01", "9.01"], True, False, ("8k:7.01", "P1")),
    ],
)
def test_eightk_items_severity(items, held, watch, expected):
    e = make_event(source="edgar", kind="filing", symbols=["ACME"], meta={"form_type": "8-K", "items": items})
    ctx = base_ctx(held={"ACME"} if held else None, watch={"ACME"} if watch else None)
    assert EightKItems().evaluate(e, ctx) == expected


def test_eightk_parses_items_from_text_and_ignores_non_8k():
    assert parse_items("Item 2.02: Results ... Item 9.01: Exhibits Item 77.77 nonsense") == ["2.02", "9.01"]
    e = make_event(source="edgar", kind="filing", symbols=["ACME"], meta={"form_type": "8-K/A"},
                   body="Item 1.03: Bankruptcy or Receivership")
    assert EightKItems().evaluate(e, base_ctx(held={"ACME"})) == ("8k:1.03", "P3")
    assert e.meta["items"] == ["1.03"]
    assert EightKItems().evaluate(make_event(kind="filing", meta={"form_type": "10-Q"}), base_ctx()) is None
    assert EightKItems().evaluate(make_event(kind="filing", symbols=["ACME"], meta={"form_type": "8-K"}), base_ctx()) == ("8k:unknown", "P0")


@pytest.mark.parametrize(
    "form,held,expected",
    [
        ("NT 10-K", True, ("filing:NT 10-K", "P3")),
        ("NT 10-Q", False, ("filing:NT 10-Q", "P1")),
        ("SC 13D", True, ("filing:SC 13D", "P2")),
        ("424B5", True, ("filing:424B5", "P2")),
        ("S-3", False, ("filing:S-3", "P1")),
        ("S-3/A", False, ("filing:S-3/A", "P1")),
        ("144", True, ("filing:144", "P1")),
        ("144", False, ("filing:144", "P0")),
        ("10-Q", True, None),
        ("8-K", True, None),
        ("4", True, None),
    ],
)
def test_filing_forms(form, held, expected):
    e = make_event(source="edgar", kind="filing", symbols=["ACME"], meta={"form_type": form})
    out = FilingForms().evaluate(e, base_ctx(held={"ACME"} if held else None))
    assert out == expected
    if expected and form.startswith(("S-", "424B")):
        assert e.meta["dilution"] is True


def _form4(eid, owner, day, price, code="P", acq="A"):
    return make_event(eid, source="edgar", kind="filing", symbols=["ACME"], ts=T0 + timedelta(days=day),
                      meta={"form_type": "4", "transaction_code": code, "acquired_disposed": acq, "owner": owner,
                            "price": price, "transaction_date": (T0 + timedelta(days=day)).date().isoformat()})


def test_form4_buy_then_cluster():
    r = Form4BuyAndCluster()
    ctx = base_ctx()
    assert r.evaluate(_form4("f1", "Alice", 0, 10.0), ctx) == ("form4_buy", "P1")
    assert r.evaluate(_form4("f2", "Bob", 3, 10.5), ctx) == ("form4_buy", "P1")
    out = r.evaluate(_form4("f3", "Carol", 5, 11.0), ctx)
    assert out == ("insider_cluster", "P2")
    assert r.evaluate(_form4("f4", "Alice", 1, 10.0, code="S"), ctx) is None  # sale
    assert r.evaluate(_form4("f5", "Dan", 2, 10.0, code="A"), ctx) is None  # grant / award, not a buy
    assert r.evaluate(_form4("f5", "Dan", 2, 10.0, acq="D"), ctx) is None  # disposed


def test_form4_cluster_rejects_identical_batches_and_expires():
    r = Form4BuyAndCluster()
    ctx = base_ctx()
    for i, name in enumerate(["A", "B", "C", "D"]):
        out = r.evaluate(_form4(f"g{i}", name, 0, 9.99), ctx)
    assert out == ("form4_buy", "P1")  # 100% identical date+price => grant batch, not a cluster
    assert not cluster_ok([{"owner": "x", "date": T0.date(), "price": 1}] * 3)
    ctx2 = base_ctx()
    r.evaluate(_form4("h1", "A", 0, 1.0), ctx2)
    r.evaluate(_form4("h2", "B", 1, 2.0), ctx2)
    assert r.evaluate(_form4("h3", "C", 40, 3.0), ctx2) == ("form4_buy", "P1")  # first two aged out


@pytest.mark.parametrize(
    "code,status,held,watch,expected",
    [
        ("T1", "halted", True, False, ("halt:T1", "P3")),
        ("T2", "halted", False, True, ("halt:T2", "P2")),
        ("T1", "halted", False, False, ("halt:T1", "P1")),
        ("T12", "halted", False, False, ("halt:T12", "P2")),
        ("H10", "halted", True, False, ("halt:H10", "P3")),
        ("LUDP", "paused", False, False, ("halt:LUDP", "P0")),
        ("LUDP", "paused", True, False, ("halt:LUDP", "P2")),
        ("T1", "resumed", True, False, ("resume:T1", "P2")),
        ("MWC1", "halted", True, False, None),
    ],
)
def test_halts(code, status, held, watch, expected):
    e = make_event(kind="halt", symbols=["PUMP"], meta={"reason_code": code, "status": status})
    ctx = base_ctx(held={"PUMP"} if held else None, watch={"PUMP"} if watch else None)
    assert HaltsLuld().evaluate(e, ctx) == expected
    if code == "T12" and expected:
        assert e.meta["toxic"] is True


def test_luld_band_event():
    e = make_event(kind="luld", symbols=["TINY"], meta={"up": 5.5, "down": 4.5})
    assert HaltsLuld().evaluate(e, base_ctx(held={"TINY"})) == ("luld_band", "P1")
    assert HaltsLuld().evaluate(e, base_ctx()) == ("luld_band", "P0")


def test_ssr():
    e = make_event(kind="ssr", symbols=["ACME"])
    assert SsrTrigger().evaluate(e, base_ctx(held={"ACME"})) == ("ssr_trigger", "P3")
    assert SsrTrigger().evaluate(e, base_ctx(watch={"ACME"})) == ("ssr_trigger", "P2")
    assert SsrTrigger().evaluate(e, base_ctx()) == ("ssr_trigger", "P1")
    bar = make_event(kind="bar_trigger", symbols=["ACME"], meta={"trigger": "ssr", "drop_pct": -4.0})
    assert SsrTrigger().evaluate(bar, base_ctx()) is None
    bar.meta["drop_pct"] = -11.0
    assert SsrTrigger().evaluate(bar, base_ctx()) == ("ssr_trigger", "P1")


@pytest.mark.parametrize(
    "title,hit",
    [
        ("Mega Industries Set To Join S&P 500", True),
        ("Acme to be added to the Nasdaq-100 index", True),
        ("Acme will replace Old Co in the S&P MidCap 400", True),
        ("Acme will replace its CFO", False),
        ("Acme reports earnings", False),
    ],
)
def test_index_inclusion(title, hit):
    e = make_event(kind="news", symbols=["MEGA"], title=title)
    out = IndexInclusion().evaluate(e, base_ctx())
    assert (out == ("index_inclusion", "P2")) is hit


def test_rvol_gap_gate_and_news_tag():
    r = RvolGateTriggers()
    e = make_event(kind="bar_trigger", symbols=["TINY"], meta={"trigger": "gap", "gap_pct": 12.0, "rvol": 2.5})
    assert r.evaluate(e, base_ctx()) == ("premarket_gap", "P1")
    ctx = base_ctx(news_tagged={"TINY": T0 - timedelta(hours=2)})
    assert r.evaluate(e, ctx) == ("premarket_gap", "P2")
    stale = base_ctx(news_tagged={"TINY": T0 - timedelta(hours=30)})
    assert r.evaluate(e, stale) == ("premarket_gap", "P1")
    e.meta["rvol"] = 1.5
    assert r.evaluate(e, ctx) is None
    e.meta.update(rvol=3.0, gap_pct=5.0)
    assert r.evaluate(e, ctx) is None


def test_rvol_gate_reads_settings():
    from swing_engine.core.config import MonitorConfig

    r = RvolGateTriggers()
    e = make_event(kind="bar_trigger", symbols=["TINY"], meta={"trigger": "gap", "gap_pct": 6.0, "rvol": 1.2, "news_tagged": True})
    assert r.evaluate(e, base_ctx()) is None
    assert r.evaluate(e, base_ctx(settings=MonitorConfig(rvol_gate=1.0, gap_pct_alert=5.0))) == ("premarket_gap", "P2")


def test_breakout_burst_adverse_peg():
    r = RvolGateTriggers()
    b = make_event(kind="bar_trigger", symbols=["ACME"], meta={"trigger": "breakout_52w", "rvol": 2.1, "vol_ratio": 1.6})
    assert r.evaluate(b, base_ctx()) == ("breakout_52w", "P2")
    b.meta["vol_ratio"] = 1.2
    assert r.evaluate(b, base_ctx()) is None
    burst = make_event(kind="bar_trigger", symbols=["ACME"], meta={"trigger": "burst", "close_ratio": 1.05, "volume": 200000, "prev_volume": 100000})
    assert r.evaluate(burst, base_ctx()) == ("stockbee_burst", "P0")
    burst.meta["volume"] = 50000
    assert r.evaluate(burst, base_ctx()) is None
    adv = make_event(kind="bar_trigger", symbols=["HELD"], meta={"trigger": "adverse_move", "pct": -6.0})
    assert r.evaluate(adv, base_ctx(held={"HELD"})) == ("adverse_move", "P3")
    assert r.evaluate(adv, base_ctx()) is None
    adv.meta["pct"] = -2.0
    assert r.evaluate(adv, base_ctx(held={"HELD"})) is None
    peg = make_event(kind="bar_trigger", symbols=["ACME"], meta={"trigger": "peg", "rvol": 3.5})
    assert r.evaluate(peg, base_ctx()) == ("peg_survivor", "P2")


def test_market_wide_suppression():
    r = MarketWideSuppression()
    news = make_event(kind="news", symbols=["ACME"], title="x")
    assert r.evaluate(news, base_ctx()) is None
    assert r.evaluate(news, base_ctx(market_suppressed=True, suppression_reason="fomc")) == (SUPPRESSED_HIT, "P0")
    assert news.meta["suppression_reason"] == "fomc"
    assert r.evaluate(news, base_ctx(held={"ACME"}, market_suppressed=True)) is None
    acct = make_event(kind="account", symbols=["ACME"], meta={"event": "fill"})
    assert r.evaluate(acct, base_ctx(market_suppressed=True)) is None
    mwc = make_event(kind="halt", symbols=["SPY"], meta={"reason_code": "MWC1"})
    assert r.evaluate(mwc, base_ctx()) == (CIRCUIT_BREAKER_HIT, "P2")


def test_account_events():
    r = AccountEvents()
    assert r.evaluate(make_event(kind="account", symbols=["X"], meta={"event": "rejected"}), base_ctx()) == ("order_rejected", "P3")
    assert r.evaluate(make_event(kind="account", symbols=["X"], meta={"event": "fill"}), base_ctx()) == ("order_fill", "P2")
    assert r.evaluate(make_event(kind="account", symbols=["X"], meta={"event": "new"}), base_ctx()) == ("order_new", "P1")
    assert r.evaluate(make_event(kind="news"), base_ctx()) is None


def test_rules_are_fast():
    import time

    rules = [registry.get("rule", n)() for n in EXPECTED_RULES]
    e = make_event(source="edgar", kind="filing", symbols=["ACME"], meta={"form_type": "8-K", "items": ["2.02"]})
    ctx = base_ctx(held={"ACME"})
    t = time.perf_counter()
    for _ in range(200):
        for r in rules:
            r.evaluate(e, ctx)
    per_event_ms = (time.perf_counter() - t) / 200 * 1000
    assert per_event_ms < 5.0  # all ten rules together, generous CI bound (<1 ms each in practice)
