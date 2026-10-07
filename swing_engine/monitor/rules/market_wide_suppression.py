"""Suppress single-name alerts on market-wide circuit-breaker / FOMC / CPI days unless the name is held.
Also detects market-wide halt events themselves (MWC codes), which the pipeline turns into a suppression flag.

The flag is not a latch: `note_circuit_breaker` records the suppression together with the end of that
session (`ctx["market_suppressed_until"]`), and `suppression_active` compares it with `ctx["now"]`, so the
day after an MWC1 halt alerts flow again. Account and ops events (feed_dead, kill_switch) are never suppressed.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from swing_engine.core.interfaces import Rule
from swing_engine.core.models import Event
from swing_engine.core.registry import register

from ..constants import MARKET_WIDE_HALT_CODES
from ..hours import session_end
from ._common import P0, P2, is_held

SUPPRESSED_HIT = "market_wide_suppressed"
CIRCUIT_BREAKER_HIT = "market_wide_circuit_breaker"
EXEMPT_KINDS: frozenset[str] = frozenset({"account", "ops"})
SUPPRESSED_KEY = "market_suppressed"
SUPPRESSED_UNTIL_KEY = "market_suppressed_until"
REASON_KEY = "suppression_reason"


def note_circuit_breaker(ctx: dict[str, Any], now: datetime | None, reason: str = "circuit_breaker") -> None:
    """Record a market-wide halt: suppression lasts until the end of that session's extended hours."""
    ctx[SUPPRESSED_KEY] = True
    ctx[REASON_KEY] = reason
    ctx[SUPPRESSED_UNTIL_KEY] = session_end(now) if now is not None else None


def suppression_active(ctx: dict[str, Any], now: datetime | None) -> bool:
    """True while the recorded suppression has not expired (an entry without `until` never expires)."""
    if not ctx.get(SUPPRESSED_KEY):
        return False
    until = ctx.get(SUPPRESSED_UNTIL_KEY)
    return until is None or now is None or now < until


def expire_suppression(ctx: dict[str, Any], now: datetime | None) -> bool:
    """Clear an expired suppression; returns True when it was cleared."""
    if ctx.get(SUPPRESSED_KEY) and not suppression_active(ctx, now):
        ctx[SUPPRESSED_KEY] = False
        ctx.pop(SUPPRESSED_UNTIL_KEY, None)
        ctx.pop(REASON_KEY, None)
        return True
    return False


@register("rule", "market_wide_suppression")
class MarketWideSuppression(Rule):
    name = "market_wide_suppression"

    def evaluate(self, event: Event, ctx: dict[str, Any]) -> tuple[str, str] | None:
        if event.kind == "halt":
            code = str(event.meta.get("reason_code") or event.meta.get("code") or "").upper()
            if code in MARKET_WIDE_HALT_CODES:
                return CIRCUIT_BREAKER_HIT, P2
        if event.kind in EXEMPT_KINDS or not suppression_active(ctx, ctx.get("now")):
            return None
        if is_held(event, ctx):
            return None
        event.meta[REASON_KEY] = ctx.get(REASON_KEY, "market_wide")
        return SUPPRESSED_HIT, P0
