"""SQLite (WAL) event log: UNIQUE(event_id), per-source replay cursors, recent-window reads."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import structlog

from swing_engine.core.models import Event, Priority

log = structlog.get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id    TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    kind        TEXT NOT NULL,
    ts_source   TEXT NOT NULL,
    ts_received TEXT NOT NULL,
    symbols     TEXT NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    body        TEXT NOT NULL DEFAULT '',
    url         TEXT,
    meta        TEXT NOT NULL DEFAULT '{}',
    priority    TEXT NOT NULL DEFAULT 'P0',
    rule_hits   TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_events_received ON events (ts_received);
CREATE INDEX IF NOT EXISTS idx_events_source ON events (source, ts_received);
CREATE TABLE IF NOT EXISTS cursors (
    source     TEXT PRIMARY KEY,
    cursor     TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    TEXT NOT NULL,
    ts          TEXT NOT NULL,
    priority    TEXT NOT NULL,
    channels    TEXT NOT NULL,
    delivered   INTEGER NOT NULL,
    reason      TEXT NOT NULL DEFAULT ''
);
"""


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def _parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


class EventLog:
    """Append-only event store. `append` is idempotent on `event_id` (returns False on duplicate)."""

    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        if self.path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_SCHEMA)

    # ---- events ----------------------------------------------------------------------------------------------
    def append(self, event: Event) -> bool:
        row = (
            event.event_id, event.source, event.kind, _iso(event.ts_source), _iso(event.ts_received),
            json.dumps(event.symbols), event.title, event.body, event.url, json.dumps(event.meta, default=str),
            str(event.priority), json.dumps(event.rule_hits),
        )
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT INTO events (event_id, source, kind, ts_source, ts_received, symbols, title, body, url,"
                    " meta, priority, rule_hits) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    row,
                )
            except sqlite3.IntegrityError:
                return False
        return True

    def update(self, event: Event) -> None:
        """Persist priority / rule hits / meta after the rule stage."""
        with self._lock:
            self._conn.execute(
                "UPDATE events SET priority=?, rule_hits=?, meta=?, symbols=? WHERE event_id=?",
                (str(event.priority), json.dumps(event.rule_hits), json.dumps(event.meta, default=str),
                 json.dumps(event.symbols), event.event_id),
            )

    def contains(self, event_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("SELECT 1 FROM events WHERE event_id=?", (event_id,))
            return cur.fetchone() is not None

    def get(self, event_id: str) -> Event | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM events WHERE event_id=?", (event_id,)).fetchone()
        return self._row_to_event(row) if row else None

    def recent(self, hours: float = 24.0, source: str | None = None, now: datetime | None = None) -> list[Event]:
        since = _iso((now or datetime.now(UTC)) - timedelta(hours=hours))
        q = "SELECT * FROM events WHERE ts_received >= ?"
        args: list[object] = [since]
        if source:
            q += " AND source = ?"
            args.append(source)
        q += " ORDER BY ts_received ASC"
        with self._lock:
            rows = self._conn.execute(q, args).fetchall()
        return [self._row_to_event(r) for r in rows]

    def count(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])

    # ---- cursors ---------------------------------------------------------------------------------------------
    def cursor(self, source: str) -> str | None:
        with self._lock:
            row = self._conn.execute("SELECT cursor FROM cursors WHERE source=?", (source,)).fetchone()
        return row["cursor"] if row else None

    def set_cursor(self, source: str, cursor: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO cursors (source, cursor, updated_at) VALUES (?,?,?)"
                " ON CONFLICT(source) DO UPDATE SET cursor=excluded.cursor, updated_at=excluded.updated_at",
                (source, cursor, _iso(datetime.now(UTC))),
            )

    # ---- alerts audit ----------------------------------------------------------------------------------------
    def record_alert(self, event_id: str, priority: str, channels: list[str], delivered: bool, reason: str = "") -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO alerts (event_id, ts, priority, channels, delivered, reason) VALUES (?,?,?,?,?,?)",
                (event_id, _iso(datetime.now(UTC)), priority, json.dumps(channels), int(delivered), reason),
            )

    def recent_alerts(self, hours: float = 24.0, now: datetime | None = None) -> list[dict]:
        since = _iso((now or datetime.now(UTC)) - timedelta(hours=hours))
        with self._lock:
            rows = self._conn.execute("SELECT * FROM alerts WHERE ts >= ? ORDER BY ts ASC", (since,)).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---- helpers ---------------------------------------------------------------------------------------------
    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> Event:
        return Event(
            event_id=row["event_id"], source=row["source"], kind=row["kind"],
            ts_source=_parse_dt(row["ts_source"]), ts_received=_parse_dt(row["ts_received"]),
            symbols=json.loads(row["symbols"]), title=row["title"], body=row["body"], url=row["url"],
            meta=json.loads(row["meta"]), priority=Priority(row["priority"]), rule_hits=json.loads(row["rule_hits"]),
        )
