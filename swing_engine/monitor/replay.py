"""Replay stage-1 rules over logged events (no delivery, no classifier). Useful after changing a threshold:
shows which events would change priority under the current rule set.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from swing_engine.core import registry
from swing_engine.core.config import ROOT, DataConfig
from swing_engine.core.interfaces import Rule
from swing_engine.core.models import Event

from .constants import PRIORITY_RANK
from .eventlog import EventLog
from .rules.market_wide_suppression import CIRCUIT_BREAKER_HIT, SUPPRESSED_HIT

DEFAULT_EVENT_LOG = str(ROOT / DataConfig().event_log_path)  # settings.data.event_log_path default, CWD-independent

HOURS_PER_DAY = 24


def load_rules(names: Sequence[str] | None = None) -> list[Rule]:
    names = list(names) if names else registry.names("rule")
    return [registry.get("rule", n)() for n in names]


def evaluate_rules(event: Event, rules: Sequence[Rule], ctx: dict[str, Any]) -> tuple[str, list[str]]:
    """Pure re-run of the pipeline's rule stage (same priority-combination semantics)."""
    hits: list[str] = []
    best = "P0"
    suppressed = False
    ctx["now"] = event.ts_received
    for rule in rules:
        out = rule.evaluate(event, ctx)
        if out is None:
            continue
        hit, prio = out
        hits.append(hit)
        if hit == SUPPRESSED_HIT:
            suppressed = True
            continue
        if hit == CIRCUIT_BREAKER_HIT:
            ctx["market_suppressed"] = True
        if PRIORITY_RANK[prio] > PRIORITY_RANK[best]:
            best = prio
    return ("P0" if suppressed else best), hits


def replay(
    days: float = 1.0,
    rules: Sequence[str] | Sequence[Rule] | None = None,
    eventlog: EventLog | None = None,
    path: str | None = None,
    ctx: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    log_ = eventlog or EventLog(path or DEFAULT_EVENT_LOG)
    rule_objs: list[Rule]
    if rules and all(isinstance(r, Rule) for r in rules):
        rule_objs = list(rules)  # type: ignore[arg-type]
    else:
        rule_objs = load_rules(rules)  # type: ignore[arg-type]
    ctx = dict(ctx or {})
    ctx.setdefault("held", set())
    ctx.setdefault("watchlist", set())
    ctx.setdefault("news_tagged", {})
    ctx.setdefault("form4_history", {})
    rows: list[dict[str, Any]] = []
    changed = 0
    for e in log_.recent(days * HOURS_PER_DAY, now=now):
        ev = e.model_copy(deep=True)
        ev.rule_hits = []
        prio, hits = evaluate_rules(ev, rule_objs, ctx)
        stored_hits = [h for h in e.rule_hits if not h.startswith("haiku:")]
        diff = prio != str(e.priority) or sorted(hits) != sorted(stored_hits)
        changed += int(diff)
        rows.append(
            {
                "event_id": e.event_id, "symbols": e.symbols, "title": e.title[:80], "stored_priority": str(e.priority),
                "replay_priority": prio, "stored_hits": stored_hits, "replay_hits": hits, "changed": diff,
            }
        )
    return {"days": days, "rules": [r.name for r in rule_objs], "events": len(rows), "changed": changed, "rows": rows}


def format_replay(r: dict[str, Any], only_changed: bool = True) -> str:
    lines = [f"Replay: {r['events']} events over {r['days']}d with rules {', '.join(r['rules'])}; {r['changed']} changed"]
    for row in r["rows"]:
        if only_changed and not row["changed"]:
            continue
        lines.append(
            f"  {row['stored_priority']}->{row['replay_priority']} {' '.join(row['symbols'][:3])}: {row['title']}"
            f" [{','.join(row['stored_hits'])}] -> [{','.join(row['replay_hits'])}]"
        )
    return "\n".join(lines)
