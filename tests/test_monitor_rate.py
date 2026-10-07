from __future__ import annotations

from datetime import timedelta

import pytest

from swing_engine.core.config import Settings
from swing_engine.core.models import Event, Priority
from swing_engine.monitor import outcomes
from swing_engine.monitor.eventlog import EventLog
from swing_engine.monitor.rate import (
    RATINGS_TABLE,
    AlertRating,
    callback_data,
    parse_callback_data,
    parse_rating,
    rate_alert,
    rate_cli,
    ratings_history,
)
from tests.monitor_helpers import T0, make_event


class FakeEventLog:
    """Minimal RatableLog: get/update only (no SQLite, so no history table)."""

    def __init__(self, events: list[Event] | None = None):
        self.events = {e.event_id: e for e in (events or [])}
        self.updates: list[str] = []

    def get(self, event_id: str) -> Event | None:
        ev = self.events.get(event_id)
        return ev.model_copy(deep=True) if ev is not None else None

    def update(self, event: Event) -> None:
        self.updates.append(event.event_id)
        self.events[event.event_id] = event


def test_parse_rating_accepts_enum_values_only():
    assert parse_rating(" Useful ") is AlertRating.USEFUL
    assert parse_rating(AlertRating.TRADED) is AlertRating.TRADED
    with pytest.raises(ValueError, match="rating must be one of"):
        parse_rating("great")


def test_callback_data_round_trip_and_limits():
    data = callback_data(AlertRating.NOISE, "alpaca_news:12345")
    assert data == "noise:alpaca_news:12345"
    assert parse_callback_data(data) == (AlertRating.NOISE, "alpaca_news:12345")
    assert callback_data(AlertRating.USEFUL, "x" * 80) is None  # > 64 bytes: no button
    assert callback_data(AlertRating.USEFUL, "") is None
    for bad in (None, "", "useful", "great:e1", "useful:"):
        assert parse_callback_data(bad) is None


def test_rate_alert_on_fake_log_writes_meta():
    fake = FakeEventLog([make_event("e1", symbols=["ABC"], title="ABC news", priority=Priority.P2)])
    res = rate_alert(fake, "e1", "useful", "telegram", now=T0)
    assert res.ok and res.rating is AlertRating.USEFUL and res.symbols == ["ABC"] and not res.history_recorded
    meta = fake.events["e1"].meta
    assert meta["rating"] == "useful" and meta["rating_source"] == "telegram" and meta["rated_at"].startswith("2026-10-06")
    again = rate_alert(fake, "e1", AlertRating.NOISE, "cli", now=T0)
    assert again.ok and again.previous == "useful" and fake.events["e1"].meta["rating"] == "noise"
    assert "was useful" in again.summary()


def test_rate_alert_unknown_event_and_invalid_rating():
    fake = FakeEventLog()
    res = rate_alert(fake, "missing", "noise", "cli")
    assert not res.ok and res.reason == "unknown_event" and fake.updates == []
    assert "not rated" in res.summary()
    with pytest.raises(ValueError):
        rate_alert(fake, "missing", "meh", "cli")


def test_rate_alert_survives_a_broken_log():
    class Broken(FakeEventLog):
        def get(self, event_id):
            raise RuntimeError("disk gone")

    res = rate_alert(Broken(), "e1", "noise", "cli")
    assert not res.ok and res.reason == "eventlog_failed"


def test_rate_alert_persists_in_real_eventlog_with_history(tmp_path):
    path = tmp_path / "events.sqlite"
    elog = EventLog(path)
    elog.append(make_event("e1", symbols=["ABC"], priority=Priority.P2))
    assert rate_alert(elog, "e1", "useful", "telegram").history_recorded
    assert rate_alert(elog, "e1", "traded", "cli").ok
    elog.close()
    reopened = EventLog(path)
    assert reopened.get("e1").meta["rating"] == "traded"
    rows = ratings_history(reopened, "e1")
    assert [(r["rating"], r["source"]) for r in rows] == [("useful", "telegram"), ("traded", "cli")]
    assert ratings_history(reopened, "other") == []
    tables = {r[0] for r in reopened._conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert RATINGS_TABLE in tables
    reopened.close()


def test_ratings_history_on_fake_log_is_empty():
    assert ratings_history(FakeEventLog()) == []


def test_outcomes_pick_up_the_rating(tmp_path):
    elog = EventLog(":memory:")
    ev = make_event("e1", symbols=["ABC"], ts=T0, priority=Priority.P2)
    elog.append(ev)
    rate_alert(elog, "e1", "useful", "telegram")
    rows = outcomes._alert_rows(elog, 1.0, T0 + timedelta(hours=1))
    assert rows and rows[0]["rating"] == "useful"


def test_rate_cli_opens_the_configured_log(tmp_path):
    path = tmp_path / "events.sqlite"
    elog = EventLog(path)
    elog.append(make_event("e9", symbols=["XYZ"], priority=Priority.P3))
    elog.close()
    settings = Settings.model_validate({"data": {"event_log_path": str(path)}})
    res = rate_cli(settings, " e9 ", "Noise")
    assert res.ok and res.source == "cli" and res.rating is AlertRating.NOISE
    check = EventLog(path)
    assert check.get("e9").meta["rating"] == "noise"
    check.close()
    assert not rate_cli(settings, "nope", "noise").ok
    with pytest.raises(ValueError):
        rate_cli(settings, "e9", "bogus")


def test_rate_cli_accepts_an_injected_log():
    fake = FakeEventLog([make_event("e1", symbols=["ABC"])])
    res = rate_cli(Settings(), "e1", "traded", eventlog=fake)
    assert res.ok and fake.events["e1"].meta["rating"] == "traded"
