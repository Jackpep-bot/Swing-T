"""Shared helpers for monitor tests (not collected: no test_ prefix)."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from swing_engine.core.models import Event, Priority

FIXTURES = Path(__file__).parent / "fixtures" / "monitor"
T0 = datetime(2026, 10, 6, 14, 0, tzinfo=UTC)  # 10:00 ET on a Tuesday


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixture_json(name: str) -> Any:
    return json.loads(fixture_text(name))


def make_event(
    event_id: str = "e1",
    source: str = "alpaca_news",
    kind: str = "news",
    symbols: list[str] | None = None,
    title: str = "",
    body: str = "",
    ts: datetime = T0,
    received: datetime | None = None,
    meta: dict[str, Any] | None = None,
    priority: Priority = Priority.P0,
) -> Event:
    return Event(
        event_id=event_id,
        source=source,
        kind=kind,
        ts_source=ts,
        ts_received=received or ts,
        symbols=symbols or [],
        title=title,
        body=body,
        meta=meta or {},
        priority=priority,
    )


def base_ctx(held: set[str] | None = None, watch: set[str] | None = None, **extra: Any) -> dict[str, Any]:
    ctx: dict[str, Any] = {
        "held": set(held or ()),
        "watchlist": set(watch or ()),
        "now": T0,
        "news_tagged": {},
        "form4_history": {},
    }
    ctx.update(extra)
    return ctx
