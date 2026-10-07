"""Local sqlite ledger of every order the OrderManager has reserved.

It is the idempotency guard: a ``client_order_id`` row is inserted *before* the broker call, so a crash between
reservation and broker acknowledgement still leaves a row that :meth:`OrderManager.reconcile` can resolve, and a
second ``submit`` with the same id is a no-op that never reaches the broker.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import structlog

from swing_engine.core.models import OrderIntent
from swing_engine.risk.killswitch import resolve_state_path

log = structlog.get_logger(__name__)

DEFAULT_LEDGER_PATH = "state/orders.sqlite"
MEMORY_PATH = ":memory:"


class OrderStatus(StrEnum):
    SUBMITTING = "submitting"  # reserved locally, broker not yet acknowledged
    ACCEPTED = "accepted"
    NEW = "new"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    EXPIRED = "expired"
    REJECTED = "rejected"
    REPLACED = "replaced"
    ERROR = "error"  # broker call raised; needs reconcile
    UNKNOWN = "unknown"


TERMINAL_STATUSES: frozenset[str] = frozenset(
    {OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED, OrderStatus.REPLACED}
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    client_order_id TEXT PRIMARY KEY,
    symbol          TEXT NOT NULL,
    side            TEXT NOT NULL,
    qty             INTEGER NOT NULL,
    strategy        TEXT NOT NULL,
    intent_json     TEXT NOT NULL,
    approved_by     TEXT NOT NULL,
    status          TEXT NOT NULL,
    broker_order_id TEXT,
    broker_json     TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS orders_status ON orders(status);
"""

_COLUMNS = (
    "client_order_id", "symbol", "side", "qty", "strategy", "intent_json", "approved_by", "status",
    "broker_order_id", "broker_json", "created_at", "updated_at",
)


def normalize_status(raw: Any) -> str:
    """Map a broker status (enum or string, any case) onto :class:`OrderStatus` values; unknown ones pass through."""
    if raw is None:
        return OrderStatus.UNKNOWN.value
    text = str(getattr(raw, "value", raw)).strip().lower()
    try:
        return OrderStatus(text).value
    except ValueError:
        return text or OrderStatus.UNKNOWN.value


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _json_default(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return str(obj)


class OrderLedger:
    """Thin sqlite wrapper; ``path=":memory:"`` gives an isolated ledger for tests."""

    def __init__(self, path: str | Path = DEFAULT_LEDGER_PATH) -> None:
        if str(path) == MEMORY_PATH:
            self.path = Path(MEMORY_PATH)
            self._conn = sqlite3.connect(MEMORY_PATH)
        else:
            self.path = resolve_state_path(path)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.path)
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.row_factory = sqlite3.Row
        with self._conn:
            self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def reserve(self, intent: OrderIntent, approved_by: str) -> bool:
        """Insert the order as SUBMITTING. False when the id already exists (atomic, so safe under races)."""
        now = _now_iso()
        with self._conn:
            cur = self._conn.execute(
                f"INSERT OR IGNORE INTO orders ({', '.join(_COLUMNS)}) VALUES ({', '.join('?' * len(_COLUMNS))})",
                (
                    intent.client_order_id, intent.symbol, intent.side.value, intent.qty, intent.strategy,
                    intent.model_dump_json(), approved_by, OrderStatus.SUBMITTING.value, None, None, now, now,
                ),
            )
        reserved = cur.rowcount == 1
        log.debug("ledger_reserve", client_order_id=intent.client_order_id, reserved=reserved)
        return reserved

    def update(
        self,
        client_order_id: str,
        status: str | OrderStatus,
        broker_order_id: str | None = None,
        broker_json: Any = None,
    ) -> None:
        sets = ["status = ?", "updated_at = ?"]
        params: list[Any] = [normalize_status(status), _now_iso()]
        if broker_order_id is not None:
            sets.append("broker_order_id = ?")
            params.append(str(broker_order_id))
        if broker_json is not None:
            sets.append("broker_json = ?")
            params.append(json.dumps(broker_json, default=_json_default))
        params.append(client_order_id)
        with self._conn:
            self._conn.execute(f"UPDATE orders SET {', '.join(sets)} WHERE client_order_id = ?", params)

    def get(self, client_order_id: str) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT * FROM orders WHERE client_order_id = ?", (client_order_id,)).fetchone()
        return self._row_to_dict(row) if row is not None else None

    def pending(self) -> list[dict[str, Any]]:
        """Rows whose status is not terminal (includes SUBMITTING and ERROR)."""
        placeholders = ", ".join("?" * len(TERMINAL_STATUSES))
        rows = self._conn.execute(
            f"SELECT * FROM orders WHERE status NOT IN ({placeholders}) ORDER BY created_at",
            tuple(sorted(TERMINAL_STATUSES)),
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def all(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT * FROM orders ORDER BY created_at").fetchall()
        return [self._row_to_dict(r) for r in rows]

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["intent"] = json.loads(d.pop("intent_json"))
        raw = d.pop("broker_json")
        d["broker"] = json.loads(raw) if raw else None
        return d
