from __future__ import annotations

import asyncio
import json
from datetime import UTC, date, datetime, time, timedelta

from swing_engine.core.config import Secrets, Settings
from swing_engine.core.models import Event, Priority
from swing_engine.monitor import replay as replay_mod
from swing_engine.monitor import report as report_mod
from swing_engine.monitor import service as service_mod
from swing_engine.monitor.adapters.file_feed import FileFeed, read_events
from swing_engine.monitor.alerts import AlertPolicy
from swing_engine.monitor.delivery.console import ConsoleDeliverer
from swing_engine.monitor.eventlog import EventLog
from swing_engine.monitor.hours import (
    ET,
    is_early_close,
    is_market_hours,
    minute_of_session,
    session_bounds,
    session_end,
    session_phase,
)
from swing_engine.monitor.pipeline import Pipeline
from swing_engine.monitor.replay import load_rules
from swing_engine.monitor.service import (
    MonitorService,
    OpsRule,
    build_feeds,
    build_pipeline,
    load_held_symbols,
)
from tests.monitor_helpers import FIXTURES, T0, make_event

MARKET_OPEN_TS = datetime(2026, 10, 6, 14, 0, tzinfo=UTC)  # Tue 10:00 ET
WEEKEND_TS = datetime(2026, 10, 4, 14, 0, tzinfo=UTC)
BLACK_FRIDAY = date(2026, 11, 27)  # 13:00 ET close


class Recorder(ConsoleDeliverer):
    def __init__(self, name: str, delay_s: float = 0.0):
        super().__init__(printer=lambda s: None)
        self.name = name
        self.delay_s = delay_s
        self.sent: list[tuple[str, str]] = []

    async def send(self, title, body, priority, meta=None):
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        self.sent.append((title, priority))
        return True


class GatedClassifier:
    """Blocks every classify() call until `gate` is set (a slow Haiku backlog)."""

    def __init__(self):
        self.gate = asyncio.Event()
        self.started = 0
        self.finished = 0

    async def classify(self, event, ctx=None):
        self.started += 1
        await self.gate.wait()
        self.finished += 1
        return None


def _pipeline(deliverers, classifier=None, held=("HELD",), watch=("ACME",)) -> Pipeline:
    return Pipeline(
        rules=[*load_rules(), OpsRule()],
        classifier=classifier,
        policy=AlertPolicy(clock=lambda: T0),
        deliverers=deliverers,
        eventlog=EventLog(":memory:"),
        ctx={"held": set(held), "watchlist": set(watch)},
    )


def test_market_hours_helpers():
    assert session_phase(MARKET_OPEN_TS) == "regular" and is_market_hours(MARKET_OPEN_TS)
    assert session_phase(WEEKEND_TS) == "closed" and not is_market_hours(WEEKEND_TS)
    assert session_phase(datetime(2026, 10, 6, 11, 0, tzinfo=UTC)) == "premarket"
    assert session_phase(datetime(2026, 10, 6, 22, 0, tzinfo=UTC)) == "afterhours"
    assert not is_market_hours(datetime(2026, 10, 6, 22, 0, tzinfo=UTC), extended=False)
    assert session_phase(datetime(2026, 11, 26, 15, 0, tzinfo=UTC)) == "closed"  # Thanksgiving
    assert minute_of_session(MARKET_OPEN_TS) == 30


def test_early_close_sessions():
    assert is_early_close(BLACK_FRIDAY) and session_bounds(BLACK_FRIDAY) == (time(13, 0), time(17, 0))
    assert session_bounds(date(2026, 10, 6)) == (time(16, 0), time(20, 0))
    assert session_phase(datetime(2026, 11, 27, 17, 0, tzinfo=UTC)) == "regular"  # 12:00 ET
    assert session_phase(datetime(2026, 11, 27, 19, 0, tzinfo=UTC)) == "afterhours"  # 14:00 ET: regular session over
    assert session_phase(datetime(2026, 11, 27, 23, 0, tzinfo=UTC)) == "closed"  # 18:00 ET: extended hours over
    assert not is_market_hours(datetime(2026, 11, 27, 23, 0, tzinfo=UTC))
    assert minute_of_session(datetime(2026, 11, 27, 19, 0, tzinfo=UTC)) == 210
    assert session_end(datetime(2026, 11, 27, 15, 0, tzinfo=UTC)) == datetime(2026, 11, 27, 17, 0, tzinfo=ET)
    assert session_end(MARKET_OPEN_TS).astimezone(UTC) == datetime(2026, 10, 7, 0, 0, tzinfo=UTC)  # 20:00 EDT


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


async def test_staleness_judges_transport_liveness_not_emitted_events():
    clock_t = [MARKET_OPEN_TS]
    p = build_pipeline(Settings(), Secrets(_env_file=None), dry_run=True)

    class Quiet(FileFeed):  # a healthy socket that has had nothing worth emitting
        name = "alpaca_news"
        last_activity_at: datetime | None = None

    feed = Quiet(events=[])
    svc = MonitorService([feed], p, clock=lambda: clock_t[0], staleness={"alpaca_news": 60})
    clock_t[0] = MARKET_OPEN_TS + timedelta(seconds=61)
    feed.last_activity_at = clock_t[0] - timedelta(seconds=5)  # frames keep arriving
    assert await svc.check_staleness() == [] and svc._queue.empty()
    clock_t[0] += timedelta(seconds=120)  # now the transport itself has gone quiet
    assert await svc.check_staleness() == ["alpaca_news"]
    p.eventlog.close()


async def test_staleness_windows_follow_each_feeds_hours():
    class Stocks(FileFeed):
        name = "alpaca_stocks"

    class Edgar(FileFeed):
        name = "edgar"

    premarket = datetime(2026, 10, 6, 8, 30, tzinfo=UTC)  # 04:30 ET
    clock_t = [premarket - timedelta(hours=3)]
    p = build_pipeline(Settings(), Secrets(_env_file=None), dry_run=True)
    svc = MonitorService([Stocks(events=[]), Edgar(events=[])], p, clock=lambda: clock_t[0],
                         staleness={"alpaca_stocks": 120, "edgar": 600})
    clock_t[0] = premarket  # both silent for hours, but neither can have data yet: no 4 AM emergency
    assert await svc.check_staleness() == []
    clock_t[0] = datetime(2026, 10, 6, 11, 0, tzinfo=UTC)  # 07:00 ET: EDGAR accepts filings, the market is shut
    assert await svc.check_staleness() == ["edgar"]
    clock_t[0] = MARKET_OPEN_TS  # 10:00 ET: both are expected to be alive
    assert await svc.check_staleness() == ["alpaca_stocks", "edgar"]
    clock_t[0] = datetime(2026, 11, 27, 19, 0, tzinfo=UTC)  # 14:00 ET on an early-close day: stocks closed at 13:00
    assert "alpaca_stocks" not in await svc.check_staleness()
    p.eventlog.close()


async def test_held_positions_seed_the_context_and_follow_fills():
    p = build_pipeline(Settings(), Secrets(_env_file=None), dry_run=True, deliverers=[], held={"held"})
    assert p.ctx["held"] == {"HELD"}
    res = await p.process(make_event("h1", kind="halt", symbols=["HELD"], meta={"reason_code": "T1"}))
    assert res.priority == "P3"  # a halt on a holding is the emergency path, not 'other'
    fill = make_event("a1", source="alpaca_account", kind="account", symbols=["NEWP"], title="NEWP order fill",
                      meta={"event": "fill", "position_qty": "10"})
    await p.process(fill)
    assert "NEWP" in p.ctx["held"]
    flat = make_event("a2", source="alpaca_account", kind="account", symbols=["HELD"], title="HELD order fill",
                      meta={"event": "fill", "position_qty": 0})
    await p.process(flat)
    assert p.ctx["held"] == {"NEWP"}
    assert load_held_symbols(Secrets(_env_file=None)) == set()  # no broker keys: empty, no network
    p.eventlog.close()


async def test_p3_bypasses_a_classifier_backlog():
    clf = GatedClassifier()
    po = Recorder("pushover")
    p = _pipeline([po], classifier=clf)
    news = [make_event(f"n{i}", symbols=["ACME"], title=t) for i, t in enumerate(
        ("Acme beats estimates", "Acme names a new CFO", "Acme recalls a product line"))]
    halt = make_event("h1", kind="halt", symbols=["HELD"], meta={"reason_code": "T1"})
    svc = MonitorService([FileFeed(events=[*news, halt])], p, stop_when_feeds_end=True, watchdog_interval_s=0.01)
    task = asyncio.create_task(svc.run())
    for _ in range(300):
        if po.sent:
            break
        await asyncio.sleep(0.01)
    assert po.sent and po.sent[0][1] == "P3"  # the halt went out while the P1s were still waiting on Haiku
    assert clf.started >= 1 and clf.finished == 0
    clf.gate.set()
    await asyncio.wait_for(task, timeout=5)
    assert svc.processed == 4 and svc.inflight_cancelled == 0 and svc.inflight == 0


async def test_shutdown_drains_inflight_deliveries_before_cancelling():
    po = Recorder("pushover", delay_s=0.3)
    p = _pipeline([po])
    halt = make_event("h1", kind="halt", symbols=["HELD"], meta={"reason_code": "T1"})
    svc = MonitorService([FileFeed(events=[halt])], p, stop_when_feeds_end=True, watchdog_interval_s=0.01)
    await asyncio.wait_for(svc.run(), timeout=5)
    assert po.sent == [po.sent[0]] and po.sent[0][1] == "P3"
    assert svc.inflight_cancelled == 0 and p.draining is True and p.stats["delivered"] == 1


async def test_build_feeds_wires_the_bar_trigger_engine_to_the_held_set():
    sec = Secrets(_env_file=None, alpaca_api_key="k", alpaca_secret_key="s")
    held = {"HELD"}
    reference = {"HELD": {"prev_close": 100.0, "avg_vol_20d": 1_000_000.0}}
    feeds = build_feeds(Settings(), sec, dry_run=False, names=["alpaca_stocks"], held=held, reference=reference)
    feed = feeds[0]
    assert feed.engine is not None and feed.engine.held is held and feed.engine.reference == reference
    bar = json.dumps([{"T": "b", "S": "HELD", "o": 99.0, "h": 99.5, "l": 92.0, "c": 93.0, "v": 50_000, "t": "2026-10-06T14:00:00Z"}])
    events = feed._parse_frame(bar)
    assert {e.meta.get("trigger") for e in events if e.kind == "bar_trigger"} == {"gap", "adverse_move"}
    assert all(e.symbols == ["HELD"] for e in events)

    class WS:
        def __init__(self):
            self.sent: list[str] = []

        async def send(self, msg):
            self.sent.append(msg)

    ws = WS()
    await feed._handshake(ws)
    assert json.loads(ws.sent[1])["bars"] == ["*"]
    assert service_mod.load_bar_reference(Settings.model_validate({"data": {"store_path": "/nonexistent/x.duckdb"}})) == {}


def test_session_rollover_resets_smallcap_memory_and_stale_latches():
    p = build_pipeline(Settings(), Secrets(_env_file=None), dry_run=True)
    p.smallcap.observe(make_event("h1", kind="halt", symbols=["SCAM"], meta={"reason_code": "T12"}))
    svc = MonitorService([], p, clock=lambda: MARKET_OPEN_TS)
    svc.stale_alerted.add("edgar")
    assert svc.roll_session(MARKET_OPEN_TS + timedelta(hours=5)) is False and "SCAM" in p.smallcap.blocklist
    assert svc.roll_session(MARKET_OPEN_TS + timedelta(days=1)) is True
    assert "SCAM" not in p.smallcap.blocklist and "SCAM" in p.smallcap.tainted and svc.stale_alerted == set()
    p.eventlog.close()


async def test_feed_cursors_are_persisted_per_source():
    p = build_pipeline(Settings(), Secrets(_env_file=None), dry_run=True)
    late = make_event("b", symbols=["X"], title="later", ts=T0 + timedelta(minutes=5))
    svc = MonitorService([FileFeed(events=[make_event("a", symbols=["X"], title="t"), late])], p, stop_when_feeds_end=True,
                         watchdog_interval_s=0.01)
    log = p.eventlog
    await asyncio.wait_for(svc.run(), timeout=5)
    assert svc.cursors["file"] == late.ts_source.astimezone(UTC).isoformat()
    assert svc._persisted_cursors["file"] == svc.cursors["file"]  # written to the event log before it closed
    assert log is p.eventlog


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
