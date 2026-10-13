"""Decision receipts: the append-only ``events`` table (docs/proposals/video-model-plan.md, P0 item 1).

One row per decision the engine made: a ``fire`` (a signal that became an order, or a shadow-only signal with
``payload.shadow``), a ``refusal`` (which step said no, with the inputs it saw), an ``exit`` action, a graded
shadow ``outcome`` (gross and net R), or a ``note``. Every row carries ``engine_sig`` (core.signature) so a
decision can be tied to the code and config that made it. Recording only: nothing here feeds back into sizing,
routing or execution, and a failed write is logged and swallowed (``write_events`` never raises).

Event ids are uuid5 of the natural key (kind, lane, strategy, symbol, step, key), so re-running a night or the
backfill inserts nothing twice and the first record of a decision is the one kept.
"""
from __future__ import annotations

import json
import math
import re
import uuid
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pandas as pd
import structlog

from swing_engine.core.config import Settings
from swing_engine.core.signature import engine_signature

log = structlog.get_logger(__name__)

EVENTS_TABLE = "events"
EVENTS_SCHEMA: dict[str, str] = {
    "event_id": "VARCHAR",  # uuid hex
    "ts": "TIMESTAMPTZ",  # when the row was written (UTC)
    "as_of": "DATE",  # session the decision belongs to (signal date; exit date for outcomes and exits)
    "kind": "VARCHAR",  # KINDS
    "lane": "VARCHAR",  # 'swing' (the intraday lane reuses the table)
    "strategy": "VARCHAR",
    "symbol": "VARCHAR",
    "step": "VARCHAR",  # which gate / step decided
    "reason": "VARCHAR",  # the engine's own reason string
    "payload": "VARCHAR",  # JSON: the inputs that decided it
    "engine_sig": "VARCHAR",
    "source": "VARCHAR",  # SOURCES
    "run_id": "VARCHAR",
}
FIRE, REFUSAL, OUTCOME, EXIT, NOTE = "fire", "refusal", "outcome", "exit", "note"
KINDS = (FIRE, REFUSAL, OUTCOME, EXIT, NOTE)
SOURCE_LIVE, SOURCE_REPLAY, SOURCE_BACKFILL = "live", "replay", "backfill"
SOURCES = (SOURCE_LIVE, SOURCE_REPLAY, SOURCE_BACKFILL)
LANE_SWING = "swing"
STEP_UNKNOWN = "unknown"  # backfilled refusals: the deciding step was not recorded before receipts existed
DEFAULT_STEP = "sizing"
ID_NAMESPACE = uuid.UUID("6f1d3c52-8f0a-5a44-9b57-0c9f6f0c5e11")
COST_LOOKBACK_DAYS = 60  # bars before the first signal for research.costs' spread window (as research.cards)
SIGNAL_DAY_SLACK_DAYS = 4  # a pre-open run stamps signals with the run date, the shadow ledger with the bar session

#: reason text (lower-cased substring) -> step; first match wins. The texts are the engine's existing reasons:
#: risk.sizing.size_signal_detail, ops.nightly, execution.autopilot / order_manager, research.replay skip buckets.
STEP_RULES: tuple[tuple[str, str], ...] = (
    ("kill switch", "kill_switch"),
    ("kill_switch", "kill_switch"),
    ("limit check failed", "limits"),
    ("max_new_orders_per_day", "daily_cap"),
    ("daily_order_cap", "daily_cap"),
    ("review", "review"),
    ("not allowed by the playbook", "router"),
    ("playbook table", "router"),
    ("multiplier 0", "router"),
    ("reward_risk", "reward_risk"),
    ("max open positions", "slot"),
    ("already has an open position", "slot"),
    ("symbol_busy", "slot"),
    ("stale_entry", "fill"),
    ("an exit for this symbol", "rule"),
    ("invalid intent", "rule"),
    ("approval required", "rule"),
)
#: execution.position_manager.ExitReason -> step of an executed exit action (anything else: 'rule')
EXIT_STEPS = {"time_stop": "time", "breakeven": "stop", "trail": "stop", "strategy_trail": "stop", "no_stop": "stop"}
#: research.shadow.Hit -> step of a graded outcome
OUTCOME_STEPS = {"target_hit": "target", "stop_hit": "stop", "time_exit": "time", "entry_skipped": "fill",
                 "delisted": "rule"}
_HIT_COLUMN = re.compile(r"^hit_(\d+)d$")


def step_for(reason: str, default: str = DEFAULT_STEP) -> str:
    """The step a refusal reason belongs to (``default`` when no rule matches: a sizer rejection)."""
    text = str(reason).lower()
    return next((step for needle, step in STEP_RULES if needle in text), default)


def stamp(settings: Settings, source: str = SOURCE_LIVE, run_id: str | None = None, lane: str = LANE_SWING) -> dict[str, str]:
    """The fields every event of one run shares; spread into :func:`make_event`."""
    return {"engine_sig": engine_signature(settings), "source": source, "run_id": run_id or uuid.uuid4().hex,
            "lane": lane}


def _jsonable(obj: Any) -> Any:
    if obj is None or obj is pd.NaT or obj is pd.NA:
        return None
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, Mapping):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple | set | frozenset):
        return [_jsonable(v) for v in obj]
    if hasattr(obj, "model_dump"):
        return _jsonable(obj.model_dump(mode="json"))
    if isinstance(obj, bool | int | str):
        return obj
    if hasattr(obj, "item"):  # numpy scalar
        return _jsonable(obj.item())
    return str(getattr(obj, "value", obj))


def event_id(kind: str, strategy: str, symbol: str, step: str, key: str, lane: str = LANE_SWING) -> str:
    """The deterministic id of the event with this natural key (a fire's key is its client order id)."""
    return uuid.uuid5(ID_NAMESPACE, "|".join([kind, lane, strategy, symbol, step, key])).hex


def cost_note(cost: float | None, bps: float | None) -> str:
    """Where a net R's cost came from (shared by outcome and exit-fill receipts)."""
    from swing_engine.research.cards import NET_SLIPPAGE_BPS_PER_SIDE

    if cost is None:
        return "gross only: no cost model for this row (short side, or the stop is not below the entry)"
    if bps is None:
        return f"default {NET_SLIPPAGE_BPS_PER_SIDE:g} bps per side (no per-signal cost data)"
    return "per-signal cost_bps (research.costs)"


def make_event(
    kind: str, step: str, reason: str, as_of: date, strategy: str | None = "", symbol: str | None = "",
    payload: Mapping[str, Any] | None = None, *, key: str | None = None, engine_sig: str, source: str = SOURCE_LIVE,
    run_id: str = "", lane: str = LANE_SWING,
) -> dict[str, Any]:
    """One ``events`` row. ``key`` completes the natural key (default: ``as_of``); pass the client order id for
    events that happen once per order."""
    strategy, symbol = strategy or "", symbol or ""
    return {
        "event_id": event_id(kind, strategy, symbol, step, key or as_of.isoformat(), lane), "ts": pd.Timestamp(datetime.now(UTC)), "as_of": as_of,
        "kind": kind, "lane": lane, "strategy": strategy, "symbol": symbol, "step": step, "reason": str(reason),
        "payload": json.dumps(_jsonable(payload or {}), sort_keys=True), "engine_sig": engine_sig, "source": source,
        "run_id": run_id,
    }


def write_events(store: Any, rows: Iterable[Mapping[str, Any]]) -> int:
    """Insert the rows whose ``event_id`` is not stored yet; returns how many were written. Never raises."""
    try:
        frame = pd.DataFrame(list(rows), columns=list(EVENTS_SCHEMA)).drop_duplicates("event_id")
        if frame.empty:
            return 0
        if store.has_table(EVENTS_TABLE):
            seen = store.sql(
                f"SELECT event_id FROM {EVENTS_TABLE} WHERE event_id IN (SELECT unnest(?))", [frame["event_id"].tolist()]
            )["event_id"]
            frame = frame.loc[~frame["event_id"].isin(set(seen))]
        return int(store.write_table(EVENTS_TABLE, frame, ["event_id"], schema=EVENTS_SCHEMA))
    except Exception as exc:  # noqa: BLE001 - a receipt must never break the run that produced it
        log.error("receipts.write_failed", error=f"{type(exc).__name__}: {exc}")
        return 0


def read_events(
    store: Any, *, as_of: date | None = None, strategy: str | None = None, symbol: str | None = None,
    kind: str | None = None, source: str | None = None, limit: int | None = None,
) -> pd.DataFrame:
    """Events newest first, filtered by equality on the given columns (``payload`` stays a JSON string)."""
    if not store.has_table(EVENTS_TABLE):
        return pd.DataFrame(columns=list(EVENTS_SCHEMA))
    filters = {"as_of": as_of, "strategy": strategy, "symbol": symbol, "kind": kind, "source": source}
    where = [f"{col} = ?" for col, value in filters.items() if value is not None]
    query = f"SELECT * FROM {EVENTS_TABLE}" + (f" WHERE {' AND '.join(where)}" if where else "")
    query += " ORDER BY ts DESC, event_id" + (f" LIMIT {int(limit)}" if limit else "")
    return store.sql(query, [v for v in filters.values() if v is not None])


# ----------------------------------------------------------------------------------------------- autopilot
def autopilot_events(
    report: Any, intents: Iterable[Any], exits: Iterable[Any] = (), context: Mapping[str, Any] | None = None,
    **st: str,
) -> list[dict[str, Any]]:
    """Events for one ``execution.autopilot.AutopilotReport``: a fire per submitted entry (``context`` maps
    client order id -> the chain that led to it: regime, multiplier, signal), a refusal per entry that a gate
    stopped, and one event per exit action."""
    chain = context or {}
    by_cid = {i.client_order_id: i for i in intents}
    actions = {(a.symbol, str(a.kind)): a for a in exits}
    mode = str(getattr(report.mode, "value", report.mode))
    base = {"mode": mode, "approved_by": report.approved_by, "broker": report.broker, "paper": report.paper}
    rows: list[dict[str, Any]] = []

    def entry(kind: str, step: str, reason: str, cid: str | None, symbol: str, strategy: str | None,
              once: bool, extra: Mapping[str, Any]) -> None:
        intent = by_cid.get(cid or "")
        day = getattr(intent, "signal_as_of", None) or report.as_of
        payload = {**chain.get(cid or "", {}), **base, "intent": intent, "client_order_id": cid, **extra}
        key = cid if once else f"{cid}|{report.as_of.isoformat()}"
        rows.append(make_event(kind, step, reason, day, strategy, symbol, payload, key=key, **st))

    for r in report.entries:
        status, cid = str(r.status), r.client_order_id
        if status == "submitted":
            order = {"client_order_id": cid, "broker_order_id": r.response.get("broker_order_id"),
                     "status": r.response.get("status")}
            entry(FIRE, "broker", "submitted", cid, r.symbol, r.strategy, True,
                  {"order": order, "limits": report.limits, "account": report.account})
        elif status == "error":
            entry(REFUSAL, "broker", r.reason, cid, r.symbol, r.strategy, True, {})
        elif status in ("vetoed", "capped", "refused"):
            step = {"vetoed": "review", "capped": "daily_cap"}.get(status) or step_for(r.reason, "rule")
            entry(REFUSAL, step, r.reason, cid, r.symbol, r.strategy, False,
                  {"new_orders_before": report.new_orders_before,
                   "max_new_orders_per_day": report.max_new_orders_per_day, "kill_switch": report.kill_switch})
        elif status in ("staged", "planned"):
            why = "staged for a human approver" if status == "staged" else "planned (dry run): nothing sent"
            entry(NOTE, "broker", why, cid, r.symbol, r.strategy, False, {})
    if mode == "aborted":  # nothing was planned: every intent of this run was declined by the abort
        for intent in by_cid.values():
            entry(REFUSAL, "broker", "; ".join(report.errors) or "autopilot aborted", intent.client_order_id,
                  intent.symbol, intent.strategy, False, {})

    for r in report.exits:
        status, action_kind = str(r.status), str(r.kind)
        why = r.reason.split(":")[0].strip()
        payload = {**base, "action": action_kind, "status": status, "client_order_id": r.client_order_id,
                   "response": r.response, "exit_action": actions.get((r.symbol, action_kind))}
        key = f"{report.as_of.isoformat()}|{action_kind}"
        if status == "done" and action_kind == "cancel_order":  # an entry cancelled unfilled
            step = "kill_switch" if why == "kill_switch" else "fill"
            rows.append(make_event(REFUSAL, step, r.reason, report.as_of, r.strategy, r.symbol, payload,
                                   key=r.client_order_id or key, **st))
        elif status == "done":
            step = "stop" if action_kind in ("replace_stop", "place_stop") else EXIT_STEPS.get(why, "rule")
            rows.append(make_event(EXIT, step, r.reason, report.as_of, r.strategy, r.symbol, payload, key=key, **st))
        else:  # refused / error / flagged / staged / planned: nothing changed at the broker
            step = step_for(r.reason, "broker") if status in ("refused", "error") else "rule"
            rows.append(make_event(NOTE, step, r.reason, report.as_of, r.strategy, r.symbol, payload, key=key, **st))
    return rows


def autopilot_recorder(
    store: Any, settings: Settings, context: Mapping[str, Any] | None = None, *, run_id: str | None = None,
    source: str = SOURCE_LIVE,
) -> Callable[[Any, list[Any], list[Any]], None]:
    """The ``receipts`` callback for ``execution.autopilot.run_autopilot`` writing into ``store``."""
    def record(report: Any, intents: list[Any], exits: list[Any]) -> None:
        write_events(store, autopilot_events(report, intents, exits, context, **stamp(settings, source, run_id)))

    return record


def manual_events(results: Iterable[Mapping[str, Any]], intents: Iterable[Any], approved_by: str, broker: str,
                  as_of: date, **st: str) -> list[dict[str, Any]]:
    """Events for `swing paper --from-intents` (one ``OrderManager.submit`` per saved intent, no autopilot): a
    fire per submitted order and a refusal per one that raised, with the same keys ``autopilot_events`` uses, so
    an order has one fire whichever path sent it."""
    by_cid = {i.client_order_id: i for i in intents}
    rows: list[dict[str, Any]] = []
    for r in results:
        cid = str(r.get("client_order_id") or "")
        intent = by_cid.get(cid)
        if intent is None:
            continue
        day = getattr(intent, "signal_as_of", None) or as_of
        payload = {"mode": "manual", "approved_by": approved_by, "broker": broker, "intent": intent,
                   "client_order_id": cid, "order": {k: r.get(k) for k in ("broker_order_id", "status")}}
        if str(r.get("status")) == "error":
            reason = str(r.get("reason") or "submit failed")
            rows.append(make_event(REFUSAL, step_for(reason, "broker"), reason, day, intent.strategy, intent.symbol,
                                   payload, key=f"{cid}|{as_of.isoformat()}", **st))
        else:
            rows.append(make_event(FIRE, "broker", "submitted", day, intent.strategy, intent.symbol, payload,
                                   key=cid, **st))
    return rows


def link_outcomes(events: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    """``outcome event_id -> event_id`` of the fire or refusal it grades: same strategy and symbol, decided on the
    outcome's ``payload.signal_as_of`` or up to ``SIGNAL_DAY_SLACK_DAYS`` after it (a pre-open run stamps the run
    date); a fire wins over a refusal, then the nearest day. ``payload`` may be a dict or its JSON string."""
    decided: dict[tuple[str, str], list[tuple[date, int, str]]] = {}
    outcomes: list[tuple[str, tuple[str, str], date]] = []
    for e in events:
        key, day = (str(e.get("strategy")), str(e.get("symbol"))), _day(e.get("as_of"))
        if e.get("kind") in (FIRE, REFUSAL) and day is not None:
            decided.setdefault(key, []).append((day, 0 if e["kind"] == FIRE else 1, str(e["event_id"])))
        elif e.get("kind") == OUTCOME:
            p = e.get("payload") or {}
            signal_day = _day((json.loads(p) if isinstance(p, str) else p).get("signal_as_of"))
            if signal_day is not None:
                outcomes.append((str(e["event_id"]), key, signal_day))
    links: dict[str, str] = {}
    for oid, key, signal_day in outcomes:
        near = [(kind, (d - signal_day).days, eid) for d, kind, eid in decided.get(key, ())
                if 0 <= (d - signal_day).days <= SIGNAL_DAY_SLACK_DAYS]
        if near:
            links[oid] = min(near)[2]
    return links


# ----------------------------------------------------------------------------------------------- outcomes
def _day(value: Any) -> date | None:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    return pd.Timestamp(value).date()


def _flag(value: Any) -> bool:
    return str(value).lower() == "true"  # a nullable BOOLEAN reads back as True / False / NA / NaN


def _num(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _with_costs(store: Any, frame: pd.DataFrame) -> pd.DataFrame:
    """``frame`` plus per-signal ``cost_bps`` (research.costs) from the store's bars; unchanged when that fails."""
    try:
        from swing_engine.research.costs import attach_costs, cost_table

        days = pd.to_datetime(frame["as_of"]).dt.date
        bars = store.read_bars(sorted(set(frame["symbol"].astype(str))), min(days) - timedelta(days=COST_LOOKBACK_DAYS),
                               max(days))
        return attach_costs(frame, cost_table(bars)) if len(bars) else frame
    except Exception as exc:  # noqa: BLE001 - net R then falls back to the default bps, and says so
        log.info("receipts.costs_unavailable", error=f"{type(exc).__name__}: {exc}")
        return frame


def outcome_events(frame: pd.DataFrame, **st: str) -> list[dict[str, Any]]:
    """One outcome event per final horizon of each shadow-ledger row in ``frame`` (``research.shadow`` columns,
    optionally ``cost_bps``). ``gross_r`` is the ledger's R (per filled risk); ``net_r`` is the planned-risk R
    (research.cards.planned_r) minus research.cards.cost_r, or None with a ``cost_note`` when no cost applies."""
    from swing_engine.research.cards import cost_r, planned_r
    from swing_engine.research.shadow import FINAL_HITS

    if frame is None or frame.empty:
        return []
    frame = frame.reset_index(drop=True)
    horizons = sorted(int(m.group(1)) for c in frame.columns if (m := _HIT_COLUMN.match(c)))
    planned = planned_r(frame.copy())
    cost = cost_r(frame)
    rows: list[dict[str, Any]] = []
    for i, rec in enumerate(frame.to_dict("records")):
        signal_day = _day(rec["as_of"])
        if signal_day is None:
            continue
        cost_i, bps = _num(cost.iloc[i]), _num(rec.get("cost_bps"))
        note = cost_note(cost_i, bps)
        for h in horizons:
            hit = rec.get(f"hit_{h}d")
            if hit not in FINAL_HITS:
                continue
            gross_planned = _num(planned.at[i, f"result_r_{h}d"])
            net = None if cost_i is None or gross_planned is None else gross_planned - cost_i
            payload = {
                "horizon": h, "hit": hit, "skip_reason": rec.get("skip_reason"), "signal_as_of": signal_day,
                "gross_r": _num(rec.get(f"result_r_{h}d")), "gross_r_planned": gross_planned, "cost_r": cost_i,
                "net_r": net, "cost_bps": bps, "cost_note": note, "mfe_r": _num(rec.get(f"mfe_r_{h}d")),
                "mae_r": _num(rec.get(f"mae_r_{h}d")), "exit_date": _day(rec.get(f"exit_date_{h}d")),
                "entry_date": _day(rec.get("entry_date")), "entry_price": _num(rec.get("entry_price")),
                "taken": _flag(rec.get("taken")), "regime": rec.get("regime"), "side": rec.get("side"),
                "entry": _num(rec.get("entry")), "stop": _num(rec.get("stop")), "target": _num(rec.get("target")),
            }
            skip = rec.get("skip_reason")
            reason = str(skip) if hit == "entry_skipped" and isinstance(skip, str) and skip else str(hit)
            rows.append(make_event(
                OUTCOME, OUTCOME_STEPS.get(str(hit), "rule"), reason, payload["exit_date"] or signal_day,
                str(rec["strategy"]), str(rec["symbol"]), payload, key=f"{signal_day.isoformat()}|{h}d", **st,
            ))
    return rows


def record_outcomes(store: Any, graded_through: date | None = None, *, table: str | None = None, **st: str) -> int:
    """Write the outcome events of the shadow ledger (only rows graded on ``graded_through`` when given)."""
    try:
        from swing_engine.research.shadow import SHADOW_TABLE

        name = table or SHADOW_TABLE
        if not store.has_table(name):
            return 0
        where = ("graded_through = ?", [graded_through]) if graded_through is not None else (None, None)
        frame = store.read_table(name, *where)
        if frame.empty or "graded_through" not in frame.columns:
            return 0
        return write_events(store, outcome_events(_with_costs(store, frame), **st))
    except Exception as exc:  # noqa: BLE001
        log.error("receipts.outcomes_failed", error=f"{type(exc).__name__}: {exc}")
        return 0


# ----------------------------------------------------------------------------------------------- backfill
def _near(signal_day: date, days: Iterable[date]) -> bool:
    return any(0 <= (d - signal_day).days <= SIGNAL_DAY_SLACK_DAYS for d in days)


def backfill(store: Any, settings: Settings, ledger_rows: Iterable[Mapping[str, Any]] = ()) -> dict[str, int]:
    """Receipts for decisions made before receipts existed, ``source='backfill'``: the order ledger's rows
    (``execution.ledger.OrderLedger.all()``) become fires and broker / unfilled refusals, the live shadow ledger's
    other signals become shadow fires or refusals with step ``unknown``, and every graded horizon an outcome.
    Idempotent (stable event ids); a signal that already has a live receipt is left alone."""
    from swing_engine.research.shadow import SHADOW_TABLE

    st = stamp(settings, SOURCE_BACKFILL)
    rows: list[dict[str, Any]] = []
    decided: dict[tuple[str, str], list[date]] = {}  # (strategy, symbol) -> days that already have a receipt
    for r in ledger_rows:
        intent = dict(r.get("intent") or {})
        day = _day(intent.get("signal_as_of")) or _day(r.get("created_at"))
        if day is None:
            continue
        cid, status, strategy, symbol = str(r["client_order_id"]), str(r["status"]), str(r["strategy"]), str(r["symbol"])
        payload = {"intent": intent, "order": {k: r.get(k) for k in (
            "client_order_id", "broker_order_id", "status", "approved_by", "created_at", "updated_at")}}
        if status in ("rejected", "error"):
            rows.append(make_event(REFUSAL, "broker", f"broker {status}", day, strategy, symbol, payload, key=cid, **st))
        else:
            rows.append(make_event(FIRE, "broker", "submitted", day, strategy, symbol, payload, key=cid, **st))
            filled = _num((r.get("broker") or {}).get("filled_qty")) if isinstance(r.get("broker"), Mapping) else None
            if status in ("canceled", "expired") and not filled:
                rows.append(make_event(REFUSAL, "fill", f"entry {status} unfilled", day, strategy, symbol, payload,
                                       key=cid, **st))
        decided.setdefault((strategy, symbol), []).append(day)
    live = read_events(store)
    for rec in live.loc[live["kind"].isin([FIRE, REFUSAL]) & (live["source"] != SOURCE_BACKFILL)].to_dict("records"):
        day = _day(rec["as_of"])
        if day is not None:
            decided.setdefault((str(rec["strategy"]), str(rec["symbol"])), []).append(day)
    shadow = store.read_table(SHADOW_TABLE) if store.has_table(SHADOW_TABLE) else pd.DataFrame()
    shadow_only = {n for n, cfg in settings.strategies.items()
                   if not (cfg or {}).get("enabled", True) and (cfg or {}).get("shadow_only")}
    for rec in shadow.to_dict("records"):
        day, strategy, symbol = _day(rec["as_of"]), str(rec["strategy"]), str(rec["symbol"])
        if day is None or _near(day, decided.get((strategy, symbol), ())):
            continue
        taken = _flag(rec.get("taken"))
        payload = {"signal": {k: rec.get(k) for k in ("side", "entry", "entry_type", "stop", "target", "reward_risk",
                                                      "score")},
                   "regime": rec.get("regime"), "taken": taken, "recorded_at": rec.get("recorded_at")}
        if strategy in shadow_only and not taken:
            rows.append(make_event(FIRE, "scan", "shadow-only signal", day, strategy, symbol,
                                   {**payload, "shadow": True}, **st))
        else:
            why = "sized, but no order in the ledger" if taken else "not taken"
            rows.append(make_event(REFUSAL, STEP_UNKNOWN, f"{why} (step not recorded before receipts)", day,
                                   strategy, symbol, payload, **st))
    counts = {k: sum(r["kind"] == k for r in rows) for k in (FIRE, REFUSAL)}
    written = write_events(store, rows)
    outcomes = record_outcomes(store, **st)
    return {**counts, "outcomes_written": outcomes, "written": written + outcomes}
