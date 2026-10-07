"""Form 4 open-market buys (codes P/A) and insider clusters (>= 3 distinct insiders in 30 days, rejecting
clusters where >= 80% of the buys share an identical date+price, which signals grants or 10b5-1 batches).
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any

from swing_engine.core.interfaces import Rule
from swing_engine.core.models import Event
from swing_engine.core.registry import register

from ..constants import (
    FORM4_BUY_CODES,
    INSIDER_CLUSTER_IDENTICAL_REJECT_PCT,
    INSIDER_CLUSTER_MIN,
    INSIDER_CLUSTER_WINDOW_DAYS,
)
from ._common import P1, P2, form_type


def _as_date(value: Any, fallback: datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value[:10]).date()
        except ValueError:
            pass
    return fallback.date()


def is_open_market_buy(meta: dict[str, Any]) -> bool:
    code = str(meta.get("transaction_code", "")).upper()
    acq = str(meta.get("acquired_disposed", "A")).upper()
    return code in FORM4_BUY_CODES and acq == "A"


def cluster_ok(buys: list[dict[str, Any]]) -> bool:
    """>= 3 distinct insiders and not a batch of identical date+price buys."""
    owners = {b["owner"] for b in buys}
    if len(owners) < INSIDER_CLUSTER_MIN:
        return False
    pairs = Counter((b["date"], b.get("price")) for b in buys)
    top = pairs.most_common(1)[0][1]
    identical_pct = 100.0 * top / len(buys)
    return identical_pct < INSIDER_CLUSTER_IDENTICAL_REJECT_PCT


@register("rule", "form4_buy_and_cluster")
class Form4BuyAndCluster(Rule):
    name = "form4_buy_and_cluster"

    def evaluate(self, event: Event, ctx: dict[str, Any]) -> tuple[str, str] | None:
        if event.kind != "filing" or form_type(event) not in {"4", "4/A"} or not event.symbols:
            return None
        if not is_open_market_buy(event.meta):
            return None
        sym = event.symbols[0].upper()
        owner = str(event.meta.get("owner") or event.meta.get("reporting_owner") or "unknown").strip().lower()
        tx_date = _as_date(event.meta.get("transaction_date"), event.ts_source)
        price = event.meta.get("price")
        history: dict[str, list[dict[str, Any]]] = ctx.setdefault("form4_history", {})
        buys = history.setdefault(sym, [])
        cutoff = tx_date - timedelta(days=INSIDER_CLUSTER_WINDOW_DAYS)
        buys[:] = [b for b in buys if b["date"] >= cutoff]
        key = (owner, tx_date, price, event.event_id)
        if key not in {(b["owner"], b["date"], b.get("price"), b.get("event_id")) for b in buys}:
            buys.append({"owner": owner, "date": tx_date, "price": price, "event_id": event.event_id})
        event.meta["insider_buyers_30d"] = len({b["owner"] for b in buys})
        if cluster_ok(buys):
            event.meta["insider_cluster"] = True
            return "insider_cluster", P2
        return "form4_buy", P1
