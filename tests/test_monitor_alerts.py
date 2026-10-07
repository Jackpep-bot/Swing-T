from __future__ import annotations

from datetime import UTC, datetime, timedelta

from swing_engine.core.models import Priority
from swing_engine.monitor.alerts import AlertPolicy
from tests.monitor_helpers import make_event


class Clock:
    def __init__(self, t: datetime):
        self.t = t

    def __call__(self) -> datetime:
        return self.t

    def tick(self, **kw) -> None:
        self.t += timedelta(**kw)


DAY = datetime(2026, 10, 6, 15, 0, tzinfo=UTC)  # 11:00 ET
NIGHT = datetime(2026, 10, 7, 3, 0, tzinfo=UTC)  # 23:00 ET


def policy(t=DAY, **kw) -> tuple[AlertPolicy, Clock]:
    c = Clock(t)
    return AlertPolicy(clock=c, **kw), c


def test_priority_routing():
    p, _ = policy()
    assert p.decide(make_event("a", priority=Priority.P0)).deliver is False
    d1 = p.decide(make_event("b", symbols=["A"], priority=Priority.P1))
    assert d1.deliver is False and d1.digest is True and p.digest_size == 1
    d2 = p.decide(make_event("c", symbols=["B"], priority=Priority.P2))
    assert d2.deliver is True and d2.channels == ["telegram", "console"]
    d3 = p.decide(make_event("d", symbols=["C"], priority=Priority.P3))
    assert d3.deliver is True and d3.channels == ["pushover", "telegram", "console"]


def test_cooldown_per_ticker_then_digest():
    p, c = policy(cooldown_min=15)
    assert p.decide(make_event("a", symbols=["ACME"], priority=Priority.P2)).deliver
    d = p.decide(make_event("b", symbols=["ACME"], priority=Priority.P2))
    assert not d.deliver and d.reason.startswith("cooldown") and d.digest
    assert p.decide(make_event("c", symbols=["OTHER"], priority=Priority.P2)).deliver
    c.tick(minutes=16)
    assert p.decide(make_event("d", symbols=["ACME"], priority=Priority.P2)).deliver


def test_cooldown_applies_to_every_symbol_on_the_event():
    p, c = policy(cooldown_min=15)
    assert p.decide(make_event("a", symbols=["ACME", "ZETA"], priority=Priority.P2)).deliver
    d = p.decide(make_event("b", symbols=["ZETA"], priority=Priority.P2))  # the reprint tagged with the other name
    assert not d.deliver and d.reason == "cooldown:ZETA" and d.digest
    assert p.decide(make_event("c", symbols=["OTHR"], priority=Priority.P2)).deliver
    c.tick(minutes=16)
    assert p.decide(make_event("d", symbols=["ZETA", "ACME"], priority=Priority.P2)).deliver


def test_p3_bypasses_cooldown_and_quiet_hours():
    p, _ = policy(t=NIGHT)
    assert p.decide(make_event("a", symbols=["ACME"], priority=Priority.P3)).deliver
    assert p.decide(make_event("b", symbols=["ACME"], priority=Priority.P3)).deliver


def test_hourly_cap():
    p, c = policy(hourly_cap=3)
    for i in range(3):
        assert p.decide(make_event(f"a{i}", symbols=[f"S{i}"], priority=Priority.P2)).deliver
    d = p.decide(make_event("x", symbols=["S9"], priority=Priority.P2))
    assert not d.deliver and d.reason == "hourly_cap"
    c.tick(minutes=61)
    assert p.decide(make_event("y", symbols=["S8"], priority=Priority.P2)).deliver


def test_quiet_hours_unless_held():
    p, _ = policy(t=NIGHT, quiet_hours_et=(22, 6))
    assert p.in_quiet_hours()
    d = p.decide(make_event("a", symbols=["ACME"], priority=Priority.P2))
    assert not d.deliver and d.reason == "quiet_hours"
    assert p.decide(make_event("b", symbols=["ACME"], priority=Priority.P2), {"held": {"ACME"}}).deliver
    p2, _ = policy(t=DAY, quiet_hours_et=(22, 6))
    assert not p2.in_quiet_hours()


def test_digest_schedule_and_flush():
    p, c = policy(t=datetime(2026, 10, 6, 12, 0, tzinfo=UTC))  # 08:00 ET
    assert not p.digest_due()
    p.decide(make_event("a", symbols=["ACME"], title="hello", priority=Priority.P1))
    c.tick(minutes=31)  # 08:31 ET
    assert p.digest_due()
    msg = p.flush_digest()
    assert msg is not None and "1 items" in msg[0] and "ACME" in msg[1]
    assert not p.digest_due()
    assert p.flush_digest() is None
    c.tick(hours=7, minutes=20)  # 15:51 ET
    assert p.digest_due()


def test_format_includes_classification():
    e = make_event("a", symbols=["ACME"], title="Beats", priority=Priority.P2)
    e.rule_hits = ["held_hit"]
    e.meta["classification"] = {"event_type": "earnings", "relevance": "high", "materiality": 4,
                                "suggested_action": "review", "rationale": "beat"}
    title, body = AlertPolicy.format(e)
    assert title.startswith("P2 $ACME: Beats")
    assert "rules=held_hit" in body and "haiku=earnings/high/m4 review: beat" in body
