"""Shared feed plumbing: backoff schedule, websocket reconnect loop, polling loop. Underscore => not discovered."""
from __future__ import annotations

import asyncio
import hashlib
import json
import random
from collections.abc import AsyncIterator, Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import structlog

from swing_engine.core.interfaces import Feed
from swing_engine.core.models import Event

from ..constants import BACKOFF_BASE_S, BACKOFF_FACTOR, BACKOFF_JITTER, BACKOFF_MAX_S, WS_PING_INTERVAL_S

log = structlog.get_logger(__name__)


def backoff_delays(
    base: float = BACKOFF_BASE_S,
    factor: float = BACKOFF_FACTOR,
    max_s: float = BACKOFF_MAX_S,
    jitter: float = BACKOFF_JITTER,
    rng: random.Random | None = None,
) -> Iterator[float]:
    """Exponential backoff with +/- jitter, capped. Infinite iterator; call next() per failure."""
    rng = rng or random.Random()  # noqa: S311 - jitter only
    delay = base
    while True:
        j = 1.0 + rng.uniform(-jitter, jitter)
        yield min(max_s, delay) * j
        delay = min(max_s, delay * factor)


def stable_id(*parts: Any) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:24]  # noqa: S324 - not security


def parse_ts(value: Any, default: datetime | None = None) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value:
        v = value.strip().replace("Z", "+00:00")
        # Alpaca sends nanosecond precision; fromisoformat accepts at most 6 fractional digits.
        if "." in v:
            head, _, tail = v.partition(".")
            frac = ""
            tz = ""
            for i, ch in enumerate(tail):
                if ch.isdigit():
                    frac += ch
                else:
                    tz = tail[i:]
                    break
            v = f"{head}.{frac[:6] or '0'}{tz}"
        try:
            dt = datetime.fromisoformat(v)
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            pass
    return default or datetime.now(UTC)


def now_utc() -> datetime:
    return datetime.now(UTC)


class ReconnectingFeed(Feed):
    """Runs `_session()` forever with backoff between failures. Subclasses push events into `self._emit`."""

    name = "base"

    def __init__(self, max_sessions: int | None = None, sleeper: Callable[[float], Any] = asyncio.sleep):
        self._max_sessions = max_sessions
        self._sleep = sleeper
        self._queue: asyncio.Queue[Event | None] = asyncio.Queue()
        self.sessions = 0
        self.last_event_at: datetime | None = None
        self.last_error: str | None = None
        self.stopped = False

    async def _session(self) -> None:  # pragma: no cover - abstract
        raise NotImplementedError

    async def _emit(self, event: Event) -> None:
        self.last_event_at = now_utc()
        await self._queue.put(event)

    def stop(self) -> None:
        self.stopped = True
        self._queue.put_nowait(None)

    async def _runner(self) -> None:
        delays = backoff_delays()
        while not self.stopped:
            if self._max_sessions is not None and self.sessions >= self._max_sessions:
                break
            self.sessions += 1
            try:
                await self._session()
                delays = backoff_delays()  # a clean session end resets the schedule
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 - any feed error => reconnect with backoff
                self.last_error = f"{type(e).__name__}: {e}"[:200]
                delay = next(delays)
                log.warning("feed.reconnect", feed=self.name, error=self.last_error, delay_s=round(delay, 2))
                await self._sleep(delay)
        await self._queue.put(None)

    async def events(self) -> AsyncIterator[Event]:
        task = asyncio.create_task(self._runner())
        try:
            while True:
                item = await self._queue.get()
                if item is None:
                    break
                yield item
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass


class WebSocketFeed(ReconnectingFeed):
    """Alpaca-style websocket session: connect, auth, subscribe, then parse every frame.

    `connector(url)` must return an async context manager yielding an object with `send(str)` and async iteration.
    Tests inject a fake; production uses `websockets.connect`.
    """

    name = "ws"
    url: str = ""

    def __init__(self, connector: Callable[..., Any] | None = None, **kw: Any):
        super().__init__(**kw)
        self._connector = connector

    def _connect(self, url: str) -> Any:
        if self._connector is not None:
            return self._connector(url)
        import websockets

        return websockets.connect(url, ping_interval=WS_PING_INTERVAL_S, max_size=None)

    async def _handshake(self, ws: Any) -> None:  # pragma: no cover - abstract
        raise NotImplementedError

    def _parse_frame(self, raw: str | bytes) -> list[Event]:  # pragma: no cover - abstract
        raise NotImplementedError

    async def _session(self) -> None:
        async with self._connect(self.url) as ws:
            await self._handshake(ws)
            async for raw in ws:
                for ev in self._parse_frame(raw):
                    await self._emit(ev)


def decode_frame(raw: str | bytes) -> Any:
    if isinstance(raw, bytes | bytearray):
        raw = raw.decode("utf-8", errors="replace")
    return json.loads(raw)


class PollingFeed(ReconnectingFeed):
    """Poll `_poll()` every `interval_s`; emits only events whose ids were not seen before."""

    name = "poll"

    def __init__(self, interval_s: float, max_polls: int | None = None, **kw: Any):
        super().__init__(**kw)
        self.interval_s = interval_s
        self._max_polls = max_polls
        self.polls = 0
        self._seen: set[str] = set()

    async def _poll(self) -> list[Event]:  # pragma: no cover - abstract
        raise NotImplementedError

    async def _session(self) -> None:
        while not self.stopped:
            if self._max_polls is not None and self.polls >= self._max_polls:
                self.stopped = True
                return
            self.polls += 1
            for ev in await self._poll():
                if ev.event_id in self._seen:
                    continue
                self._seen.add(ev.event_id)
                await self._emit(ev)
            await self._sleep(self.interval_s)
