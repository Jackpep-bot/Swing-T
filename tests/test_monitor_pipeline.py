from __future__ import annotations

import asyncio
import json
from datetime import timedelta

from swing_engine.core.models import Classification, Event, Priority
from swing_engine.monitor.alerts import AlertPolicy
from swing_engine.monitor.delivery.console import ConsoleDeliverer
from swing_engine.monitor.eventlog import EventLog
from swing_engine.monitor.matcher import Matcher
from swing_engine.monitor.pipeline import Pipeline
from swing_engine.monitor.replay import load_rules
from swing_engine.monitor.service import OpsRule
from swing_engine.monitor.smallcap import SmallCapTrack
from tests.monitor_helpers import T0, make_event


class FakeClassifier:
    def __init__(self, result: Classification | None = None, raise_exc: bool = False):
        self.result = result
        self.raise_exc = raise_exc
        self.seen: list[str] = []

    async def classify(self, event, ctx=None):
        self.seen.append(event.event_id)
        if self.raise_exc:
            raise RuntimeError("boom")
        return self.result


class RecordingDeliverer(ConsoleDeliverer):
    def __init__(self, name: str, ok: bool = True):
        super().__init__(printer=lambda s: None)
        self.name = name
        self.ok = ok

    async def send(self, title, body, priority, meta=None):
        self.sent.append((title, body, priority))
        return self.ok


def make_pipeline(tmp_path=None, classifier=None, held=None, watch=None, matcher=None, smallcap=None, **policy_kw):
    tg, po, co = RecordingDeliverer("telegram"), RecordingDeliverer("pushover"), RecordingDeliverer("console")
    p = Pipeline(
        rules=load_rules(),
        classifier=classifier,
        policy=AlertPolicy(clock=lambda: T0, **policy_kw),
        deliverers=[tg, po, co],
        eventlog=EventLog(":memory:"),
        matcher=matcher,
        ctx={"held": held or set(), "watchlist": watch or set()},
        audit_path=(tmp_path / "alerts.jsonl") if tmp_path else None,
        smallcap=smallcap,
    )
    return p, tg, po, co


async def test_held_8k_severe_goes_p3_to_pushover_and_telegram(tmp_path):
    p, tg, po, co = make_pipeline(tmp_path, held={"DOOM"})
    e = make_event("f1", source="edgar", kind="filing", symbols=["doom"], title="8-K DOOMED", meta={"form_type": "8-K", "items": ["4.02", "9.01"]})
    res = await p.process(e)
    assert not res.dropped and res.priority == "P3"
    assert set(res.event.rule_hits) == {"held_hit", "8k:4.02"}
    assert res.delivered == ["pushover", "telegram", "console"]
    assert len(po.sent) == 1 and po.sent[0][2] == "P3" and "$DOOM" in po.sent[0][0]
    assert p.eventlog.get("f1").priority == Priority.P3
    rows = [json.loads(line) for line in (tmp_path / "alerts.jsonl").read_text().splitlines()]
    assert rows[0]["event_id"] == "f1" and rows[0]["delivered"] == ["pushover", "telegram", "console"]
    assert p.stats == {
        "received": 1, "dropped": 0, "classified": 0, "delivered": 1, "halts_logged": 0, "halt_log_errors": 0,
        "smallcap_alerts": 0,
    }


async def test_duplicates_are_dropped_before_rules():
    p, tg, _, _ = make_pipeline(held={"ACME"})
    e1 = make_event("n1", symbols=["ACME"], title="Acme beats estimates and raises guidance")
    e2 = make_event("n2", source="edgar", symbols=["ACME"], title="UPDATE: Acme beats estimates and raises guidance")
    assert not (await p.process(e1)).dropped
    r2 = await p.process(e2)
    assert r2.dropped and r2.drop_reason.startswith("near_duplicate")
    r3 = await p.process(make_event("n1", symbols=["ACME"], title="Acme beats estimates and raises guidance"))
    assert r3.dropped and r3.drop_reason.startswith("duplicate_id")
    assert p.eventlog.count() == 1 and len(tg.sent) == 1


async def test_matcher_adds_symbols_and_keywords():
    m = Matcher(tickers=["ACME"], aliases={"ACME": ["Acme Corp"]}, keywords=["offering"])
    p, tg, _, _ = make_pipeline(watch={"ACME"}, matcher=m)
    res = await p.process(make_event("n1", symbols=[], title="Acme Corp prices offering"))
    assert res.event.symbols == ["ACME"] and res.event.meta["keywords"] == ["offering"]
    assert "watchlist_hit" in res.event.rule_hits and res.priority == "P1"
    assert res.decision is not None and res.decision.digest and p.policy.digest_size == 1


async def test_classifier_can_drop_noise_but_never_touches_held_or_p3():
    noise = Classification(relevance="none", event_type="other", materiality=1, sentiment="neutral", tickers=[], rationale="roundup", suggested_action="ignore")
    clf = FakeClassifier(noise)
    p, tg, po, _ = make_pipeline(classifier=clf, watch={"ACME"}, held={"HELD"})
    r = await p.process(make_event("n1", symbols=["ACME"], title="Top movers: ACME"))
    assert r.priority == "P0" and "haiku:none" in r.event.rule_hits and r.decision.deliver is False
    r2 = await p.process(make_event("n2", symbols=["HELD"], title="Held co roundup"))
    assert r2.priority == "P2" and r2.delivered == ["telegram", "console"]
    r3 = await p.process(make_event("h1", kind="halt", symbols=["HELD"], meta={"reason_code": "T1"}))
    assert r3.priority == "P3" and "h1" not in clf.seen  # P3 never waits on the LLM
    assert r3.event.meta.get("classification") is None


async def test_classifier_upgrade_and_fallback():
    strong = Classification(relevance="high", event_type="earnings", materiality=5, sentiment="positive", tickers=["ACME"], rationale="beat", suggested_action="review")
    p, tg, _, _ = make_pipeline(classifier=FakeClassifier(strong), watch={"ACME"})
    r = await p.process(make_event("n1", symbols=["ACME"], title="Acme beats"))
    assert r.priority == "P2" and "haiku:upgrade" in r.event.rule_hits and r.event.meta["classification"]["event_type"] == "earnings"
    assert "haiku=earnings/high/m5" in tg.sent[0][1]
    p2, _, _, _ = make_pipeline(classifier=FakeClassifier(None), watch={"ACME"})
    r2 = await p2.process(make_event("n2", symbols=["ACME"], title="Acme beats"))
    assert r2.priority == "P1" and "haiku:fallback" in r2.event.rule_hits
    p3, _, _, _ = make_pipeline(classifier=FakeClassifier(raise_exc=True), watch={"ACME"})
    r3 = await p3.process(make_event("n3", symbols=["ACME"], title="Acme beats"))
    assert r3.priority == "P1" and r3.classification is None


async def test_market_wide_circuit_breaker_sets_suppression():
    p, tg, _, _ = make_pipeline(watch={"ACME"}, held={"HELD"})
    r = await p.process(make_event("m1", kind="halt", symbols=["SPY"], meta={"reason_code": "MWC1"}))
    assert r.priority == "P2" and p.ctx["market_suppressed"] is True
    r2 = await p.process(make_event("n1", kind="news", symbols=["ACME"], title="Acme set to join S&P 500"))
    assert r2.priority == "P0" and "market_wide_suppressed" in r2.event.rule_hits and "index_inclusion" in r2.event.rule_hits
    r3 = await p.process(make_event("n2", kind="news", symbols=["HELD"], title="Held co news"))
    assert r3.priority == "P2"


async def test_market_wide_suppression_expires_with_the_session_and_spares_ops_events():
    p, tg, po, _ = make_pipeline(watch={"ACME"})
    p.rules.append(OpsRule())
    await p.process(make_event("m1", kind="halt", symbols=["SPY"], meta={"reason_code": "MWC1"}))
    assert p.ctx["market_suppressed"] is True and p.ctx["market_suppressed_until"] > T0
    ops = Event(event_id="o1", source="monitor", kind="ops", ts_source=T0, ts_received=T0, title="feed_dead: edgar",
                meta={"what": "feed_dead"}, priority=Priority.P3, rule_hits=["feed_dead"])
    r_ops = await p.process(ops)
    assert r_ops.priority == "P3" and "pushover" in r_ops.delivered
    assert "market_wide_suppressed" not in r_ops.event.rule_hits and po.sent  # the watchdog alert went out
    same_day = T0 + timedelta(hours=2)
    r_same = await p.process(make_event("n1", symbols=["ACME"], title="Acme set to join S&P 500", ts=same_day, received=same_day))
    assert r_same.priority == "P0"
    next_day = T0 + timedelta(days=1)
    r_next = await p.process(make_event("n2", symbols=["ACME"], title="Acme to replace Zeta in the S&P 500", ts=next_day, received=next_day))
    assert r_next.priority == "P2" and p.ctx["market_suppressed"] is False and "market_suppressed_until" not in p.ctx


async def test_account_fills_update_held_positions():
    p, tg, po, _ = make_pipeline(held={"OLD"})
    fill = make_event("a1", source="alpaca_account", kind="account", symbols=["NEWP"], title="NEWP order fill buy 10",
                      meta={"event": "fill", "position_qty": "10"})
    await p.process(fill)
    assert p.ctx["held"] == {"OLD", "NEWP"}
    flat = make_event("a2", source="alpaca_account", kind="account", symbols=["OLD"], title="OLD order fill sell 5",
                      meta={"event": "fill", "position_qty": 0})
    await p.process(flat)
    assert p.ctx["held"] == {"NEWP"}
    await p.process(make_event("a3", source="alpaca_account", kind="account", symbols=["NEWP"], title="x", meta={"event": "new"}))
    assert p.ctx["held"] == {"NEWP"}  # no position_qty: unchanged
    r = await p.process(make_event("h1", kind="halt", symbols=["NEWP"], meta={"reason_code": "T1"}))
    assert r.priority == "P3" and po.sent[-1][2] == "P3"


async def test_p3_delivery_runs_channels_concurrently():
    class Slow(RecordingDeliverer):
        async def send(self, title, body, priority, meta=None):
            await asyncio.sleep(0.2)
            return await super().send(title, body, priority, meta)

    tg, po, co = Slow("telegram"), Slow("pushover"), Slow("console")
    p = Pipeline(rules=load_rules(), policy=AlertPolicy(clock=lambda: T0), deliverers=[tg, po, co],
                 eventlog=EventLog(":memory:"), ctx={"held": {"HELD"}})
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    r = await p.process(make_event("h1", kind="halt", symbols=["HELD"], meta={"reason_code": "T1"}))
    elapsed = loop.time() - t0
    assert r.delivered == ["pushover", "telegram", "console"] and elapsed < 0.5  # three sends, one wait


async def test_prepare_and_finish_split():
    p, tg, _, _ = make_pipeline(held={"ACME"})
    res = p.prepare(make_event("n1", symbols=["ACME"], title="Acme beats"))
    assert not res.dropped and res.priority == "P2" and res.decision is None and tg.sent == []
    assert p.eventlog.get("n1").priority == Priority.P2  # rules already logged before the slow half runs
    await p.finish(res)
    assert res.decision is not None and res.delivered == ["telegram", "console"]
    assert p.prepare(make_event("n1", symbols=["ACME"], title="Acme beats")).dropped


async def test_rule_exception_is_isolated():
    class Bad:
        name = "bad"

        def evaluate(self, event, ctx):
            raise ValueError("nope")

    p, tg, _, _ = make_pipeline(held={"ACME"})
    p.rules.insert(0, Bad())
    r = await p.process(make_event("n1", symbols=["ACME"], title="x"))
    assert r.priority == "P2" and r.event.rule_hits == ["held_hit"]


async def test_delivery_failure_records_other_channels():
    p, tg, po, co = make_pipeline(held={"ACME"})
    tg.ok = False
    r = await p.process(make_event("h1", kind="halt", symbols=["ACME"], meta={"reason_code": "T12"}))
    assert r.delivered == ["pushover", "console"]
    audit = p.eventlog.recent_alerts(1)
    assert audit and json.loads(audit[0]["channels"]) == ["pushover", "console"]


async def test_digest_flush_uses_first_available_channel():
    p, tg, _, co = make_pipeline(watch={"ACME"})
    await p.process(make_event("n1", symbols=["ACME"], title="Acme digest-worthy"))
    assert await p.flush_digest_if_due(force=True) is True
    assert len(tg.sent) == 1 and tg.sent[0][2] == "P1" and "Acme digest-worthy" in tg.sent[0][1]
    assert await p.flush_digest_if_due(force=True) is False


async def test_smallcap_observe_hook_records_session_state():
    sc = SmallCapTrack({})
    p, _, _, _ = make_pipeline(smallcap=sc)
    await p.process(make_event("h1", kind="halt", symbols=["SCAM"], meta={"reason_code": "T12"}))
    await p.process(make_event("f1", source="edgar", kind="filing", symbols=["TINY"], title="424B5", meta={"form_type": "424B5"}))
    assert "SCAM" in sc.blocklist and sc.session_state("TINY")["dilution"] is True
