from __future__ import annotations

import asyncio
import json

import httpx
import pytest
import respx

from swing_engine.core.config import Secrets, Settings
from swing_engine.core.models import Priority
from swing_engine.monitor.delivery.console import ConsoleDeliverer
from swing_engine.monitor.delivery.telegram import TelegramAPIError, TelegramDeliverer
from swing_engine.monitor.eventlog import EventLog
from swing_engine.monitor.service import (
    TELEGRAM_UPDATES_CURSOR,
    TELEGRAM_UPDATES_TASK,
    MonitorService,
    TelegramUpdatesFeed,
    build_pipeline,
    build_telegram_updates,
)
from tests.monitor_helpers import T0, make_event

CHAT = "4242"


class FakeEventLog:
    def __init__(self, events=()):
        self.events = {e.event_id: e for e in events}
        self.cursors: dict[str, str] = {}

    def get(self, event_id):
        ev = self.events.get(event_id)
        return ev.model_copy(deep=True) if ev is not None else None

    def update(self, event):
        self.events[event.event_id] = event

    def cursor(self, source):
        return self.cursors.get(source)

    def set_cursor(self, source, cursor):
        self.cursors[source] = cursor


class FakeBot:
    def __init__(self, batches=()):
        self.batches = list(batches)
        self.calls: list[tuple[int | None, float]] = []
        self.answers: list[tuple[str, str]] = []

    async def get_updates(self, offset, timeout_s):
        self.calls.append((offset, timeout_s))
        if not self.batches:
            await asyncio.sleep(3600)
        item = self.batches.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    async def answer_callback(self, callback_query_id, text=""):
        self.answers.append((callback_query_id, text))
        return True


class FakeSleep:
    def __init__(self):
        self.calls: list[float] = []

    async def __call__(self, s):
        self.calls.append(s)


def cb(update_id, data, chat=CHAT, sender=CHAT, cq_id=None, with_message=True):
    cq = {"id": cq_id or f"cq{update_id}", "from": {"id": int(sender)}, "data": data}
    if with_message:
        cq["message"] = {"message_id": 1, "chat": {"id": int(chat), "type": "private"}}
    return {"update_id": update_id, "callback_query": cq}


def feed(events=(), batches=(), chat=CHAT, **kw):
    elog = FakeEventLog(events)
    bot = FakeBot(batches)
    return TelegramUpdatesFeed(bot, chat, elog, sleeper=FakeSleep(), clock=lambda: T0, **kw), bot, elog


async def test_accepts_only_the_configured_chat():
    ev = make_event("e1", symbols=["ABC"], priority=Priority.P2)
    f, bot, elog = feed([ev], [[
        cb(10, "useful:e1", chat="999", sender="999"),   # another chat: ignored, not answered
        cb(11, "noise:e1", chat=CHAT, sender="777"),     # right chat id, wrong presser (private chat)
        cb(12, "traded:e1", with_message=False),         # inline-mode callback without a message
        cb(13, "useful:e1"),                             # the owner
    ]])
    assert await f.poll_once() == 4
    assert f.counts["rejected"] == 3 and f.counts["rated"] == 1
    assert elog.events["e1"].meta["rating"] == "useful" and elog.events["e1"].meta["rating_source"] == "telegram"
    assert bot.answers == [("cq13", "Rated useful")]
    assert f.offset == 14 and elog.cursors[TELEGRAM_UPDATES_CURSOR] == "14"


async def test_group_chat_accepts_any_member_of_that_group():
    ev = make_event("e1", symbols=["ABC"])
    f, bot, elog = feed([ev], [[cb(1, "noise:e1", chat="-1001", sender="55"), cb(2, "useful:e1", chat="-1002")]],
                        chat="-1001")
    await f.poll_once()
    assert f.counts["rated"] == 1 and f.counts["rejected"] == 1 and elog.events["e1"].meta["rating"] == "noise"


async def test_empty_chat_id_rejects_everything():
    f, bot, _ = feed([make_event("e1")], [[cb(1, "useful:e1", chat="0", sender="0")]], chat="")
    await f.poll_once()
    assert f.counts["rejected"] == 1 and bot.answers == []


async def test_messages_malformed_and_unknown_events():
    f, bot, elog = feed([make_event("e1")], [[
        {"update_id": 5, "message": {"chat": {"id": int(CHAT)}, "text": "/buy everything"}},
        cb(6, "great:e1"),
        cb(7, "useful:missing"),
        {"no_update_id": True},
    ]])
    await f.poll_once()
    assert f.counts["ignored"] == 2 and f.counts["malformed"] == 1 and f.counts["not_rated"] == 1
    assert bot.answers == [("cq6", "Unrecognised button"), ("cq7", "Not rated: unknown_event")]
    assert "rating" not in elog.events["e1"].meta and f.offset == 8


async def test_offset_is_resumed_from_the_event_log_cursor():
    elog = FakeEventLog()
    elog.cursors[TELEGRAM_UPDATES_CURSOR] = "41"
    bot = FakeBot([[]])
    f = TelegramUpdatesFeed(bot, CHAT, elog)
    assert f.offset == 41
    await f.poll_once()
    assert bot.calls == [(41, 30.0)]
    elog.cursors[TELEGRAM_UPDATES_CURSOR] = "garbage"
    assert TelegramUpdatesFeed(bot, CHAT, elog).offset is None
    assert TelegramUpdatesFeed(bot, CHAT, None).offset is None


async def test_backoff_honours_retry_after_then_grows_exponentially():
    f, _, _ = feed(backoff_base_s=1.0, backoff_max_s=8.0)
    assert f.next_delay(TelegramAPIError("getUpdates", 429, "slow down", retry_after=17)) == 17.0
    assert [f.next_delay(httpx.ConnectError("x")) for _ in range(4)] == [2.0, 4.0, 8.0, 8.0]


async def test_run_loop_survives_errors_and_resets_failures():
    ev = make_event("e1")
    errors = [TelegramAPIError("getUpdates", 409, "Conflict"), httpx.ReadTimeout("t")]
    f, bot, elog = feed([ev], [*errors, [cb(3, "traded:e1")]])
    task = asyncio.create_task(f.run())
    for _ in range(50):
        await asyncio.sleep(0)
        if f.counts["rated"]:
            break
    f.stop()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert f._sleep.calls == [1.0, 2.0] and f.failures == 0 and elog.events["e1"].meta["rating"] == "traded"


@respx.mock
async def test_end_to_end_with_the_real_bot_client_and_eventlog():
    base = "https://api.telegram.org/bot1:a"
    respx.post(f"{base}/getUpdates").mock(return_value=httpx.Response(200, json={"ok": True, "result": [
        cb(100, "useful:alpaca_news:9"), cb(101, "noise:alpaca_news:9", chat="31337", sender="31337"),
    ]}))
    answer = respx.post(f"{base}/answerCallbackQuery").mock(return_value=httpx.Response(200, json={"ok": True}))
    elog = EventLog(":memory:")
    elog.append(make_event("alpaca_news:9", symbols=["ABC"], priority=Priority.P2))
    async with httpx.AsyncClient() as client:
        bot = TelegramDeliverer("1:a", CHAT, client=client)
        f = TelegramUpdatesFeed(bot, CHAT, elog)
        assert await f.poll_once() == 2
    assert elog.get("alpaca_news:9").meta["rating"] == "useful"
    assert answer.call_count == 1 and json.loads(answer.calls[0].request.read())["text"] == "Rated useful"
    assert elog.cursor(TELEGRAM_UPDATES_CURSOR) == "102"
    elog.close()


def test_build_telegram_updates_only_for_live_runs_with_telegram():
    s = Settings()
    no_tg = Secrets(_env_file=None)
    tg = Secrets(telegram_bot_token="1:a", telegram_chat_id=CHAT, _env_file=None)
    dry = build_pipeline(s, tg, dry_run=True)
    assert build_telegram_updates(tg, dry, dry_run=True) is None
    assert build_telegram_updates(no_tg, dry, dry_run=False) is None
    bot = TelegramDeliverer("1:a", CHAT)
    live = build_pipeline(s, tg, dry_run=True, deliverers=[ConsoleDeliverer(), bot])
    updates = build_telegram_updates(tg, live, dry_run=False)
    assert updates is not None and updates.bot is bot and updates.chat_id == CHAT and updates.eventlog is live.eventlog
    fallback = build_telegram_updates(tg, dry, dry_run=False)
    assert isinstance(fallback.bot, TelegramDeliverer) and fallback.owns_bot and not updates.owns_bot


async def test_aclose_only_closes_an_owned_bot():
    class Closable(FakeBot):
        closed = 0

        async def aclose(self):
            Closable.closed += 1

    await TelegramUpdatesFeed(Closable(), CHAT, None).aclose()
    assert Closable.closed == 0
    await TelegramUpdatesFeed(Closable(), CHAT, None, owns_bot=True).aclose()
    assert Closable.closed == 1


async def test_service_runs_and_stops_the_updates_task():
    p = build_pipeline(Settings(), Secrets(_env_file=None), dry_run=True, deliverers=[])
    p.eventlog.append(make_event("e1", symbols=["ABC"]))
    bot = FakeBot([[cb(1, "useful:e1")]])
    updates = TelegramUpdatesFeed(bot, CHAT, p.eventlog)
    svc = MonitorService([], p, watchdog_interval_s=0.01, updates=updates)
    runner = asyncio.create_task(svc.run())
    for _ in range(100):
        await asyncio.sleep(0.005)
        if updates.counts["rated"]:
            break
    assert any(t.get_name() == TELEGRAM_UPDATES_TASK for t in svc._tasks)
    assert p.eventlog.get("e1").meta["rating"] == "useful"
    svc.stop()
    await asyncio.wait_for(runner, timeout=10)
    assert updates._stopped


def test_store_factory_and_rollover_reload_the_float_map(tmp_path):
    from datetime import date, datetime, timedelta

    import pandas as pd

    from swing_engine.data.store import Store
    from swing_engine.monitor.service import store_factory

    missing = Settings.model_validate({"data": {"store_path": str(tmp_path / "none.duckdb")}})
    assert store_factory(missing) is None
    path = tmp_path / "swing.duckdb"
    with Store(path) as st:
        st.write_table("float", pd.DataFrame([{"symbol": "TINY", "as_of": date(2026, 9, 30), "float_shares": 5e6}]),
                       ["symbol", "as_of"])
    s = Settings.model_validate({"data": {"store_path": str(path)}})
    opener = store_factory(s)
    assert opener is not None
    p = build_pipeline(s, Secrets(_env_file=None), dry_run=True, deliverers=[], store=opener)
    assert p.smallcap.float_map == {}  # build_pipeline never touches the store
    assert p.load_float_map(date(2026, 10, 6)) == 1 and p.smallcap.float_map["TINY"].float_shares == 5e6
    p.smallcap.set_float_map({})
    svc = MonitorService([], p, clock=lambda: T0)
    assert svc.roll_session(T0 + timedelta(days=1))
    assert "TINY" in p.smallcap.float_map
    assert not svc.roll_session(datetime(2026, 10, 7, 15, 0, tzinfo=T0.tzinfo))
    p.eventlog.close()
