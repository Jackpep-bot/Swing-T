"""Any event touching a held or watchlisted symbol gets flagged; held => push, watchlist => digest."""
from __future__ import annotations

from typing import Any

from swing_engine.core.interfaces import Rule
from swing_engine.core.models import Event
from swing_engine.core.registry import register

from ._common import P1, P2, is_held, is_watched


@register("rule", "watchlist_hit")
class WatchlistHit(Rule):
    name = "watchlist_hit"

    def evaluate(self, event: Event, ctx: dict[str, Any]) -> tuple[str, str] | None:
        if not event.symbols:
            return None
        if is_held(event, ctx):
            return "held_hit", P2
        if is_watched(event, ctx):
            return "watchlist_hit", P1
        return None
