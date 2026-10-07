from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from swing_engine.core.config import Secrets, Settings
from swing_engine.core.models import Event, Priority
from swing_engine.monitor import replay as replay_mod
from swing_engine.monitor import report as report_mod
from swing_engine.monitor import service as service_mod
from swing_engine.monitor.adapters.file_feed import FileFeed, read_events
from swing_engine.monitor.delivery.console import ConsoleDeliverer
from swing_engine.monitor.eventlog import EventLog
from swing_engine.monitor.hours import is_market_hours, minute_of_session, session_phase
from swing_engine.monitor.service import MonitorService, OpsRule, build_feeds, build_pipeline
from tests.monitor_helpers import FIXTURES, T0, make_event

MARKET_OPEN_TS = datetime(2026, 10, 6, 14, 0, tzinfo=UTC)  # Tue 10:00 ET
WEEKEND_TS = datetime(2026, 10, 4, 14, 0, tzinfo=UTC)


def test_market_hours_helpers():
    assert session_phase(MARKET_OPEN_TS) == "regular" and is_market_hours(MARKET_OPEN_TS)
    assert session_phase(WEEKEND_TS) == "closed" and not is_market_hours(WEEKEND_TS)
    assert session_phase(datetime(2026, 10, 6, 11, 0, tzinfo=UTC)) == "premarket"
    assert session_phase(datetime(2026, 10, 6, 22, 0, tzinfo=UTC)) == "afterhours"
    assert not is_market_hours(datetime(2026, 10, 6, 22, 0, tzinfo=UTC), extended=False)
    assert session_phase(datetime(2026, 11, 26, 15, 0, tzinfo=UTC)) == "closed"  # Thanksgiving
    assert minute_of_session(MARKET_OPEN_TS) == 30


def test_build_pipeline_dry_run_uses_console_only_and_no_classifier():
    s = Settings()
    s.monitor.watchlist = ["ACME"]
    sec = Secrets(anthropic_api_key="sk-test", telegram_bot_token="t", telegram_chat_id="c", _env_file=None)
    p = build_pipeline(s, sec, dry_run=True)
    assert list(p.deliverers) == ["console"] and p.classifier is None and p.eventlog.path == ":memory:"
    assert p.ctx["watchlist"] == {"ACME"} and p.matcher is not None and p.smallcap is not None
    assert any(isinstance(r, OpsRule) for r in p.rules)
    live = build_pipeline(s, sec, dry_run=False, deliverers=[ConsoleDeliverer()])
    assert live.classifier is not None and live.classifier.model == "claude-haiku-4-5" and live.audit_path is not None
    live.eventlog.close()
    feeds = build_feeds(s, sec, dry_run=True)
    assert len(feeds) == 1 and isinstance(feeds[0], FileFeed)


async def test_service_dry_run_processes_file_feed_and_stops():
    out: list[str] = []
    s = Settings()
    s.monitor.watchlist = ["MEGA"]
    p = build_pipeline(s, Secrets(_env_file=None), dry_run=True, deliverers=[ConsoleDeliverer(printer=out.append)])
    p.ctx["held"] = {"HELD"}
    feed = FileFeed(FIXTURES / "replay_events.jsonl", rebase_received=True)
    svc = MonitorService([feed], p, stop_when_feeds_end=True, watchdog_interval_s=0.01)
    await asyncio.wait_for(svc.run(), timeout=5)
    assert svc.processed == 8 and p.stats["received"] == 8
    assert p.stats["dropped"] == 1  # the UPDATE reprint of the S&P headline
    assert any("[P3] P3 $HELD" in line for line in out)  # order rejection on a holding
    assert any("[P2] P2 $MEGA" in line for line in out)  # index inclusion on the watchlist


async def test_staleness_watchdog_is_market_hours_aware():
    clock_t = [MARKET_OPEN_TS]
    p = build_pipeline(Settings(), Secrets(_env_file=None), dry_run=True)

    class Named(FileFeed):
        name = "alpaca_news"

    svc = MonitorService([Named(events=[])], p, clock=lambda: clock_t[0], staleness={"alpaca_news": 60})
    assert await svc.check_staleness() == []  # just started, inside grace
    clock_t[0] = MARKET_OPEN_TS + timedelta(seconds=61)
    assert await svc.check_staleness() == ["alpaca_news"]
    ev = svc._queue.get_nowait()
    assert ev.kind == "ops" and ev.priority == Priority.P3 and ev.meta["what"] == "feed_dead"
    assert await svc.check_staleness() == ["alpaca_news"] and svc._queue.empty()  # alerted once
    svc.last_seen["alpaca_news"] = clock_t[0]
    assert await svc.check_staleness() == []
    clock_t[0] = WEEKEND_TS + timedelta(days=0)
    svc.last_seen.clear()
    assert await svc.check_staleness() == []  # closed market: silence is fine
    res = await p.process(ev)
    assert res.priority == "P3" and res.event.rule_hits == ["feed_dead"]
    p.eventlog.close()


async def test_service_stop_is_graceful():
    p = build_pipeline(Settings(), Secrets(_env_file=None), dry_run=True)
    feed = FileFeed(events=[make_event("a", symbols=["X"], title="t")])
    svc = MonitorService([feed], p, watchdog_interval_s=0.01)
    task = asyncio.create_task(svc.run())
    await asyncio.sleep(0.05)
    svc.stop()
    await asyncio.wait_for(task, timeout=5)
    assert svc.processed == 1


def _seed_log() -> EventLog:
    log = EventLog(":memory:")
    for e in read_events(FIXTURES / "replay_events.jsonl"):
        log.append(e)
    doom = log.get("edgar:0007654321-26-000044")
    doom.priority = Priority.P3
    doom.rule_hits = ["held_hit", "8k:4.02", "haiku:fallback"]
    log.update(doom)
    log.record_alert(doom.event_id, "P3", ["pushover", "telegram"], True, "p3_emergency")
    return log


def test_report_counts():
    log = _seed_log()
    now = datetime(2026, 10, 7, 0, 0, tzinfo=UTC)
    r = report_mod.report(1, eventlog=log, now=now)
    assert r["events"] == 8 and r["by_source"]["alpaca_news"] == 3 and r["by_kind"]["halt"] == 2
    assert r["by_priority"]["P3"] == 1 and r["alerts_delivered"] == 1 and r["alert_channels"] == {"pushover": 1, "telegram": 1}
    assert ("held_hit", 1) in r["top_rules"] and r["notable"][0]["symbols"] == ["DOOM"]
    text = report_mod.format_report(r)
    assert "8 events" in text and "P3" in text and "DOOM" in text


def test_replay_reruns_rules_and_flags_changes():
    log = _seed_log()
    now = datetime(2026, 10, 7, 0, 0, tzinfo=UTC)
    r = replay_mod.replay(1, eventlog=log, ctx={"held": {"DOOM"}}, now=now)
    assert r["events"] == 8 and "eightk_items" in r["rules"]
    rows = {row["event_id"]: row for row in r["rows"]}
    doom = rows["edgar:0007654321-26-000044"]
    assert doom["replay_priority"] == "P3" and doom["changed"] is False and sorted(doom["stored_hits"]) == ["8k:4.02", "held_hit"]
    scam = rows["nasdaq_halts:scam-t12"]
    assert scam["replay_priority"] == "P2" and scam["changed"] is True  # stored as P0 (never run through rules)
    assert rows["alpaca_news:41234569"]["replay_hits"] == ["index_inclusion"]
    subset = replay_mod.replay(1, rules=["halts_luld"], eventlog=log, now=now)
    assert subset["rules"] == ["halts_luld"] and rows["alpaca_news:41234569"]["replay_hits"]
    assert "->" in replay_mod.format_replay(r)


def test_ops_rule_passthrough():
    e = Event(event_id="x", source="monitor", kind="ops", ts_source=T0, ts_received=T0, meta={"what": "kill_switch"}, priority=Priority.P3)
    assert OpsRule().evaluate(e, {}) == ("kill_switch", "P3")
    assert OpsRule().evaluate(make_event(), {}) is None


def test_run_monitor_signature_matches_contract():
    import inspect

    params = list(inspect.signature(service_mod.run_monitor).parameters)
    assert params == ["settings", "secrets", "dry_run", "feeds"]
