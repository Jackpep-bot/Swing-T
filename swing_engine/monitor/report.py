"""Summaries over the event log: counts by source/kind/priority/rule, top symbols, alert delivery stats."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from typing import Any

from swing_engine.core.config import ROOT, DataConfig

from .constants import PRIORITY_RANK
from .eventlog import EventLog

DEFAULT_EVENT_LOG = str(ROOT / DataConfig().event_log_path)  # settings.data.event_log_path default, CWD-independent

HOURS_PER_DAY = 24
TOP_N = 15


def report(days: float = 1.0, eventlog: EventLog | None = None, path: str | None = None, now: datetime | None = None) -> dict[str, Any]:
    log_ = eventlog or EventLog(path or DEFAULT_EVENT_LOG)
    hours = days * HOURS_PER_DAY
    events = log_.recent(hours, now=now)
    alerts = log_.recent_alerts(hours, now=now)
    by_source: Counter[str] = Counter(e.source for e in events)
    by_kind: Counter[str] = Counter(e.kind for e in events)
    by_priority: Counter[str] = Counter(str(e.priority) for e in events)
    by_rule: Counter[str] = Counter(h for e in events for h in e.rule_hits)
    by_symbol: Counter[str] = Counter(s for e in events for s in e.symbols)
    delivered = [a for a in alerts if a["delivered"]]
    notable = sorted(
        (e for e in events if PRIORITY_RANK[str(e.priority)] >= PRIORITY_RANK["P2"]),
        key=lambda e: (-PRIORITY_RANK[str(e.priority)], e.ts_received),
    )
    return {
        "days": days,
        "events": len(events),
        "by_source": dict(by_source),
        "by_kind": dict(by_kind),
        "by_priority": dict(by_priority),
        "top_rules": by_rule.most_common(TOP_N),
        "top_symbols": by_symbol.most_common(TOP_N),
        "alerts": len(alerts),
        "alerts_delivered": len(delivered),
        "alert_channels": dict(Counter(c for a in delivered for c in json.loads(a["channels"]))),
        "notable": [
            {"ts": e.ts_received.isoformat(), "priority": str(e.priority), "symbols": e.symbols,
             "title": e.title[:100], "rule_hits": e.rule_hits, "event_id": e.event_id,
             "rating": e.meta.get("rating")}  # event_id: what `swing monitor rate <event_id> <rating>` takes
            for e in notable[:TOP_N]
        ],
    }


def format_report(r: dict[str, Any]) -> str:
    lines = [f"Monitor report: last {r['days']}d, {r['events']} events, {r['alerts']} alerts ({r['alerts_delivered']} delivered)"]
    lines.append("by source: " + ", ".join(f"{k}={v}" for k, v in sorted(r["by_source"].items())))
    lines.append("by kind:   " + ", ".join(f"{k}={v}" for k, v in sorted(r["by_kind"].items())))
    lines.append("by prio:   " + ", ".join(f"{k}={v}" for k, v in sorted(r["by_priority"].items())))
    if r["top_rules"]:
        lines.append("rules:     " + ", ".join(f"{k}={v}" for k, v in r["top_rules"]))
    if r["top_symbols"]:
        lines.append("symbols:   " + ", ".join(f"{k}={v}" for k, v in r["top_symbols"]))
    if r["alert_channels"]:
        lines.append("channels:  " + ", ".join(f"{k}={v}" for k, v in sorted(r["alert_channels"].items())))
    for n in r["notable"]:
        rated = f" rated={n['rating']}" if n.get("rating") else ""
        lines.append(
            f"  {n['priority']} {n['ts'][:16]} {' '.join(n['symbols'][:3])}: {n['title']} [{','.join(n['rule_hits'])}]"
            f" id={n.get('event_id', '?')}{rated}"
        )
    return "\n".join(lines)
