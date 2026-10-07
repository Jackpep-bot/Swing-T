from __future__ import annotations

from datetime import timedelta

from swing_engine.core.models import Priority
from swing_engine.monitor.eventlog import EventLog
from tests.monitor_helpers import T0, make_event


def test_append_is_idempotent_on_event_id(tmp_path):
    log = EventLog(tmp_path / "events.sqlite")
    e = make_event("a1", symbols=["ACME"], title="hello")
    assert log.append(e) is True
    assert log.append(e) is False
    assert log.count() == 1
    assert log.contains("a1") and not log.contains("zz")


def test_wal_mode_on_disk(tmp_path):
    log = EventLog(tmp_path / "events.sqlite")
    mode = log._conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_roundtrip_and_update():
    log = EventLog(":memory:")
    e = make_event("a1", symbols=["ACME"], title="t", meta={"k": 1})
    log.append(e)
    e.priority = Priority.P2
    e.rule_hits = ["held_hit"]
    e.meta["x"] = "y"
    log.update(e)
    got = log.get("a1")
    assert got is not None
    assert got.priority == Priority.P2 and got.rule_hits == ["held_hit"] and got.meta == {"k": 1, "x": "y"}
    assert got.ts_source == T0 and got.symbols == ["ACME"]


def test_recent_window_and_source_filter():
    log = EventLog(":memory:")
    log.append(make_event("old", received=T0 - timedelta(hours=30)))
    log.append(make_event("new", received=T0 - timedelta(hours=1)))
    log.append(make_event("edgar1", source="edgar", kind="filing", received=T0 - timedelta(minutes=5)))
    ids = [e.event_id for e in log.recent(24, now=T0)]
    assert ids == ["new", "edgar1"]
    assert [e.event_id for e in log.recent(24, source="edgar", now=T0)] == ["edgar1"]


def test_cursors_upsert():
    log = EventLog(":memory:")
    assert log.cursor("edgar") is None
    log.set_cursor("edgar", "0001-26-000001")
    log.set_cursor("edgar", "0001-26-000002")
    assert log.cursor("edgar") == "0001-26-000002"


def test_alert_audit():
    log = EventLog(":memory:")
    log.record_alert("a1", "P2", ["telegram"], True, "p2_push")
    rows = log.recent_alerts(1)
    assert len(rows) == 1 and rows[0]["delivered"] == 1 and rows[0]["priority"] == "P2"
