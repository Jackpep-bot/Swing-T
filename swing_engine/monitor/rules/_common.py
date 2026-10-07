"""Shared helpers for stage-1 rules (not a rule module; the leading underscore keeps it out of discovery)."""
from __future__ import annotations

from typing import Any

from swing_engine.core.models import Event

from ..constants import GAP_PCT_DEFAULT, PRIORITY_RANK, RVOL_GATE_DEFAULT

P0, P1, P2, P3 = "P0", "P1", "P2", "P3"


def held_symbols(ctx: dict[str, Any]) -> set[str]:
    return {s.upper() for s in ctx.get("held", ())}


def watch_symbols(ctx: dict[str, Any]) -> set[str]:
    return {s.upper() for s in ctx.get("watchlist", ())}


def is_held(event: Event, ctx: dict[str, Any]) -> bool:
    return bool(held_symbols(ctx) & {s.upper() for s in event.symbols})


def is_watched(event: Event, ctx: dict[str, Any]) -> bool:
    return bool(watch_symbols(ctx) & {s.upper() for s in event.symbols})


def tiered(event: Event, ctx: dict[str, Any], held: str, watched: str, other: str) -> str:
    if is_held(event, ctx):
        return held
    if is_watched(event, ctx):
        return watched
    return other


def max_priority(a: str, b: str) -> str:
    return a if PRIORITY_RANK[a] >= PRIORITY_RANK[b] else b


def setting(ctx: dict[str, Any], name: str, default: float) -> float:
    s = ctx.get("settings")
    if s is None:
        return default
    val = getattr(s, name, None) if not isinstance(s, dict) else s.get(name)
    return float(val) if val is not None else default


def rvol_gate(ctx: dict[str, Any]) -> float:
    return setting(ctx, "rvol_gate", RVOL_GATE_DEFAULT)


def gap_gate(ctx: dict[str, Any]) -> float:
    return setting(ctx, "gap_pct_alert", GAP_PCT_DEFAULT)


def form_type(event: Event) -> str:
    return str(event.meta.get("form_type") or event.meta.get("form") or "").upper().strip()
