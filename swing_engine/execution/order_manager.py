"""OrderManager: the only path from an ``OrderIntent`` to a broker.

``submit`` raises :class:`OrderRefused` when ``approved_by`` is empty, the kill-switch file exists, the intent fails
validation, or ``LimitState.check`` says no. It is idempotent on ``client_order_id`` through the sqlite ledger: a
repeat submit returns the stored record with ``status="duplicate"`` and never calls the broker again. Cancels are
allowed while the kill switch is tripped (they only reduce exposure).

Exits (``close_position``, ``replace_stop``, ``place_stop``, ``cancel_order``) also go through here so every broker
mutation is approved and logged in one place. Closing is exposure-reducing and allowed under the kill switch like
a cancel; replacing or placing a stop is a new order/modification and is refused while it is tripped.
``replace_stop`` never loosens a stop; ``place_stop`` only arms a stop on a position that has none.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, NoReturn

import structlog

from swing_engine.core.interfaces import Broker
from swing_engine.core.models import EntryType, OrderIntent, Side
from swing_engine.data.delisted import ENTITY_SEP
from swing_engine.execution.ledger import DEFAULT_LEDGER_PATH, OrderLedger, OrderStatus, normalize_status
from swing_engine.risk import killswitch
from swing_engine.risk.killswitch import DEFAULT_KILL_SWITCH_FILE
from swing_engine.risk.limits import LimitState

log = structlog.get_logger(__name__)

DUPLICATE = "duplicate"
CLOSED = "closed"
REPLACED = "replaced"
PLACED = "placed"
PAPER_SIM_BROKER = "paper_sim"
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
    if ENTITY_SEP in intent.symbol:  # data.delisted research key (TICKER~YYYYMMDD), not a tradable ticker
        return f"{intent.symbol} is a delisted-entity research key, not a ticker"
    if intent.entry_type != EntryType.OPEN:  # research-only until the broker adapter places stop/limit entries
        return f"entry type {intent.entry_type.value} is not supported by the broker layer yet"
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

    def cancel_order(self, order_id: str | None, client_order_id: str | None = None) -> dict[str, Any]:
        """Cancel by broker order id (falls back to the ledger's id for ``client_order_id``); marks the ledger."""
        row = self.ledger.get(client_order_id) if client_order_id else None
        boid = order_id or (row or {}).get("broker_order_id")
        if not boid:
            self._refuse("no broker order id to cancel", client_order_id)
        self.broker.cancel(str(boid))
        if row is not None:
            self.ledger.update(row["client_order_id"], OrderStatus.CANCELED)
        log.info("order_canceled", client_order_id=client_order_id, broker_order_id=boid)
        return {"status": OrderStatus.CANCELED.value, "client_order_id": client_order_id, "broker_order_id": str(boid)}

    def close_position(
        self, symbol: str, approved_by: str, qty: int | None = None, price: float | None = None, reason: str = ""
    ) -> dict[str, Any]:
        """Flatten ``symbol``. ``price`` is only used by brokers that need one to fill (paper_sim)."""
        self._require_approval(approved_by, symbol)
        closer = getattr(self.broker, "close_position", None)
        if not callable(closer):
            self._refuse(f"broker {self._broker_name()} cannot close positions", symbol)
        params = inspect.signature(closer).parameters
        kwargs: dict[str, Any] = {}
        if "price" in params:
            if price is None:
                self._refuse(f"broker {self._broker_name()} needs a reference price to close {symbol}", symbol)
            kwargs["price"] = float(price)
        if "qty" in params and qty is not None:
            kwargs["qty"] = int(qty)
        if "reason" in params and reason:
            kwargs["reason"] = reason
        response = closer(symbol, **kwargs)
        log.info("position_close", symbol=symbol, qty=qty, reason=reason, approved_by=approved_by.strip(),
                 broker=self._broker_name())
        return {"status": CLOSED, "symbol": symbol, "qty": qty, "reason": reason,
                "approved_by": approved_by.strip(), "broker": response}

    def replace_stop(
        self, symbol: str, new_stop: float, approved_by: str, order_id: str | None = None
    ) -> dict[str, Any]:
        """Tighten the protective stop of ``symbol``; refuses to loosen it or to act under the kill switch."""
        self._require_approval(approved_by, symbol)
        if self.kill_switch_tripped():
            self._refuse("kill switch tripped: stop changes are blocked", symbol)
        if new_stop <= 0:
            self._refuse(f"new stop must be positive, got {new_stop}", symbol)
        replacer = getattr(self.broker, "replace_stop", None)
        if callable(replacer):
            extra = {"order_id": order_id} if "order_id" in inspect.signature(replacer).parameters else {}
            try:
                response = replacer(symbol, float(new_stop), **extra)
            except (LookupError, ValueError) as exc:
                self._refuse(f"replace_stop failed: {exc}", symbol)
        elif self._broker_name() == PAPER_SIM_BROKER:
            response = self._sim_replace_stop(symbol, float(new_stop))
        else:
            self._refuse(f"broker {self._broker_name()} cannot replace stops", symbol)
        log.info("stop_replaced", symbol=symbol, new_stop=new_stop, approved_by=approved_by.strip(),
                 broker=self._broker_name())
        return {"status": REPLACED, "symbol": symbol, "new_stop": float(new_stop),
                "approved_by": approved_by.strip(), "broker": response}

    def place_stop(self, symbol: str, stop: float, approved_by: str) -> dict[str, Any]:
        """Arm a protective stop on ``symbol`` when it has none (an expired GTC leg, a failed close that had
        already cancelled the legs, legs dropped after a partial fill). Refused under the kill switch."""
        self._require_approval(approved_by, symbol)
        if self.kill_switch_tripped():
            self._refuse("kill switch tripped: stop changes are blocked", symbol)
        if stop <= 0:
            self._refuse(f"stop must be positive, got {stop}", symbol)
        placer = getattr(self.broker, "place_stop", None)
        if callable(placer):
            try:
                response = placer(symbol, float(stop))
            except (LookupError, ValueError) as exc:
                self._refuse(f"place_stop failed: {exc}", symbol)
        elif self._broker_name() == PAPER_SIM_BROKER:
            response = self._sim_place_stop(symbol, float(stop))
        else:
            self._refuse(f"broker {self._broker_name()} cannot place stops", symbol)
        log.info("stop_placed", symbol=symbol, stop=stop, approved_by=approved_by.strip(), broker=self._broker_name())
        return {"status": PLACED, "symbol": symbol, "stop": float(stop), "approved_by": approved_by.strip(),
                "broker": response}

    def _sim_place_stop(self, symbol: str, stop: float) -> dict[str, Any]:
        for pos in self.broker.positions():
            if pos.symbol != symbol:
                continue
            if pos.stop is not None:
                self._refuse(f"{symbol} already has a stop at {pos.stop}", symbol)
            pos.stop = stop
            return {"symbol": symbol, "stop": stop}
        self._refuse(f"no open {symbol} position on {PAPER_SIM_BROKER}", symbol)

    def _sim_replace_stop(self, symbol: str, new_stop: float) -> dict[str, Any]:
        """paper_sim keeps the stop on its Position objects (``positions()`` returns them by reference)."""
        for pos in self.broker.positions():
            if pos.symbol != symbol:
                continue
            old = pos.stop
            loosens = old is not None and (new_stop <= old if pos.side == Side.LONG else new_stop >= old)
            if loosens:
                self._refuse(f"refusing to loosen or keep the {symbol} stop: {old} -> {new_stop}", symbol)
            pos.stop = new_stop
            return {"symbol": symbol, "previous_stop": old, "new_stop": new_stop}
        self._refuse(f"no open {symbol} position on {PAPER_SIM_BROKER}", symbol)

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
    def _require_approval(self, approved_by: str, ref: str | None) -> None:
        if not isinstance(approved_by, str) or not approved_by.strip():
            self._refuse("approval required: approved_by is empty", ref)

    def _broker_name(self) -> str:
        return str(getattr(self.broker, "name", type(self.broker).__name__))

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
