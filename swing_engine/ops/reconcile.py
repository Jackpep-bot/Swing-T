"""Fill reconcile: ``exit`` receipts for exits that filled AT THE BROKER (a bracket's stop or target leg, or a
close order), which no engine step sees happen.

Read-and-record only. The single broker call is ``closed_orders(since)`` (a listing); nothing here submits,
replaces or cancels, and nothing here feeds a trading decision. One ``exit`` event per filled order, keyed by the
broker's order id, so a rerun writes nothing twice.

Matching a fill to its entry: (1) it is a leg nested under a ``swing-*`` entry order; (2) it ``replaces`` such a
leg (a tightened stop gets a new order id); (3) otherwise the latest filled ``swing-*`` entry on the same symbol
with the opposite side that filled no later than the exit (a close order, or a re-armed ``rearm-*`` stop). A fill
that matches nothing is still recorded, with step ``unknown``.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, timedelta
from typing import Any

import pandas as pd

from swing_engine.core.config import Settings
from swing_engine.ops import receipts

LOOKBACK_DAYS = 30  # default --since, and the nightly's window (idempotent, so re-reading is free)
ENTRY_LOOKBACK_DAYS = 90  # entries are read this far before `since`: Alpaca cancels GTC orders after 90 days
NY = "America/New_York"
STOP_TYPES = frozenset({"stop", "stop_limit", "trailing_stop"})
LEG_STOP, LEG_TARGET, LEG_CLOSE, LEG_UNKNOWN = "stop", "target", "close", "unknown"
NO_R_NOTE = "R not computed: no planned entry / stop for this fill"


def _text(value: Any) -> str:
    return str(getattr(value, "value", value) or "").lower()


def _ts(value: Any) -> pd.Timestamp | None:
    try:
        ts = pd.Timestamp(value)
    except (TypeError, ValueError):
        return None
    if ts is pd.NaT:
        return None
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts


def _fill_ts(order: Mapping[str, Any]) -> pd.Timestamp | None:
    """When the order filled; a partial fill that was then cancelled has no ``filled_at``."""
    return _ts(order.get("filled_at")) or _ts(order.get("canceled_at")) or _ts(order.get("updated_at"))


def _filled(order: Mapping[str, Any]) -> bool:
    return (receipts._num(order.get("filled_qty")) or 0) > 0 and _fill_ts(order) is not None


def ledger_rows(settings: Settings) -> list[dict[str, Any]]:
    """Every row of the order ledger (``[]`` when there is none yet)."""
    from swing_engine.execution.ledger import OrderLedger
    from swing_engine.risk.killswitch import resolve_state_path

    path = resolve_state_path(settings.execution.ledger_file)
    if not path.exists():
        return []
    ledger = OrderLedger(path)
    try:
        return ledger.all()
    finally:
        ledger.close()


def _match(orders: Iterable[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, tuple[dict[str, Any], str]]]:
    """(candidate exit orders, order id -> (entry order, how it matched)) from a nested closed-order listing."""
    from swing_engine.risk.sizing import CLIENT_ORDER_ID_PREFIX

    entries: list[dict[str, Any]] = []
    candidates: dict[str, dict[str, Any]] = {}
    parent: dict[str, tuple[dict[str, Any], str]] = {}
    for raw in orders:
        order = dict(raw)
        is_entry = str(order.get("client_order_id") or "").startswith(f"{CLIENT_ORDER_ID_PREFIX}-")
        if is_entry:
            entries.append(order)
        else:
            candidates[str(order.get("id"))] = order
        for leg in order.get("legs") or []:
            item = {"symbol": order.get("symbol"), **dict(leg)}
            candidates[str(item.get("id"))] = item
            if is_entry:
                parent[str(item.get("id"))] = (order, "bracket_leg")
    changed = True
    while changed:  # a stop tightened twice is a chain of replacements
        changed = False
        for oid, order in candidates.items():
            old = str(order.get("replaces") or "")
            if oid not in parent and old in parent:
                parent[oid] = (parent[old][0], "replaces")
                changed = True
    filled_entries = [(e, _fill_ts(e)) for e in entries if _filled(e)]
    for oid, order in candidates.items():
        when = _fill_ts(order)
        if oid in parent or not _filled(order) or when is None:
            continue
        # ponytail: latest earlier entry on the symbol, no share accounting; fine while the engine holds one
        # position per symbol (risk.sizing refuses a second). Track lots if that rule ever goes.
        prior = [(t, e) for e, t in filled_entries if e.get("symbol") == order.get("symbol") and t is not None
                 and t <= when and _text(e.get("side")) != _text(order.get("side"))]
        if prior:
            parent[oid] = (max(prior, key=lambda p: p[0])[1], "symbol")
    return list(candidates.values()), parent


def _known(store: Any, fire_ids: list[str]) -> tuple[dict[str, dict[str, Any]], dict[str, tuple[str, str]]]:
    """(fire event id -> its payload, close order id -> (step, event id) of the engine's own close receipt)."""
    import json

    if not store.has_table(receipts.EVENTS_TABLE):
        return {}, {}
    fires = store.sql(f"SELECT event_id, payload FROM {receipts.EVENTS_TABLE} WHERE event_id IN (SELECT unnest(?))",
                      [fire_ids])
    closes = store.sql(f"SELECT event_id, step, payload FROM {receipts.EVENTS_TABLE} WHERE kind = ? AND payload LIKE ?",
                       [receipts.EXIT, '%"action": "close"%'])
    by_order: dict[str, tuple[str, str]] = {}
    for rec in closes.to_dict("records"):
        oid = (json.loads(rec["payload"]).get("response") or {}).get("broker_order_id")
        if oid:
            by_order[str(oid)] = (str(rec["step"]), str(rec["event_id"]))
    return {r["event_id"]: json.loads(r["payload"]) for r in fires.to_dict("records")}, by_order


def reconcile_fills(
    store: Any, settings: Settings, broker: Any, ledger: Iterable[Mapping[str, Any]] = (), since: date | None = None,
    **st: str,
) -> dict[str, Any]:
    """Write one ``exit`` event per order that filled at ``broker`` on or after ``since`` and is not an entry.
    Returns counts. Raises when the broker cannot list closed orders; the callers decide what that costs."""
    from swing_engine.execution.position_manager import strategy_from_client_order_id
    from swing_engine.research.cards import cost_r

    since = since or date.today() - timedelta(days=LOOKBACK_DAYS)
    st = st or receipts.stamp(settings)
    orders = list(broker.closed_orders(since - timedelta(days=ENTRY_LOOKBACK_DAYS)))
    candidates, parent = _match(orders)
    intents = {str(r["client_order_id"]): r for r in ledger}

    fills: list[dict[str, Any]] = []
    for order in candidates:
        when = _fill_ts(order)
        if not _filled(order) or when is None or when.tz_convert(NY).date() < since:
            continue
        oid, symbol = str(order.get("id")), str(order.get("symbol") or "")
        entry, how = parent.get(oid, (None, None))
        cid = str(entry.get("client_order_id")) if entry else None
        row = intents.get(cid or "") or {}
        intent = dict(row.get("intent") or {})
        strategy = str(row.get("strategy") or strategy_from_client_order_id(cid, settings.strategies) or "")
        legs = [dict(leg) for leg in (entry or {}).get("legs") or []]
        order_type = _text(order.get("order_type") or order.get("type"))
        fills.append({
            "order": order, "oid": oid, "symbol": symbol, "when": when, "entry": entry, "how": how, "cid": cid,
            "intent": intent, "strategy": strategy, "order_type": order_type,
            "long": _text((entry or {}).get("side")) != "sell",
            "fire_id": receipts.event_id(receipts.FIRE, strategy, symbol, "broker", cid) if cid else None,
            # planned levels: the ledger's intent, else the bracket as the broker holds it
            "stop": receipts._num(intent.get("stop")) or next(
                (receipts._num(leg.get("stop_price")) for leg in legs if leg.get("stop_price") is not None), None),
            "target": receipts._num(intent.get("target")) or next(
                (receipts._num(leg.get("limit_price")) for leg in legs
                 if _text(leg.get("order_type") or leg.get("type")) == "limit"), None),
        })

    fire_payloads, closes = _known(store, [f["fire_id"] for f in fills if f["fire_id"]])
    for f in fills:
        signal = (fire_payloads.get(f["fire_id"] or "") or {}).get("signal") or {}
        f["planned_entry"] = receipts._num(signal.get("entry")) or receipts._num(f["intent"].get("entry_limit"))
        f["basis"] = "signal entry" if receipts._num(signal.get("entry")) else (
            "entry limit (signal entry not on the fire receipt)" if f["planned_entry"] else None)
        f["as_of"] = receipts._day(f["intent"].get("signal_as_of")) or (
            _fill_ts(f["entry"]).tz_convert(NY).date() if f["entry"] and _fill_ts(f["entry"]) is not None else None)

    priced = [f for f in fills if f["planned_entry"] and f["stop"] and f["as_of"]]
    cost: dict[str, tuple[float | None, float | None]] = {}
    if priced:
        frame = receipts._with_costs(store, pd.DataFrame(
            [{"symbol": f["symbol"], "as_of": f["as_of"], "entry": f["planned_entry"], "stop": f["stop"]} for f in priced]
        )).reset_index(drop=True)
        in_r = cost_r(frame)
        bps = frame["cost_bps"] if "cost_bps" in frame.columns else pd.Series([None] * len(frame))
        cost = {f["oid"]: (receipts._num(in_r.iloc[i]), receipts._num(bps.iloc[i])) for i, f in enumerate(priced)}

    rows: list[dict[str, Any]] = []
    by_step: dict[str, int] = {}
    for f in fills:
        order, entry = f["order"], f["entry"]
        action = closes.get(f["oid"])
        if entry is None:
            leg, step, what = LEG_UNKNOWN, receipts.STEP_UNKNOWN, "fill matches no engine entry"
        elif f["order_type"] in STOP_TYPES:
            leg, step, what = LEG_STOP, "stop", "stop filled at the broker"
        elif f["how"] in ("bracket_leg", "replaces"):
            leg, step, what = LEG_TARGET, "target", "target filled at the broker"
        elif action or f["order_type"] == "market":
            leg, step = LEG_CLOSE, action[0] if action else "rule"
            what = "close order filled" if action else "close order filled (no close receipt: before receipts, or manual)"
        else:
            leg, step, what = LEG_UNKNOWN, receipts.STEP_UNKNOWN, f"{f['order_type'] or 'order'} filled outside the bracket"
        price, entry_price = receipts._num(order.get("filled_avg_price")), receipts._num((entry or {}).get("filled_avg_price"))
        sign = 1.0 if f["long"] else -1.0
        risk = sign * (f["planned_entry"] - f["stop"]) if f["planned_entry"] and f["stop"] else None
        gross = sign * (price - entry_price) / risk if risk and risk > 0 and price and entry_price else None
        cost_i, bps_i = cost.get(f["oid"], (None, None))
        net = None if gross is None or cost_i is None else gross - cost_i
        payload = {
            "entry_order_id": (entry or {}).get("id"), "entry_client_order_id": f["cid"], "exit_order_id": f["oid"],
            "exit_client_order_id": order.get("client_order_id"), "leg_type": leg, "order_type": f["order_type"],
            "side": _text(order.get("side")), "matched_by": f["how"], "fill_price": price,
            "fill_time": f["when"].isoformat(), "qty": receipts._num(order.get("filled_qty")),
            "entry_fill_price": entry_price,
            "entry_fill_time": _fill_ts(entry).isoformat() if entry and _fill_ts(entry) is not None else None,
            "planned_entry": f["planned_entry"], "planned_entry_basis": f["basis"], "planned_stop": f["stop"],
            "planned_target": f["target"], "gross_r": gross, "cost_r": cost_i, "net_r": net, "cost_bps": bps_i,
            "cost_note": NO_R_NOTE if gross is None else receipts.cost_note(cost_i, bps_i),
            "ref": f["fire_id"] if f["fire_id"] in fire_payloads else None,
            "action_event": action[1] if action else None,
        }
        r_text = "" if gross is None else f" ({gross:+.2f}R gross" + ("" if net is None else f", {net:+.2f}R net") + ")"
        reason = f"{what}: {payload['qty']:g} @ {price}{r_text}"
        rows.append(receipts.make_event(receipts.EXIT, step, reason, f["when"].tz_convert(NY).date(), f["strategy"],
                                        f["symbol"], payload, key=f"fill|{f['oid']}", **st))
        by_step[step] = by_step.get(step, 0) + 1
    return {"orders_read": len(orders), "exit_fills": len(rows), "by_step": by_step,
            "unmatched": by_step.get(receipts.STEP_UNKNOWN, 0), "written": receipts.write_events(store, rows)}
