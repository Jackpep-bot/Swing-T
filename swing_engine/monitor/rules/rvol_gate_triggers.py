"""Bar-derived triggers behind the RVOL gate: pre-market gap, 52w/ATH breakout, Stockbee burst (feature only),
PEG survivors and adverse moves on holdings. Thresholds come from settings.monitor (rvol_gate, gap_pct_alert) with
constants as fallback.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from swing_engine.core.interfaces import Rule
from swing_engine.core.models import Event
from swing_engine.core.registry import register

from ..constants import (
    ADVERSE_MOVE_PCT,
    BREAKOUT_VOL_RATIO,
    BURST_CLOSE_RATIO,
    BURST_MIN_VOLUME,
    NEWS_TAG_WINDOW_HOURS,
    RVOL_ESCALATE,
    TRIGGER_ADVERSE,
    TRIGGER_BREAKOUT_52W,
    TRIGGER_BURST,
    TRIGGER_GAP,
    TRIGGER_PEG,
)
from ._common import P0, P1, P2, P3, gap_gate, is_held, rvol_gate


def _num(meta: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(meta.get(key, default))
    except (TypeError, ValueError):
        return default


def news_tagged(event: Event, ctx: dict[str, Any]) -> bool:
    if event.meta.get("news_tagged"):
        return True
    tagged = ctx.get("news_tagged") or {}
    now = ctx.get("now") or event.ts_received
    window = timedelta(hours=NEWS_TAG_WINDOW_HOURS)
    for sym in event.symbols:
        ts = tagged.get(sym.upper())
        if ts is not None and now - ts <= window:
            return True
    return False


@register("rule", "rvol_gate_triggers")
class RvolGateTriggers(Rule):
    name = "rvol_gate_triggers"

    def evaluate(self, event: Event, ctx: dict[str, Any]) -> tuple[str, str] | None:
        if event.kind != "bar_trigger":
            return None
        trig = str(event.meta.get("trigger", "")).lower()
        rvol = _num(event.meta, "rvol")
        gate = rvol_gate(ctx)
        if trig == TRIGGER_ADVERSE:
            pct = _num(event.meta, "pct")
            if is_held(event, ctx) and pct <= -ADVERSE_MOVE_PCT:
                return "adverse_move", P3
            return None
        if trig == TRIGGER_BURST:
            ratio = _num(event.meta, "close_ratio")
            vol = _num(event.meta, "volume")
            prev_vol = _num(event.meta, "prev_volume")
            if ratio >= BURST_CLOSE_RATIO and vol > prev_vol and vol >= BURST_MIN_VOLUME:
                return "stockbee_burst", P0  # feature only, never alerted
            return None
        if rvol < gate:
            return None
        if trig == TRIGGER_GAP:
            gap = _num(event.meta, "gap_pct")
            if abs(gap) < gap_gate(ctx):
                return None
            event.meta["rvol_escalated"] = rvol >= RVOL_ESCALATE
            return "premarket_gap", P2 if news_tagged(event, ctx) else P1
        if trig == TRIGGER_BREAKOUT_52W:
            if _num(event.meta, "vol_ratio") < BREAKOUT_VOL_RATIO:
                return None
            return "breakout_52w", P2
        if trig == TRIGGER_PEG:
            return "peg_survivor", P2
        return None
