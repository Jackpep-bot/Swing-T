"""Alert ratings (useful / noise / traded): the human feedback the gate in docs/gates.md needs per rule.

``rate_alert(eventlog, event_id, rating, source)`` writes the rating into the event's meta (``meta["rating"]``,
``meta["rating_source"]``, ``meta["rated_at"]``) so ``monitor.outcomes.compute_outcomes`` tags the outcome row,
and appends one row per press to the ``alert_ratings`` history table in the same SQLite file (a re-rating
overwrites the meta value; the history keeps every press). Sources: the Telegram inline keyboard on P2/P3
alerts (``service.TelegramUpdatesFeed``, callback data ``<rating>:<event_id>``) and the CLI (``rate_cli``,
wired as ``swing monitor rate``). A rating is an enum; nothing here produces a number.
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

import structlog
from pydantic import BaseModel, Field

from swing_engine.core.config import ROOT, Settings
from swing_engine.core.models import Event

from .eventlog import EventLog

log = structlog.get_logger(__name__)


class AlertRating(StrEnum):
    USEFUL = "useful"
    NOISE = "noise"
    TRADED = "traded"


RATING_KEY = "rating"
RATING_SOURCE_KEY = "rating_source"
RATED_AT_KEY = "rated_at"
RATINGS_TABLE = "alert_ratings"
SOURCE_TELEGRAM = "telegram"
SOURCE_CLI = "cli"
CALLBACK_SEP = ":"
#: Telegram Bot API limit for InlineKeyboardButton.callback_data
CALLBACK_DATA_MAX_BYTES = 64
REASON_UNKNOWN_EVENT = "unknown_event"
REASON_LOG_FAILED = "eventlog_failed"

_RATINGS_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {RATINGS_TABLE} (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id  TEXT NOT NULL,
    ts        TEXT NOT NULL,
    rating    TEXT NOT NULL,
    source    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_{RATINGS_TABLE}_event ON {RATINGS_TABLE} (event_id);
"""


class RatableLog(Protocol):
    """What rating needs from an event log (``EventLog`` satisfies it; tests pass a fake)."""

    def get(self, event_id: str) -> Event | None: ...

    def update(self, event: Event) -> None: ...


class RatingResult(BaseModel):
    ok: bool
    event_id: str
    rating: AlertRating | None = None
    source: str = ""
    reason: str = ""
    previous: str | None = None
    symbols: list[str] = Field(default_factory=list)
    title: str = ""
    history_recorded: bool = False

    def summary(self) -> str:
        if not self.ok:
            return f"not rated: {self.event_id} ({self.reason})"
        syms = ",".join(self.symbols) or "-"
        prev = f" (was {self.previous})" if self.previous and self.previous != self.rating else ""
        return f"rated {self.rating} via {self.source}: {syms} {self.title[:80]}{prev}"


# ---- parsing ---------------------------------------------------------------------------------------------
def parse_rating(value: str | AlertRating) -> AlertRating:
    """`AlertRating` from user input (case/space-insensitive); ValueError on anything else."""
    text = str(value).strip().lower()
    try:
        return AlertRating(text)
    except ValueError as exc:
        allowed = ", ".join(r.value for r in AlertRating)
        raise ValueError(f"rating must be one of {allowed}, got {value!r}") from exc


def callback_data(rating: AlertRating, event_id: str) -> str | None:
    """``<rating>:<event_id>`` for an inline button, or None when it would exceed Telegram's 64-byte limit."""
    data = f"{AlertRating(rating).value}{CALLBACK_SEP}{event_id}"
    return data if event_id and len(data.encode("utf-8")) <= CALLBACK_DATA_MAX_BYTES else None


def parse_callback_data(data: str | None) -> tuple[AlertRating, str] | None:
    """Inverse of :func:`callback_data` (event ids may themselves contain ``:``); None when malformed."""
    if not data or CALLBACK_SEP not in data:
        return None
    head, event_id = data.split(CALLBACK_SEP, 1)
    try:
        rating = AlertRating(head)
    except ValueError:
        return None
    return (rating, event_id) if event_id else None


# ---- rating ----------------------------------------------------------------------------------------------
def rate_alert(
    eventlog: RatableLog,
    event_id: str,
    rating: str | AlertRating,
    source: str,
    *,
    now: datetime | None = None,
) -> RatingResult:
    """Persist ``rating`` on ``event_id``. ValueError on an invalid rating; ``ok=False`` for an unknown event."""
    value = parse_rating(rating)
    try:
        event = eventlog.get(event_id)
    except Exception as exc:  # noqa: BLE001 - a broken log must surface as a failed rating, not a crash
        log.warning("rating.lookup_failed", event_id=event_id, error=f"{type(exc).__name__}: {exc}"[:200])
        return RatingResult(ok=False, event_id=event_id, rating=value, source=source, reason=REASON_LOG_FAILED)
    if event is None:
        log.warning("rating.unknown_event", event_id=event_id, rating=value.value, source=source)
        return RatingResult(ok=False, event_id=event_id, rating=value, source=source, reason=REASON_UNKNOWN_EVENT)
    ts = (now or datetime.now(UTC)).astimezone(UTC).isoformat()
    previous = event.meta.get(RATING_KEY)
    event.meta[RATING_KEY] = value.value
    event.meta[RATING_SOURCE_KEY] = source
    event.meta[RATED_AT_KEY] = ts
    try:
        eventlog.update(event)
    except Exception as exc:  # noqa: BLE001
        log.warning("rating.update_failed", event_id=event_id, error=f"{type(exc).__name__}: {exc}"[:200])
        return RatingResult(ok=False, event_id=event_id, rating=value, source=source, reason=REASON_LOG_FAILED)
    recorded = _record_history(eventlog, event_id, value, source, ts)
    log.info("rating.recorded", event_id=event_id, rating=value.value, source=source, previous=previous)
    return RatingResult(
        ok=True, event_id=event_id, rating=value, source=source,
        previous=None if previous is None else str(previous), symbols=list(event.symbols), title=event.title,
        history_recorded=recorded,
    )


def ratings_history(eventlog: RatableLog, event_id: str | None = None) -> list[dict[str, Any]]:
    """Rows of ``alert_ratings`` (oldest first), optionally for one event; empty when the log has no table."""
    handle = _connection(eventlog)
    if handle is None:
        return []
    conn, lock = handle
    q = f"SELECT event_id, ts, rating, source FROM {RATINGS_TABLE}"
    args: list[Any] = []
    if event_id is not None:
        q += " WHERE event_id = ?"
        args.append(event_id)
    q += " ORDER BY id ASC"
    with lock:
        conn.executescript(_RATINGS_SCHEMA)
        rows = conn.execute(q, args).fetchall()
    return [dict(zip(("event_id", "ts", "rating", "source"), tuple(r), strict=True)) for r in rows]


def rate_cli(
    settings: Settings,
    event_id: str,
    rating: str,
    *,
    eventlog: RatableLog | None = None,
    source: str = SOURCE_CLI,
) -> RatingResult:
    """Entry point for ``swing monitor rate <event_id> <rating>``: opens the configured event log, rates, closes.
    ValueError on an invalid rating; check ``result.ok`` (``result.summary()`` is a one-line message)."""
    value = parse_rating(rating)
    own = eventlog is None
    log_: RatableLog = eventlog or EventLog(_resolve(settings.data.event_log_path))
    try:
        return rate_alert(log_, event_id.strip(), value, source)
    finally:
        if own and isinstance(log_, EventLog):
            log_.close()


# ---- internals -------------------------------------------------------------------------------------------
def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def _connection(eventlog: RatableLog) -> tuple[sqlite3.Connection, Any] | None:
    """The SQLite connection behind an ``EventLog`` (None for fakes / other stores). The ratings table lives in
    the event log file so ``data/events.sqlite`` stays the single record of alerts and ratings."""
    conn = getattr(eventlog, "_conn", None)
    if not isinstance(conn, sqlite3.Connection):
        return None
    lock = getattr(eventlog, "_lock", None) or threading.RLock()
    return conn, lock


def _record_history(eventlog: RatableLog, event_id: str, rating: AlertRating, source: str, ts: str) -> bool:
    handle = _connection(eventlog)
    if handle is None:
        return False
    conn, lock = handle
    try:
        with lock:
            conn.executescript(_RATINGS_SCHEMA)
            conn.execute(
                f"INSERT INTO {RATINGS_TABLE} (event_id, ts, rating, source) VALUES (?,?,?,?)",
                (event_id, ts, rating.value, source),
            )
    except sqlite3.Error as exc:
        log.warning("rating.history_failed", event_id=event_id, error=f"{type(exc).__name__}: {exc}"[:200])
        return False
    return True
