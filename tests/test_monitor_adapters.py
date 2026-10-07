from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx
import pytest
import respx

from swing_engine.core import registry
from swing_engine.core.models import Event
from swing_engine.monitor.adapters import (
    alpaca_account,
    alpaca_news,
    alpaca_stocks,
    edgar,
    nasdaq_halts,
    nyse_halts,
)
from swing_engine.monitor.adapters._base import PollingFeed, backoff_delays, parse_ts
from swing_engine.monitor.adapters.file_feed import FileFeed, read_events, write_events
from swing_engine.monitor.constants import BACKOFF_BASE_S, BACKOFF_JITTER, EDGAR_FORBIDDEN_RETRY_S
from tests.monitor_helpers import FIXTURES, fixture_json, fixture_text, make_event


def test_registry_has_all_feeds():
    assert {"alpaca_news", "alpaca_stocks", "alpaca_account", "edgar", "nasdaq_halts", "nyse_halts", "file"} <= set(registry.names("feed"))


def test_parse_ts_handles_nanoseconds_and_naive():
    dt = parse_ts("2026-10-06T20:05:12.123456789Z")
    assert dt == datetime(2026, 10, 6, 20, 5, 12, 123456, tzinfo=UTC)
    assert parse_ts("2026-10-06").tzinfo is not None
    assert parse_ts("garbage").tzinfo is not None


def test_backoff_schedule_grows_and_caps():
    import random

    d = backoff_delays(base=1, factor=2, max_s=10, jitter=0.0, rng=random.Random(1))
    assert [next(d) for _ in range(6)] == [1, 2, 4, 8, 10, 10]


# ---- Alpaca news --------------------------------------------------------------------------------------------
def test_alpaca_news_frames():
    frames = fixture_json("alpaca_news_frames.json")
    events = []
    for f in frames[:-1]:
        events.extend(alpaca_news.parse_frame(f))
    assert [e.event_id for e in events] == ["alpaca_news:41234567", "alpaca_news:41234568", "alpaca_news:41234569"]
    e = events[0]
    assert e.kind == "news" and e.symbols == ["ACME"] and e.ts_source.microsecond == 123456
    assert e.url.endswith("acme-q3") and e.meta["provider"] == "benzinga"
    assert events[2].symbols == ["MEGA", "OLDC"]
    with pytest.raises(ConnectionError):
        alpaca_news.parse_frame(frames[-1])


# ---- Alpaca stocks ------------------------------------------------------------------------------------------
def test_alpaca_stocks_statuses_lulds_and_bars():
    frames = fixture_json("alpaca_stocks_frames.json")
    engine = alpaca_stocks.BarTriggerEngine(
        reference={"ACME": {"prev_close": 50.0, "avg_vol_20d": 2_000_000, "avg_vol_50d": 2_000_000, "high_52w": 55.0},
                   "HELD": {"prev_close": 100.0, "avg_vol_20d": 1_000_000}},
        held={"HELD"},
    )
    events: list[Event] = []
    for f in frames[:-1]:
        events.extend(alpaca_stocks.parse_frame(f, engine))
    kinds = [(e.kind, e.symbols[0], e.meta.get("reason_code") or e.meta.get("trigger")) for e in events]
    assert ("halt", "PUMP", "T1") in kinds
    resumed = next(e for e in events if e.meta.get("status") == "resumed")
    assert resumed.symbols == ["PUMP"] and resumed.meta["reason_code"] == "T2"
    paused = next(e for e in events if e.meta.get("reason_code") == "LUDP")
    assert paused.meta["status"] == "paused"
    luld = next(e for e in events if e.kind == "luld")
    assert luld.meta["up"] == 5.5 and luld.meta["down"] == 4.5
    gap = next(e for e in events if e.meta.get("trigger") == "gap")
    assert gap.symbols == ["ACME"] and gap.meta["gap_pct"] == pytest.approx(8.0) and gap.meta["rvol"] > 2
    brk = next(e for e in events if e.meta.get("trigger") == "breakout_52w")
    assert brk.symbols == ["ACME"] and brk.meta["vol_ratio"] >= 1.5
    adv = next(e for e in events if e.meta.get("trigger") == "adverse_move")
    assert adv.symbols == ["HELD"] and adv.meta["pct"] == pytest.approx(-6.5)
    assert len([e for e in events if e.meta.get("trigger") == "gap"]) == 2  # once per symbol per day
    with pytest.raises(ConnectionError):
        alpaca_stocks.parse_frame(frames[-1], engine)


def test_bar_engine_uses_profile_and_ignores_unknown_symbols():
    engine = alpaca_stocks.BarTriggerEngine(reference={"A": {"prev_close": 10, "avg_vol_20d": 1000}}, profile={"A": [0.5] * 391})
    assert engine.on_bar({"T": "b", "S": "ZZZ", "o": 1, "c": 1, "v": 1, "t": "2026-10-06T13:30:00Z"}) == []
    out = engine.on_bar({"T": "b", "S": "A", "o": 10.5, "c": 10.5, "v": 1000, "t": "2026-10-06T13:30:00Z"})
    assert out[0].meta["rvol"] == pytest.approx(2.0)


def test_reference_from_panel_takes_the_last_row_per_symbol():
    import pandas as pd

    panel = pd.DataFrame(
        {
            "symbol": ["A", "A", "B", "C"],
            "ts": pd.to_datetime(["2026-10-05", "2026-10-06", "2026-10-06", "2026-10-06"]),
            "close": [9.0, 10.0, 20.0, float("nan")],
            "avg_vol_20d": [900.0, 1000.0, 2000.0, 1.0],
            "avg_vol_50d": [950.0, 1050.0, float("nan"), 1.0],
            "high_52w": [11.0, 12.0, 25.0, 1.0],
        }
    )
    ref = alpaca_stocks.reference_from_panel(panel)
    assert ref["A"] == {"prev_close": 10.0, "avg_vol_20d": 1000.0, "avg_vol_50d": 1050.0, "high_52w": 12.0}
    assert ref["B"] == {"prev_close": 20.0, "avg_vol_20d": 2000.0, "high_52w": 25.0}
    assert "C" not in ref and alpaca_stocks.reference_from_panel(None) == {}


async def test_stocks_handshake_subscribes_bars_and_a_heartbeat_symbol():
    class WS:
        def __init__(self):
            self.sent: list[str] = []

        async def send(self, msg: str) -> None:
            self.sent.append(msg)

    ws = WS()
    engine = alpaca_stocks.BarTriggerEngine(reference={"ACME": {"prev_close": 50.0}})
    await alpaca_stocks.AlpacaStocksFeed("k", "s", symbols=["ACME"], engine=engine)._handshake(ws)
    sub = json.loads(ws.sent[1])
    assert sub["statuses"] == ["ACME"] and sub["bars"] == ["ACME"] and sub["trades"] == ["SPY"]
    ws2 = WS()
    await alpaca_stocks.AlpacaStocksFeed("k", "s", heartbeat_symbol=None)._handshake(ws2)
    assert "trades" not in json.loads(ws2.sent[1]) and "bars" not in json.loads(ws2.sent[1])


# ---- Alpaca account -----------------------------------------------------------------------------------------
def test_alpaca_account_frames():
    frames = fixture_json("alpaca_account_frames.json")
    events = []
    for f in frames[:-1]:
        events.extend(alpaca_account.parse_frame(f))
    assert [e.meta["event"] for e in events] == ["new", "fill", "rejected"]
    fill = events[1]
    assert fill.kind == "account" and fill.symbols == ["ACME"] and fill.meta["filled_avg_price"] == "54.10"
    assert events[2].symbols == ["HELD"] and events[2].title.startswith("HELD order rejected")
    assert alpaca_account.parse_frame(frames[0].encode()) == []  # bytes frames decode too
    with pytest.raises(ConnectionError):
        alpaca_account.parse_frame(frames[-1])


# ---- websocket reconnect loop -------------------------------------------------------------------------------
class FakeWS:
    def __init__(self, frames, fail_after: bool):
        self.frames = list(frames)
        self.fail_after = fail_after
        self.sent: list[str] = []

    async def send(self, msg: str) -> None:
        self.sent.append(msg)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.frames:
            return self.frames.pop(0)
        if self.fail_after:
            raise ConnectionResetError("socket closed")
        raise StopAsyncIteration


async def test_ws_feed_reconnects_with_backoff():
    frames = fixture_json("alpaca_news_frames.json")
    sessions = [FakeWS(frames[:4], fail_after=True), FakeWS(frames[4:5], fail_after=False)]
    opened: list[FakeWS] = []

    @asynccontextmanager
    async def connector(url):
        ws = sessions.pop(0)
        opened.append(ws)
        yield ws

    sleeps: list[float] = []

    async def sleeper(s):
        sleeps.append(s)

    feed = alpaca_news.AlpacaNewsFeed("k", "s", connector=connector, max_sessions=2, sleeper=sleeper)
    got = [e async for e in feed.events()]
    assert [e.event_id for e in got] == ["alpaca_news:41234567", "alpaca_news:41234568", "alpaca_news:41234569"]
    assert feed.sessions == 2 and len(sleeps) == 1 and sleeps[0] > 0
    assert json.loads(opened[0].sent[0])["action"] == "auth" and json.loads(opened[1].sent[1])["news"] == ["*"]
    assert "ConnectionResetError" in feed.last_error
    assert feed.last_activity_at is not None and feed.last_event_at is not None


async def _run_ws_sessions(sessions: list[FakeWS]) -> list[float]:
    @asynccontextmanager
    async def connector(url):
        yield sessions.pop(0)

    sleeps: list[float] = []

    async def sleeper(s):
        sleeps.append(s)

    n = len(sessions)
    feed = alpaca_news.AlpacaNewsFeed("k", "s", connector=connector, max_sessions=n, sleeper=sleeper)
    _ = [e async for e in feed.events()]
    return sleeps


async def test_backoff_restarts_after_a_healthy_session_but_ratchets_on_dead_ones():
    frames = fixture_json("alpaca_news_frames.json")
    # every session receives a frame before the socket drops: each reconnect waits about the base delay
    healthy = await _run_ws_sessions([FakeWS(frames[:1], fail_after=True) for _ in range(4)])
    assert len(healthy) == 4
    assert all(s <= BACKOFF_BASE_S * (1 + BACKOFF_JITTER) for s in healthy), healthy
    # sockets that die before any frame keep ratcheting towards the cap
    dead = await _run_ws_sessions([FakeWS([], fail_after=True) for _ in range(4)])
    assert len(dead) == 4 and dead[2] > dead[0] and dead[3] > dead[1]


async def test_polling_feed_never_repolls_faster_than_its_interval_after_an_error():
    class Flaky(PollingFeed):
        name = "flaky"

        async def _poll(self):
            raise RuntimeError("503 from the vendor")

    sleeps: list[float] = []

    async def sleeper(s):
        sleeps.append(s)

    feed = Flaky(interval_s=60, max_sessions=3, sleeper=sleeper)
    assert [e async for e in feed.events()] == []
    assert len(sleeps) == 3 and all(s >= 60 for s in sleeps), sleeps
    assert feed.last_activity_at is None  # never completed a poll


def test_polling_retry_floor_honours_retry_after_and_sec_403():
    def status_error(code: int, **headers: str) -> httpx.HTTPStatusError:
        req = httpx.Request("GET", "https://www.sec.gov/cgi-bin/browse-edgar")
        resp = httpx.Response(code, headers=headers, request=req)
        return httpx.HTTPStatusError(str(code), request=req, response=resp)

    feed = edgar.EdgarFeed("ua test@example.com", interval_s=20)
    assert feed._retry_floor(RuntimeError("x")) == 20
    assert feed._retry_floor(status_error(503)) == 20
    assert feed._retry_floor(status_error(503, **{"Retry-After": "90"})) == 90
    assert feed._retry_floor(status_error(403)) == EDGAR_FORBIDDEN_RETRY_S
    assert feed._retry_floor(status_error(429, **{"Retry-After": "garbage"})) == 20


def test_polling_feed_forgets_the_oldest_seen_ids():
    feed = PollingFeed(interval_s=1)
    feed._seen = {}
    from swing_engine.monitor.adapters import _base

    assert all(feed._remember(f"id{i}") for i in range(_base.POLL_SEEN_MAX + 5))
    assert len(feed._seen) == _base.POLL_SEEN_MAX and not feed._remember("id10") and feed._remember("id0")


# ---- EDGAR --------------------------------------------------------------------------------------------------
def test_edgar_atom_parse():
    cik_map = {"0001234567": "ACME", "7654321": "DOOM", "1112223": "TINY"}
    events = edgar.parse_atom(fixture_text("edgar_current.atom"), cik_map)
    by_id = {e.event_id: e for e in events}
    assert set(by_id) == {
        "edgar:0001234567-26-000012", "edgar:0007654321-26-000044", "edgar:0001112223-26-000009",
        "edgar:0001234567-26-000013", "edgar:0005556667-26-000002",
    }
    acme = by_id["edgar:0001234567-26-000012"]
    assert acme.symbols == ["ACME"] and acme.meta["form_type"] == "8-K" and acme.meta["items"] == ["2.02", "9.01"]
    assert acme.ts_source == datetime(2026, 10, 6, 20, 5, 12, tzinfo=UTC)
    doom = by_id["edgar:0007654321-26-000044"]
    assert doom.meta["items"] == ["4.02", "3.01"] and "items 4.02, 3.01" in doom.title
    tiny = by_id["edgar:0001112223-26-000009"]
    assert tiny.meta["form_type"] == "424B5" and tiny.symbols == ["TINY"]
    f4 = by_id["edgar:0001234567-26-000013"]
    assert f4.meta["form_type"] == "4" and f4.meta["role"] == "Issuer" and f4.symbols == ["ACME"]
    late = by_id["edgar:0005556667-26-000002"]
    assert late.meta["form_type"] == "NT 10-K" and late.symbols == []


@respx.mock
async def test_edgar_feed_polls_with_user_agent_and_cursor():
    route = respx.get("https://www.sec.gov/cgi-bin/browse-edgar").mock(return_value=httpx.Response(200, text=fixture_text("edgar_current.atom")))
    sleeps: list[float] = []

    async def sleeper(s):
        sleeps.append(s)

    async with httpx.AsyncClient() as client:
        feed = edgar.EdgarFeed("swing-engine test@example.com", form_types=["8-K", "4"], cik_map={"1234567": "ACME"},
                               client=client, interval_s=20, max_polls=2, sleeper=sleeper)
        events = [e async for e in feed.events()]
    assert route.call_count == 4  # 2 polls x 2 forms
    req = route.calls[0].request
    assert req.headers["User-Agent"] == "swing-engine test@example.com"
    assert "type=8-K" in str(req.url) and "owner=exclude" in str(req.url) and "output=atom" in str(req.url)
    assert "owner=only" in str(route.calls[1].request.url)
    assert len(events) == 5  # second poll is fully deduped
    # the cursor is the newest ts_source (UTC ISO), not an accession number (those sort by filer-agent CIK)
    assert feed.cursor == max(e.ts_source for e in events).astimezone(UTC).isoformat()
    assert feed.cursor.endswith("+00:00")
    assert 20 in sleeps
    assert feed.last_activity_at is not None  # a completed poll counts as transport liveness


@respx.mock
async def test_edgar_catch_up_filters_by_ts_source_not_accession():
    respx.get("https://www.sec.gov/cgi-bin/browse-edgar").mock(return_value=httpx.Response(200, text=fixture_text("edgar_current.atom")))
    async with httpx.AsyncClient() as client:
        feed = edgar.EdgarFeed("ua test@example.com", form_types=["8-K"], client=client, interval_s=20)
        fresh = await feed.catch_up(None)
        since = fresh[1].ts_source
        newer = await feed.catch_up(since.isoformat())
        legacy = await feed.catch_up("0001213900-26-000010")  # an old accession cursor must not drop anything
    assert len(fresh) == 5
    assert [e.event_id for e in newer] == [e.event_id for e in fresh if e.ts_source > since]
    assert 0 < len(newer) < len(fresh)
    assert len(legacy) == len(fresh)


# ---- Nasdaq halts -------------------------------------------------------------------------------------------
def test_nasdaq_rss_parse_and_diff():
    rows1 = nasdaq_halts.parse_halts_rss(fixture_text("nasdaq_halts_1.xml"))
    assert [r["IssueSymbol"] for r in rows1] == ["PUMP", "TINY"]
    assert rows1[0]["ReasonCode"] == "T1" and rows1[1]["ResumptionTradeTime"] == "10:07:00"
    diff = nasdaq_halts.HaltDiff()
    ev1 = diff.apply(rows1)
    assert [(e.symbols[0], e.meta["status"]) for e in ev1] == [("PUMP", "halted"), ("TINY", "halted"), ("TINY", "resumed")]
    assert ev1[0].ts_source == datetime(2026, 10, 6, 13, 31, tzinfo=UTC)
    assert diff.apply(rows1) == []
    ev2 = diff.apply(nasdaq_halts.parse_halts_rss(fixture_text("nasdaq_halts_2.xml")))
    assert [(e.symbols[0], e.meta["status"], e.meta["reason_code"]) for e in ev2] == [("PUMP", "resumed", "T1"), ("SCAM", "halted", "T12")]
    assert ev2[0].ts_source == datetime(2026, 10, 6, 13, 45, tzinfo=UTC)
    assert len({e.event_id for e in ev1 + ev2}) == 5


@respx.mock
async def test_nasdaq_feed_polls_every_60s():
    respx.get("https://www.nasdaqtrader.com/rss.aspx").mock(
        side_effect=[httpx.Response(200, text=fixture_text("nasdaq_halts_1.xml")), httpx.Response(200, text=fixture_text("nasdaq_halts_2.xml"))]
    )
    sleeps: list[float] = []

    async def sleeper(s):
        sleeps.append(s)

    async with httpx.AsyncClient() as client:
        feed = nasdaq_halts.NasdaqHaltsFeed(client=client, max_polls=2, sleeper=sleeper)
        events = [e async for e in feed.events()]
    assert len(events) == 5 and sleeps[:1] == [60]


# ---- NYSE halts ---------------------------------------------------------------------------------------------
def test_nyse_csv_parse_and_diff():
    rows = nyse_halts.parse_halts_csv(fixture_text("nyse_halts.csv"))
    assert [(r["IssueSymbol"], r["ReasonCode"]) for r in rows] == [("BIGCO", "T1"), ("FLIP", "LUDP"), ("SUSP", "H10")]
    feed = nyse_halts.NyseHaltsFeed()
    events = feed.diff(rows)
    assert [(e.symbols[0], e.meta["status"]) for e in events] == [("BIGCO", "halted"), ("FLIP", "halted"), ("FLIP", "resumed"), ("SUSP", "halted")]
    assert events[0].ts_source == datetime(2026, 10, 6, 13, 35, tzinfo=UTC)
    assert feed.diff(rows) == []


# ---- file feed ----------------------------------------------------------------------------------------------
async def test_file_feed_roundtrip(tmp_path):
    events = read_events(FIXTURES / "replay_events.jsonl")
    assert len(events) == 8 and events[0].symbols == ["ACME"]
    p = tmp_path / "out.jsonl"
    assert write_events(p, events) == 8
    assert [e.event_id for e in read_events(p)] == [e.event_id for e in events]
    sleeps: list[float] = []

    async def sleeper(s):
        sleeps.append(s)

    feed = FileFeed(events=[make_event("a", ts=datetime(2026, 10, 6, 1, 0, tzinfo=UTC)), make_event("b", ts=datetime(2026, 10, 6, 1, 0, 30, tzinfo=UTC))],
                    realtime=True, speed=10.0, rebase_received=True, sleeper=sleeper)
    got = [e async for e in feed.events()]
    assert [e.event_id for e in got] == ["a", "b"] and sleeps == [3.0]
    assert got[0].ts_received > got[0].ts_source
    assert asyncio.iscoroutinefunction(feed.catch_up)
