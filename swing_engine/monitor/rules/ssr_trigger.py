"""Short-sale restriction (Rule 201) trigger: >= 10% drop from prior close. Held => emergency."""
from __future__ import annotations

from typing import Any

from swing_engine.core.interfaces import Rule
from swing_engine.core.models import Event
from swing_engine.core.registry import register

from ..constants import SSR_TRIGGER_DROP_PCT
from ._common import P1, P2, P3, tiered


@register("rule", "ssr_trigger")
class SsrTrigger(Rule):
    name = "ssr_trigger"

    def evaluate(self, event: Event, ctx: dict[str, Any]) -> tuple[str, str] | None:
        is_ssr = event.kind == "ssr" or (event.kind == "bar_trigger" and event.meta.get("trigger") == "ssr")
        if not is_ssr:
            return None
        drop = event.meta.get("drop_pct")
        if drop is not None and float(drop) > -SSR_TRIGGER_DROP_PCT and event.kind == "bar_trigger":
            return None
        return "ssr_trigger", tiered(event, ctx, P3, P2, P1)
