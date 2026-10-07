"""Trading halts (T1/T2/T12/H10), LULD pauses and band updates. Held => emergency; T12/H10 are toxic anywhere."""
from __future__ import annotations

from typing import Any

from swing_engine.core.interfaces import Rule
from swing_engine.core.models import Event
from swing_engine.core.registry import register

from ..constants import LULD_CODES, MARKET_WIDE_HALT_CODES, NEWS_HALT_CODES, TOXIC_HALT_CODES
from ._common import P0, P1, P2, P3, tiered


def halt_code(event: Event) -> str:
    return str(event.meta.get("reason_code") or event.meta.get("code") or "").upper().strip()


@register("rule", "halts_luld")
class HaltsLuld(Rule):
    name = "halts_luld"

    def evaluate(self, event: Event, ctx: dict[str, Any]) -> tuple[str, str] | None:
        if event.kind == "luld":
            return "luld_band", tiered(event, ctx, P1, P0, P0)
        if event.kind != "halt":
            return None
        code = halt_code(event)
        status = str(event.meta.get("status", "halted")).lower()
        if code in MARKET_WIDE_HALT_CODES:
            return None  # handled by market_wide_suppression
        if status == "resumed":
            return f"resume:{code or 'na'}", tiered(event, ctx, P2, P1, P0)
        if code in TOXIC_HALT_CODES:
            event.meta["toxic"] = True
            return f"halt:{code}", tiered(event, ctx, P3, P2, P2)
        if code in NEWS_HALT_CODES:
            return f"halt:{code}", tiered(event, ctx, P3, P2, P1)
        if code in LULD_CODES or status == "paused":
            return f"halt:{code or 'LUDP'}", tiered(event, ctx, P2, P1, P0)
        return f"halt:{code or 'unknown'}", tiered(event, ctx, P3, P2, P1)
