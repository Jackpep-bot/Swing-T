"""Shared feed plumbing: backoff schedule, websocket reconnect loop, polling loop. Underscore => not discovered."""
from __future__ import annotations

import asyncio
import hashlib
import json
import random
import time
from collections.abc import AsyncIterator, Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import structlog

from swing_engine.core.interfaces import Feed
from swing_engine.core.models import Event

from ..constants import (
    BACKOFF_BASE_S,
    BACKOFF_FACTOR,
    BACKOFF_JITTER,
    BACKOFF_MAX_S,
    HTTP_FORBIDDEN,
    POLL_SEEN_MAX,
    WS_PING_INTERVAL_S,
)

log = structlog.get_logger(__name__)
#: a failed session that stayed up at least this long counts as healthy: the backoff schedule restarts.
HEALTHY_SESSION_S = BACKOFF_MAX_S


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
    """Runs `_session()` forever with backoff between failures. Subclasses push events into `self._emit`.

    Liveness is tracked separately from data: `last_activity_at` moves on every received frame or completed
    poll (even when nothing new was emitted), which is what the service watchdog should judge a feed by.
    The backoff schedule restarts after any session that was healthy (saw activity, or lived at least
    `HEALTHY_SESSION_S`), not only after a clean return: websocket drops always raise.
    """

    name = "base"

    def __init__(self, max_sessions: int | None = None, sleeper: Callable[[float], Any] = asyncio.sleep):
        self._max_sessions = max_sessions
        self._sleep = sleeper
        self._queue: asyncio.Queue[Event | None] = asyncio.Queue()
        self.sessions = 0
        self.last_event_at: datetime | None = None
        self.last_activity_at: datetime | None = None
        self.last_error: str | None = None
        self.stopped = False
        self._session_healthy = False

    async def _session(self) -> None:  # pragma: no cover - abstract
        raise NotImplementedError

    def _note_activity(self) -> None:
        """Transport is alive: a frame arrived or a poll completed (with or without new events)."""
        self.last_activity_at = now_utc()
        self._session_healthy = True

    async def _emit(self, event: Event) -> None:
        self.last_event_at = now_utc()
        self._note_activity()
        await self._queue.put(event)

    def stop(self) -> None:
        self.stopped = True
        self._queue.put_nowait(None)

    def _retry_floor(self, exc: BaseException) -> float:
        """Minimum delay before the next session after `exc` (polling feeds honour their interval)."""
        return 0.0

    async def _runner(self) -> None:
        delays = backoff_delays()
        while not self.stopped:
            if self._max_sessions is not None and self.sessions >= self._max_sessions:
                break
            self.sessions += 1
            self._session_healthy = False
            started = time.monotonic()
            try:
                await self._session()
                delays = backoff_delays()  # a clean session end resets the schedule
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 - any feed error => reconnect with backoff
                self.last_error = f"{type(e).__name__}: {e}"[:200]
                if self._session_healthy or time.monotonic() - started >= HEALTHY_SESSION_S:
                    delays = backoff_delays()  # the session that just died was healthy: do not ratchet
                delay = max(next(delays), self._retry_floor(e))
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
                self._note_activity()  # subscription acks, heartbeat trades and empty frames all count
                for ev in self._parse_frame(raw):
                    await self._emit(ev)


def decode_frame(raw: str | bytes) -> Any:
    if isinstance(raw, bytes | bytearray):
        raw = raw.decode("utf-8", errors="replace")
    return json.loads(raw)


class PollingFeed(ReconnectingFeed):
    """Poll `_poll()` every `interval_s`; emits only events whose ids were not seen before.

    A failed poll never re-polls faster than `interval_s` (vendors publish a cadence: Nasdaq 60 s, SEC fair
    access), honours `Retry-After` on 429/503, and waits `forbidden_retry_s` after a 403 when set.
    """

    name = "poll"
    forbidden_retry_s: float | None = None

    def __init__(self, interval_s: float, max_polls: int | None = None, **kw: Any):
        super().__init__(**kw)
        self.interval_s = interval_s
        self._max_polls = max_polls
        self.polls = 0
        self._seen: dict[str, None] = {}  # insertion-ordered set, pruned to POLL_SEEN_MAX

    async def _poll(self) -> list[Event]:  # pragma: no cover - abstract
        raise NotImplementedError

    def _remember(self, event_id: str) -> bool:
        """True when `event_id` is new. Keeps at most POLL_SEEN_MAX ids (oldest forgotten first)."""
        if event_id in self._seen:
            return False
        self._seen[event_id] = None
        while len(self._seen) > POLL_SEEN_MAX:
            del self._seen[next(iter(self._seen))]
        return True

    def _retry_floor(self, exc: BaseException) -> float:
        floor = float(self.interval_s)
        response = getattr(exc, "response", None)
        if response is None:
            return floor
        headers = getattr(response, "headers", None)
        retry_after = headers.get("Retry-After") if headers is not None and hasattr(headers, "get") else None
        if retry_after:
            try:
                floor = max(floor, float(retry_after))
            except ValueError:
                pass
        if getattr(response, "status_code", None) == HTTP_FORBIDDEN and self.forbidden_retry_s is not None:
            floor = max(floor, float(self.forbidden_retry_s))
        return floor

    async def _session(self) -> None:
        while not self.stopped:
            if self._max_polls is not None and self.polls >= self._max_polls:
                self.stopped = True
                return
            self.polls += 1
            events = await self._poll()
            self._note_activity()  # a successful poll with nothing new is still a live transport
            for ev in events:
                if self._remember(ev.event_id):
                    await self._emit(ev)
            await self._sleep(self.interval_s)
