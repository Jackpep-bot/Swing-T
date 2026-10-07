"""Suppress single-name alerts on market-wide circuit-breaker / FOMC / CPI days unless the name is held.
Also detects market-wide halt events themselves (MWC codes), which the pipeline turns into a suppression flag.
"""
from __future__ import annotations

from typing import Any

from swing_engine.core.interfaces import Rule
from swing_engine.core.models import Event
from swing_engine.core.registry import register

from ..constants import MARKET_WIDE_HALT_CODES
from ._common import P0, P2, is_held

SUPPRESSED_HIT = "market_wide_suppressed"
CIRCUIT_BREAKER_HIT = "market_wide_circuit_breaker"


@register("rule", "market_wide_suppression")
class MarketWideSuppression(Rule):
    name = "market_wide_suppression"

    def evaluate(self, event: Event, ctx: dict[str, Any]) -> tuple[str, str] | None:
        if event.kind == "halt":
            code = str(event.meta.get("reason_code") or event.meta.get("code") or "").upper()
            if code in MARKET_WIDE_HALT_CODES:
                return CIRCUIT_BREAKER_HIT, P2
        if not ctx.get("market_suppressed"):
            return None
        if event.kind == "account" or is_held(event, ctx):
            return None
        event.meta["suppression_reason"] = ctx.get("suppression_reason", "market_wide")
        return SUPPRESSED_HIT, P0
