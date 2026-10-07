"""Index-inclusion headlines ("Set to Join S&P 500", "to be added to the Nasdaq-100")."""
from __future__ import annotations

from typing import Any

from swing_engine.core.interfaces import Rule
from swing_engine.core.models import Event
from swing_engine.core.registry import register

from ..constants import INDEX_INCLUSION_PHRASES
from ._common import P2

_INDEX_WORDS = ("s&p", "nasdaq-100", "nasdaq 100", "russell", "dow jones")
_WEAK_PHRASES = ("will replace", "to replace")


def is_index_inclusion(title: str) -> bool:
    t = title.lower()
    for phrase in INDEX_INCLUSION_PHRASES:
        if phrase in t:
            if phrase in _WEAK_PHRASES and not any(w in t for w in _INDEX_WORDS):
                continue
            return True
    return False


@register("rule", "index_inclusion")
class IndexInclusion(Rule):
    name = "index_inclusion"

    def evaluate(self, event: Event, ctx: dict[str, Any]) -> tuple[str, str] | None:
        if event.kind != "news" or not event.symbols:
            return None
        if is_index_inclusion(event.title):
            return "index_inclusion", P2
        return None
