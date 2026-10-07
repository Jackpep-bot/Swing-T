"""8-K item rule with the full item list and severity tiers (constants.EIGHTK_*)."""
from __future__ import annotations

import re
from typing import Any

from swing_engine.core.interfaces import Rule
from swing_engine.core.models import Event
from swing_engine.core.registry import register

from ..constants import EIGHTK_ITEMS, EIGHTK_MAJOR, EIGHTK_MINOR, EIGHTK_SEVERE
from ._common import P0, P1, P2, P3, form_type, tiered

_ITEM_RE = re.compile(r"\bItem\s+(\d{1,2}\.\d{2})\b", re.IGNORECASE)


def parse_items(text: str) -> list[str]:
    seen: list[str] = []
    for m in _ITEM_RE.finditer(text or ""):
        item = m.group(1)
        if item in EIGHTK_ITEMS and item not in seen:
            seen.append(item)
    return seen


def item_severity(item: str) -> str:
    if item in EIGHTK_SEVERE:
        return "severe"
    if item in EIGHTK_MAJOR:
        return "major"
    if item in EIGHTK_MINOR:
        return "minor"
    return "minor"


_SEVERITY_ORDER = {"severe": 2, "major": 1, "minor": 0}


@register("rule", "eightk_items")
class EightKItems(Rule):
    name = "eightk_items"

    def evaluate(self, event: Event, ctx: dict[str, Any]) -> tuple[str, str] | None:
        if event.kind != "filing" or not form_type(event).startswith("8-K"):
            return None
        items = [str(i) for i in event.meta.get("items", []) if str(i) in EIGHTK_ITEMS]
        if not items:
            items = parse_items(f"{event.title}\n{event.body}")
        if not items:
            return "8k:unknown", tiered(event, ctx, P2, P1, P0)
        event.meta["items"] = items
        top = max(items, key=lambda i: _SEVERITY_ORDER[item_severity(i)])
        sev = item_severity(top)
        event.meta["eightk_severity"] = sev
        if sev == "severe":
            return f"8k:{top}", tiered(event, ctx, P3, P2, P1)
        if sev == "major":
            return f"8k:{top}", tiered(event, ctx, P2, P2, P1)
        return f"8k:{top}", tiered(event, ctx, P1, P1, P0)
