"""Replayable JSONL feed for tests, dry runs and `swing monitor replay`. One core.models.Event per line."""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from swing_engine.core.interfaces import Feed
from swing_engine.core.models import Event
from swing_engine.core.registry import register

log = structlog.get_logger(__name__)
SOURCE = "file"


def read_events(path: str | Path) -> list[Event]:
    out: list[Event] = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.append(Event.model_validate(json.loads(line)))
    return out


def write_events(path: str | Path, events: Iterable[Event]) -> int:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with p.open("w", encoding="utf-8") as fh:
        for e in events:
            fh.write(e.model_dump_json() + "\n")
            n += 1
    return n


@register("feed", SOURCE)
class FileFeed(Feed):
    name = SOURCE

    def __init__(
        self,
        path: str | Path | None = None,
        events: Iterable[Event] | None = None,
        realtime: bool = False,
        speed: float = 1.0,
        rebase_received: bool = False,
        sleeper: Callable[[float], Any] = asyncio.sleep,
    ):
        self.path = Path(path) if path else None
        self._events = list(events) if events is not None else None
        self.realtime = realtime
        self.speed = max(speed, 1e-6)
        self.rebase_received = rebase_received
        self._sleep = sleeper
        self.last_event_at: datetime | None = None

    def load(self) -> list[Event]:
        if self._events is None:
            self._events = read_events(self.path) if self.path else []
        return self._events

    async def events(self) -> AsyncIterator[Event]:
        prev: datetime | None = None
        for e in self.load():
            if self.realtime and prev is not None:
                gap = (e.ts_source - prev).total_seconds() / self.speed
                if gap > 0:
                    await self._sleep(gap)
            prev = e.ts_source
            if self.rebase_received:
                e = e.model_copy(update={"ts_received": datetime.now(UTC)})
            self.last_event_at = datetime.now(UTC)
            yield e
