"""Broker trade_updates: order rejections are emergencies; fills are pushes; the rest is digest material."""
from __future__ import annotations

from typing import Any

from swing_engine.core.interfaces import Rule
from swing_engine.core.models import Event
from swing_engine.core.registry import register

from ._common import P0, P1, P2, P3

REJECT_EVENTS = frozenset({"rejected", "suspended", "order_cancel_rejected", "order_replace_rejected"})
FILL_EVENTS = frozenset({"fill", "partial_fill"})
INFO_EVENTS = frozenset({"new", "accepted", "pending_new", "canceled", "expired", "replaced", "done_for_day"})


@register("rule", "account_events")
class AccountEvents(Rule):
    name = "account_events"

    def evaluate(self, event: Event, ctx: dict[str, Any]) -> tuple[str, str] | None:
        if event.kind != "account":
            return None
        kind = str(event.meta.get("event", "")).lower()
        if kind in REJECT_EVENTS:
            return f"order_{kind}", P3
        if kind in FILL_EVENTS:
            return f"order_{kind}", P2
        if kind in INFO_EVENTS:
            return f"order_{kind}", P1
        return f"order_{kind or 'unknown'}", P0
