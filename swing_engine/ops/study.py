"""Daily auto-study (docs/proposals/video-model-plan.md, P0 item 3): one markdown file per session, written from
the ``events`` table (ops.receipts) and nothing else. Counts per strategy, each fire's chain lineage, refusals by
step and reason, graded outcomes in gross and net R, and what the store covered that day.

No LLM: every word and number is produced by this module, and the output is sorted so a re-run of the same day
writes the same bytes. Reading only: nothing here feeds back into sizing, routing or execution.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import structlog

from swing_engine.core.config import ROOT, Settings
from swing_engine.ops.receipts import EVENTS_TABLE, EXIT, FIRE, OUTCOME, REFUSAL

log = structlog.get_logger(__name__)

MAX_EXAMPLES = 5  # refusal examples listed per (step, reason)
COVERAGE_LOOKBACK_DAYS = 7  # a pre-open run is stamped with the run date; its bars end at the previous session
NONE = "none"
DASH = "-"
BARS_TABLE, BREADTH_TABLE = "bars", "breadth"
BREADTH_FIELDS = ("pct_above_50", "pct_above_200", "advances", "declines", "new_highs", "new_lows")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


# ---------------------------------------------------------------------------------------------------- reading
def study_days(store: Any) -> list[date]:
    """Every distinct ``as_of`` in the events table, oldest first."""
    if not store.has_table(EVENTS_TABLE):
        return []
    return [pd.Timestamp(d).date() for d in store.sql(f"SELECT DISTINCT as_of FROM {EVENTS_TABLE} ORDER BY 1")["as_of"]]


def day_events(store: Any, as_of: date) -> list[dict[str, Any]]:
    """The day's events with ``payload`` parsed, in a stable order: every row stamped ``as_of`` plus outcome rows
    whose payload ``exit_date`` is that day."""
    if not store.has_table(EVENTS_TABLE):
        return []
    # the payload is json.dumps(sort_keys=True) text (receipts.make_event), so the exit date can be matched as text
    frame = store.sql(
        f"SELECT * FROM {EVENTS_TABLE} WHERE as_of = ? OR (kind = ? AND payload LIKE ?)",
        [as_of, OUTCOME, f'%"exit_date": "{as_of.isoformat()}"%'],
    )
    rows = []
    for rec in frame.to_dict("records"):
        try:
            payload = json.loads(rec["payload"] or "{}")
        except (TypeError, ValueError):
            payload = {}
        rows.append({**rec, "payload": payload if isinstance(payload, dict) else {}})
    return sorted(rows, key=lambda r: tuple(str(r[k]) for k in ("kind", "strategy", "symbol", "step", "reason", "event_id")))


def counts(events: list[dict[str, Any]]) -> dict[str, int]:
    """Fires, refusals and outcomes of the day (what the Telegram line quotes)."""
    by = Counter(e["kind"] for e in events)
    return {"fires": by[FIRE], "refusals": by[REFUSAL], "outcomes": by[OUTCOME]}


# ---------------------------------------------------------------------------------------------------- formatting
def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float) or value != value:  # NaN != NaN
        return None
    return float(value)


def _f(value: Any, spec: str = ".2f") -> str:
    v = _num(value)
    return DASH if v is None else format(v, spec)


def _table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    return out + ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]


def _name(strategy: Any) -> str:
    return str(strategy) or "(no strategy)"


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


# ---------------------------------------------------------------------------------------------------- sections
def _header(events: list[dict[str, Any]]) -> str:
    sigs = sorted({str(e["engine_sig"]) for e in events if e["engine_sig"]})
    sources = sorted({str(e["source"]) for e in events if e["source"]})
    seen = f"Engine signature(s) seen: {', '.join(f'`{s}`' for s in sigs) or NONE}"
    if sources:
        seen += f" (source: {', '.join(sources)})"
    return (f"{seen}. R values are gross AND net of modelled costs (research.costs); net R is null, shown as "
            f"`{DASH}`, where the receipt says no cost applies or the entry never filled.")


def _regime(store: Any, settings: Settings, as_of: date, events: list[dict[str, Any]]) -> list[str]:
    seen = Counter(str(e["payload"]["regime"]) for e in events
                   if e["kind"] in (FIRE, REFUSAL) and e["payload"].get("regime"))
    if seen:
        text = ", ".join(f"{name} ({n} receipts)" for name, n in sorted(seen.items(), key=lambda kv: (-kv[1], kv[0])))
    else:  # no receipt carried it: the scan's saved routing for the day (ops.nightly REGIME_KIND)
        saved: Any = {}
        try:
            from swing_engine.ops.nightly import REGIME_KIND, run_file

            path = run_file(settings, REGIME_KIND, as_of)
            saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except Exception as e:  # noqa: BLE001 - an unreadable run file is the same as none
            log.info("study.regime_file_unavailable", error=f"{type(e).__name__}: {e}")
        text = str(saved.get("regime")) if isinstance(saved, dict) and saved.get("regime") else "not recorded"
    lines = [f"Market regime: {text}"]
    try:
        if store.has_table(BREADTH_TABLE):
            row = store.sql(f"SELECT * FROM {BREADTH_TABLE} WHERE date = ?", [as_of]).to_dict("records")
            fields = [f"{k} {_f(row[0][k], 'g' if float(row[0][k]).is_integer() else '.1f')}"
                      for k in BREADTH_FIELDS if row and _num(row[0].get(k)) is not None]
            if fields:
                lines.append(f"Breadth: {', '.join(fields)}")
    except Exception as e:  # noqa: BLE001 - breadth is context, not the study
        log.info("study.breadth_unavailable", error=f"{type(e).__name__}: {e}")
    return lines


def _counts_section(events: list[dict[str, Any]]) -> list[str]:
    lines = ["## Counts per strategy", ""]
    if not events:
        return [*lines, NONE, ""]
    cols = ("fires", "shadow", "refusals", "exits", "outcomes")
    table: dict[str, Counter[str]] = {}
    for e in events:
        row = table.setdefault(_name(e["strategy"]), Counter())
        row[{FIRE: "fires", REFUSAL: "refusals", EXIT: "exits", OUTCOME: "outcomes"}.get(e["kind"], "other")] += 1
        if e["kind"] == FIRE and e["payload"].get("shadow"):
            row["shadow"] += 1
    rows = [[name, *(table[name][c] for c in cols)] for name in sorted(table)]
    rows.append(["**total**", *(sum(t[c] for t in table.values()) for c in cols)])
    return [*lines, *_table(["strategy", "fires", "of which shadow-only", "refusals", "exits", "outcomes"], rows), ""]


def chain_line(event: dict[str, Any]) -> str:
    """``SYMBOL strategy long: regime X -> multiplier m -> entry E stop S target T (R:R r) -> size N -> order id``,
    built only from the payload fields the receipt has."""
    p = event["payload"]
    signal = p.get("signal") if isinstance(p.get("signal"), dict) else {}
    intent = p.get("intent") if isinstance(p.get("intent"), dict) else {}
    order = p.get("order") if isinstance(p.get("order"), dict) else {}
    side = signal.get("side") or intent.get("side")
    head = " ".join(str(x) for x in (event["symbol"], _name(event["strategy"]), side) if x)
    parts: list[str] = []
    if p.get("regime"):
        parts.append(f"regime {p['regime']}")
    if _num(p.get("multiplier")) is not None:
        parts.append(f"multiplier {p['multiplier']:g}")
    geometry = [f"{label} {_f(value)}" for label, value in (
        ("entry", signal.get("entry", intent.get("entry_limit"))), ("stop", signal.get("stop", intent.get("stop"))),
        ("target", signal.get("target", intent.get("target")))) if _num(value) is not None]
    if _num(signal.get("reward_risk")) is not None:
        geometry.append(f"(R:R {_f(signal['reward_risk'])})")
    if geometry:
        parts.append(" ".join(geometry))
    if _num(intent.get("qty")) is not None:
        parts.append(f"size {intent['qty']:g}")
    order_id = order.get("client_order_id") or p.get("client_order_id") or intent.get("client_order_id")
    if p.get("shadow"):
        parts.append("shadow only, no order")
    elif order_id:
        parts.append(f"order {order_id}")
    return f"{head}: {' -> '.join(parts) or 'no chain recorded'}"


def _fires_section(events: list[dict[str, Any]]) -> list[str]:
    fires = [e for e in events if e["kind"] == FIRE]
    return ["## Fires: chain lineage", "", *([f"- {chain_line(e)}" for e in fires] or [NONE]), ""]


def _refusals_section(events: list[dict[str, Any]]) -> list[str]:
    lines = ["## Refusals by step", ""]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for e in events:
        if e["kind"] == REFUSAL:  # numbers out of the reason, so "reward_risk 1.00 below min 2.0" is one reason; an example repeats the reason only when it differs
            groups.setdefault((str(e["step"]), _NUMBER.sub("N", str(e["reason"]))), []).append(e)
    if not groups:
        return [*lines, NONE, ""]
    per_step = Counter()
    for (step, _), rows in groups.items():
        per_step[step] += len(rows)
    for step in sorted(per_step):
        lines.append(f"- **{step}**: {per_step[step]}")
        reasons = sorted((k for k in groups if k[0] == step), key=lambda k: (-len(groups[k]), k[1]))
        for key in reasons:
            rows = groups[key]
            lines.append(f"  - {len(rows)} x {key[1]}")
            for e in rows[:MAX_EXAMPLES]:
                who = " ".join(str(x) for x in (e["symbol"], _name(e["strategy"])) if x)
                lines.append(f"    - {who}" + ("" if e["reason"] == key[1] else f": {e['reason']}"))
    return [*lines, ""]


def _exits_section(events: list[dict[str, Any]]) -> list[str]:
    exits = [f"- {e['symbol']} {_name(e['strategy'])} ({e['step']}): {e['reason']}" for e in events if e["kind"] == EXIT]
    return ["## Exits", "", *(exits or [NONE]), ""]


def _outcomes_section(events: list[dict[str, Any]]) -> list[str]:
    lines = ["## Outcomes", ""]
    outcomes = [e for e in events if e["kind"] == OUTCOME]
    if not outcomes:
        return [*lines, NONE, ""]

    def horizon(e: dict[str, Any]) -> float:
        return _num(e["payload"].get("horizon")) or 0.0

    groups: dict[tuple[str, float], list[dict[str, Any]]] = {}
    for e in outcomes:
        groups.setdefault((_name(e["strategy"]), horizon(e)), []).append(e)
    summary = []
    for (name, h), rows in sorted(groups.items()):
        gross = [g for e in rows if (g := _num(e["payload"].get("gross_r"))) is not None]
        planned = [g for e in rows if (g := _num(e["payload"].get("gross_r_planned"))) is not None]
        net = [n for e in rows if (n := _num(e["payload"].get("net_r"))) is not None]
        wins = sum(g > 0 for g in gross)
        summary.append([name, f"{h:g}d", len(rows), len(gross),
                        f"{wins / len(gross):.0%}" if gross else DASH, _f(_mean(gross), "+.2f"), _f(_mean(planned), "+.2f"),
                        _f(_mean(net), "+.2f")])
    notes = Counter(str(e["payload"]["cost_note"]) for e in outcomes if e["payload"].get("cost_note"))
    lines += [
        "One row per strategy and grading horizon (a signal graded at several horizons appears once in each). "
        "`filled` is the outcomes with a gross R (the entry traded); win rate and mean gross R are over those. "
        "Gross R is per filled risk (the shadow ledger's R); planned R is the same trade per planned risk (signal "
        "entry to stop); net R is planned R minus the modelled cost, so compare net with planned, not with gross.", "",
        *_table(["strategy", "horizon", "n", "filled", "win rate", "mean gross R", "mean planned R", "mean net R"],
                summary), "",
        "Cost basis: " + ("; ".join(f"{n} x {note}" for note, n in sorted(notes.items())) or "not recorded"), "",
    ]
    rows = [[e["symbol"], _name(e["strategy"]), f"{horizon(e):g}d", e["payload"].get("signal_as_of") or DASH,
             e["payload"].get("exit_date") or DASH, e["reason"], _f(e["payload"].get("gross_r"), "+.2f"),
             _f(e["payload"].get("gross_r_planned"), "+.2f"), _f(e["payload"].get("cost_r"), ".2f"),
             _f(e["payload"].get("net_r"), "+.2f"), "yes" if e["payload"].get("taken") else "no"]
            for e in sorted(outcomes, key=lambda e: (_name(e["strategy"]), str(e["symbol"]), horizon(e),
                                                    str(e["payload"].get("signal_as_of"))))]
    return [*lines, *_table(["symbol", "strategy", "horizon", "signal", "exit", "result", "gross R", "planned R",
                             "cost R", "net R", "taken"], rows), ""]


def _coverage_section(store: Any, as_of: date, events: list[dict[str, Any]]) -> list[str]:
    lines = ["## Coverage", ""]
    found: list[str] = []
    try:
        if store.has_table(BARS_TABLE):
            from swing_engine.data._common import TZ, session_ts

            lo, hi = session_ts(as_of - timedelta(days=COVERAGE_LOOKBACK_DAYS)), session_ts(as_of) + timedelta(days=1)
            last = store.sql(
                f"SELECT ts, count(*) AS n, count(DISTINCT symbol) AS symbols FROM {BARS_TABLE} "
                "WHERE ts >= ? AND ts < ? GROUP BY ts ORDER BY ts DESC LIMIT 1", [lo.to_pydatetime(), hi.to_pydatetime()],
            ).to_dict("records")
            if last:
                session = pd.Timestamp(last[0]["ts"]).tz_convert(TZ).date()
                found.append(f"- bars: {int(last[0]['n']):,} daily bars for {int(last[0]['symbols']):,} symbols in the "
                             f"store's latest session on or before this date ({session})")
        if store.has_table(BREADTH_TABLE):
            n = store.sql(f"SELECT n_symbols FROM {BREADTH_TABLE} WHERE date = ?", [as_of])["n_symbols"].tolist()
            if n and _num(n[0]) is not None:
                found.append(f"- symbols scanned (the screened universe behind the breadth row): {int(n[0]):,}")
    except Exception as e:  # noqa: BLE001 - coverage is a courtesy; the study is the receipts
        log.info("study.coverage_unavailable", error=f"{type(e).__name__}: {e}")
    symbols = {str(e["symbol"]) for e in events if e["symbol"]}
    if symbols:
        found.append(f"- symbols with at least one receipt: {len(symbols):,}")
    return [*lines, *(found or [NONE]), ""]


# ---------------------------------------------------------------------------------------------------- public
def build_study(store: Any, settings: Settings, as_of: date) -> str:
    """The study for ``as_of`` as markdown. Deterministic: the same events give the same text."""
    events = day_events(store, as_of)
    lines = [
        f"# Daily study: {as_of.isoformat()}", "",
        "_Generated by `swing_engine.ops.study` from the decision receipts (the `events` table). Tables and "
        "rule-built sentences only; no LLM._", "",
        _header(events), "",
        *_regime(store, settings, as_of, events), "",
        *_counts_section(events),
        *_fires_section(events),
        *_refusals_section(events),
        *_exits_section(events),
        *_outcomes_section(events),
        *_coverage_section(store, as_of, events),
    ]
    return "\n".join(lines).rstrip("\n") + "\n"


def study_path(settings: Settings, as_of: date, root: Path | None = None) -> Path:
    """``<root or repo>/<settings.data.studies_dir>/YYYY-MM-DD.md`` (an absolute studies_dir is used as is)."""
    return (root if root is not None else ROOT) / Path(settings.data.studies_dir).expanduser() / f"{as_of.isoformat()}.md"


def relative_path(path: Path) -> str:
    """Repo-relative when the file is inside the repo (what the Telegram line and the dashboard name)."""
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def write_study(store: Any, settings: Settings, as_of: date, root: Path | None = None) -> Path:
    path = study_path(settings, as_of, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_study(store, settings, as_of), encoding="utf-8")
    log.info("ops.study.written", path=str(path))
    return path


__all__ = ["build_study", "chain_line", "counts", "day_events", "relative_path", "study_days", "study_path", "write_study"]
