"""OrderManager: the only path from an ``OrderIntent`` to a broker.

``submit`` raises :class:`OrderRefused` when ``approved_by`` is empty, the kill-switch file exists, the intent fails
validation, or ``LimitState.check`` says no. It is idempotent on ``client_order_id`` through the sqlite ledger: a
repeat submit returns the stored record with ``status="duplicate"`` and never calls the broker again. Cancels are
allowed while the kill switch is tripped (they only reduce exposure).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, NoReturn

import structlog

from swing_engine.core.interfaces import Broker
from swing_engine.core.models import OrderIntent, Side
from swing_engine.execution.ledger import DEFAULT_LEDGER_PATH, OrderLedger, OrderStatus, normalize_status
from swing_engine.risk import killswitch
from swing_engine.risk.killswitch import DEFAULT_KILL_SWITCH_FILE
from swing_engine.risk.limits import LimitState

log = structlog.get_logger(__name__)

DUPLICATE = "duplicate"
FILLED_STATUSES: frozenset[str] = frozenset({OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED})


class OrderRefused(RuntimeError):
    """Raised for every refusal; ``reason`` says which rule fired."""

    def __init__(self, reason: str, client_order_id: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.client_order_id = client_order_id


def validate_intent(intent: OrderIntent) -> str | None:
    """Structural sanity of an intent independent of account state. Returns the first problem or None."""
    if not intent.client_order_id or not intent.client_order_id.strip():
        return "client_order_id is required"
    if intent.qty <= 0:
        return f"qty must be positive, got {intent.qty}"
    if intent.stop <= 0:
        return "stop must be positive"
    if intent.entry_limit is not None and intent.entry_limit <= 0:
        return "entry_limit must be positive"
    ref = intent.entry_limit
    if intent.side == Side.LONG:
        if ref is not None and intent.stop >= ref:
            return "long stop must be below the entry limit"
        if intent.target is not None and intent.target <= (ref if ref is not None else intent.stop):
            return "long target must be above the entry"
    else:
        if ref is not None and intent.stop <= ref:
            return "short stop must be above the entry limit"
        if intent.target is not None and intent.target >= (ref if ref is not None else intent.stop):
            return "short target must be below the entry"
    return None


class OrderManager:
    def __init__(
        self,
        broker: Broker,
        limits: LimitState | None = None,
        killswitch_path: str | Path = DEFAULT_KILL_SWITCH_FILE,
        ledger_path: str | Path = DEFAULT_LEDGER_PATH,
        ledger: OrderLedger | None = None,
    ) -> None:
        self.broker = broker
        self.limits = limits
        self.killswitch_path = killswitch_path
        self.ledger = ledger if ledger is not None else OrderLedger(ledger_path)

    def kill_switch_tripped(self) -> bool:
        return killswitch.is_tripped(self.killswitch_path)

    # ------------------------------------------------------------ submit
    def submit(self, intent: OrderIntent, approved_by: str) -> dict[str, Any]:
        cid = intent.client_order_id
        if not isinstance(approved_by, str) or not approved_by.strip():
            self._refuse("approval required: approved_by is empty", cid)
        if self.kill_switch_tripped():
            self._refuse(f"kill switch tripped at {killswitch.resolve_state_path(self.killswitch_path)}", cid)
        problem = validate_intent(intent)
        if problem:
            self._refuse(f"invalid intent: {problem}", cid)

        existing = self.ledger.get(cid)
        if existing is not None:
            return self._duplicate(existing)

        if self.limits is not None:
            ok, reason = self.limits.check(intent, self._account_snapshot())
            if not ok:
                self._refuse(f"limit check failed: {reason}", cid)

        if not self.ledger.reserve(intent, approved_by.strip()):
            existing = self.ledger.get(cid)
            if existing is not None:
                return self._duplicate(existing)
            self._refuse("ledger could not reserve the order id", cid)  # pragma: no cover - defensive

        try:
            response = self.broker.submit(intent)
        except Exception as exc:
            self.ledger.update(cid, OrderStatus.ERROR, broker_json={"error": str(exc)})
            log.error("broker_submit_failed", client_order_id=cid, symbol=intent.symbol, error=str(exc))
            raise

        status = normalize_status(response.get("status")) if response.get("status") else OrderStatus.ACCEPTED.value
        broker_order_id = response.get("broker_order_id") or response.get("id")
        self.ledger.update(
            cid, status,
            broker_order_id=str(broker_order_id) if broker_order_id else None,
            broker_json=response.get("raw", response),
        )
        log.info(
            "order_submitted", client_order_id=cid, symbol=intent.symbol, side=intent.side.value, qty=intent.qty,
            stop=intent.stop, target=intent.target, status=status, broker_order_id=broker_order_id,
            approved_by=approved_by.strip(), broker=getattr(self.broker, "name", type(self.broker).__name__),
        )
        return {
            "status": status,
            "client_order_id": cid,
            "broker_order_id": str(broker_order_id) if broker_order_id else None,
            "symbol": intent.symbol,
            "side": intent.side.value,
            "qty": intent.qty,
            "approved_by": approved_by.strip(),
            "broker": response,
        }

    # ------------------------------------------------------------ cancel / reconcile
    def cancel(self, client_order_id: str) -> dict[str, Any]:
        row = self.ledger.get(client_order_id)
        if row is None:
            raise KeyError(f"no ledger entry for {client_order_id!r}")
        if not row.get("broker_order_id"):
            raise OrderRefused("no broker order id recorded; run reconcile first", client_order_id)
        self.broker.cancel(row["broker_order_id"])
        self.ledger.update(client_order_id, OrderStatus.CANCELED)
        log.info("order_canceled", client_order_id=client_order_id, broker_order_id=row["broker_order_id"])
        return {"status": OrderStatus.CANCELED.value, "client_order_id": client_order_id,
                "broker_order_id": row["broker_order_id"]}

    def reconcile(self) -> dict[str, Any]:
        """Refresh ledger statuses from the broker and flag positions the ledger does not know about."""
        open_orders = {str(o.get("client_order_id")): o for o in self.broker.open_orders()}
        positions = self.broker.positions()
        get_order = getattr(self.broker, "get_order", None)
        pending = self.ledger.pending()
        updated: list[dict[str, Any]] = []
        unresolved: list[str] = []
        for row in pending:
            cid = row["client_order_id"]
            broker_order = open_orders.get(cid)
            if broker_order is None and callable(get_order):
                try:
                    broker_order = get_order(cid)
                except Exception as exc:  # noqa: BLE001 - reconcile must keep going
                    log.warning("reconcile_lookup_failed", client_order_id=cid, error=str(exc))
                    broker_order = None
            if broker_order is None:
                unresolved.append(cid)
                continue
            status = normalize_status(broker_order.get("status"))
            boid = broker_order.get("id") or broker_order.get("broker_order_id")
            if status != row["status"] or (boid and str(boid) != row.get("broker_order_id")):
                self.ledger.update(cid, status, broker_order_id=str(boid) if boid else None, broker_json=broker_order)
                updated.append({"client_order_id": cid, "from": row["status"], "to": status})
        known_symbols = {r["symbol"] for r in self.ledger.all() if r["status"] in FILLED_STATUSES}
        unknown_positions = sorted(p.symbol for p in positions if p.symbol not in known_symbols)
        summary = {
            "checked": len(pending),
            "updated": updated,
            "unresolved": unresolved,
            "open_orders": len(open_orders),
            "positions": [p.model_dump(mode="json") for p in positions],
            "unknown_positions": unknown_positions,
            "kill_switch": self.kill_switch_tripped(),
        }
        log.info("reconcile_done", checked=len(pending), updated=len(updated), unresolved=len(unresolved),
                 unknown_positions=unknown_positions)
        return summary

    # ------------------------------------------------------------ helpers
    def _account_snapshot(self) -> dict[str, Any]:
        account = dict(self.broker.account())
        account["positions"] = self.broker.positions()
        account["open_orders"] = self.broker.open_orders()
        return account

    @staticmethod
    def _duplicate(row: dict[str, Any]) -> dict[str, Any]:
        log.info("order_duplicate", client_order_id=row["client_order_id"], ledger_status=row["status"])
        return {
            "status": DUPLICATE,
            "ledger_status": row["status"],
            "client_order_id": row["client_order_id"],
            "broker_order_id": row.get("broker_order_id"),
            "symbol": row["symbol"],
            "side": row["side"],
            "qty": row["qty"],
            "approved_by": row["approved_by"],
            "broker": row.get("broker"),
        }

    @staticmethod
    def _refuse(reason: str, client_order_id: str | None) -> NoReturn:
        log.warning("order_refused", reason=reason, client_order_id=client_order_id)
        raise OrderRefused(reason, client_order_id)
