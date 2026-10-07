"""Alert policy: priority routing (P1 digest / P2 push / P3 emergency), per-ticker cooldown, hourly cap, quiet hours.

P3 bypasses cooldown, cap and quiet hours (a halt on a held position is never throttled). P2 on a held symbol
bypasses quiet hours only. Everything throttled is demoted to the digest, never dropped. The cooldown applies to
every symbol on an event (not only the first after sorting), so one story tagged with different symbol sets by two
feeds cannot push twice.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from swing_engine.core.models import Event, Priority

from .constants import ALERT_BODY_MAX, ALERT_TITLE_MAX, DEFAULT_ROUTING, DIGEST_TIMES_ET, PRIORITY_RANK
from .hours import to_et

log = structlog.get_logger(__name__)


@dataclass
class AlertDecision:
    deliver: bool
    channels: list[str]
    reason: str
    digest: bool = False


@dataclass
class DigestEntry:
    ts: datetime
    event_id: str
    priority: str
    line: str


@dataclass
class AlertPolicy:
    cooldown_min: int = 15
    hourly_cap: int = 20
    quiet_hours_et: tuple[int, int] = (22, 6)
    routing: Mapping[str, Sequence[str]] = field(default_factory=lambda: dict(DEFAULT_ROUTING))
    clock: Callable[[], datetime] = field(default_factory=lambda: (lambda: datetime.now(UTC)))
    _last_push: dict[str, datetime] = field(default_factory=dict)
    _push_times: deque[datetime] = field(default_factory=deque)
    _digest: list[DigestEntry] = field(default_factory=list)
    _last_digest_flush: datetime | None = None

    # ---- decisions -------------------------------------------------------------------------------------------
    def decide(self, event: Event, ctx: dict[str, Any] | None = None) -> AlertDecision:
        ctx = ctx or {}
        now = self.clock()
        prio = str(event.priority)
        held = bool({s.upper() for s in ctx.get("held", ())} & {s.upper() for s in event.symbols})
        if prio == Priority.P0:
            return AlertDecision(False, [], "p0_dropped")
        if prio == Priority.P1:
            self.queue_digest(event, now)
            return AlertDecision(False, list(self.routing.get("P1", ())), "digest", digest=True)
        if prio == Priority.P3:
            self._note_push(event, now)
            return AlertDecision(True, list(self.routing.get("P3", ())), "p3_emergency")
        # P2
        if self.in_quiet_hours(now) and not held:
            self.queue_digest(event, now)
            return AlertDecision(False, list(self.routing.get("P1", ())), "quiet_hours", digest=True)
        cooling = self._cooling_key(event, now)
        if cooling is not None:
            self.queue_digest(event, now)
            return AlertDecision(False, list(self.routing.get("P1", ())), f"cooldown:{cooling}", digest=True)
        self._prune_pushes(now)
        if len(self._push_times) >= self.hourly_cap:
            self.queue_digest(event, now)
            return AlertDecision(False, list(self.routing.get("P1", ())), "hourly_cap", digest=True)
        self._note_push(event, now)
        return AlertDecision(True, list(self.routing.get("P2", ())), "p2_push")

    def in_quiet_hours(self, now: datetime | None = None) -> bool:
        hour = to_et(now or self.clock()).hour
        start, end = self.quiet_hours_et
        if start == end:
            return False
        if start < end:
            return start <= hour < end
        return hour >= start or hour < end

    # ---- digest ----------------------------------------------------------------------------------------------
    def queue_digest(self, event: Event, now: datetime | None = None) -> None:
        now = now or self.clock()
        syms = ",".join(event.symbols[:4]) or "-"
        hits = ",".join(event.rule_hits[:3])
        line = f"[{event.priority}] {syms} {event.title[:100]} ({event.source}; {hits})"
        self._digest.append(DigestEntry(ts=now, event_id=event.event_id, priority=str(event.priority), line=line))

    def digest_due(self, now: datetime | None = None) -> bool:
        now = now or self.clock()
        et = to_et(now)
        for t in DIGEST_TIMES_ET:
            slot = et.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
            if et >= slot and (self._last_digest_flush is None or to_et(self._last_digest_flush) < slot):
                return True
        return False

    def flush_digest(self, now: datetime | None = None) -> tuple[str, str] | None:
        now = now or self.clock()
        self._last_digest_flush = now
        if not self._digest:
            return None
        entries, self._digest = self._digest, []
        entries.sort(key=lambda e: -PRIORITY_RANK[e.priority])
        title = f"Digest: {len(entries)} items ({to_et(now):%H:%M ET})"
        body = "\n".join(e.line for e in entries[:60])
        if len(entries) > 60:
            body += f"\n... and {len(entries) - 60} more"
        return title, body[:ALERT_BODY_MAX * 4]

    @property
    def digest_size(self) -> int:
        return len(self._digest)

    # ---- formatting ------------------------------------------------------------------------------------------
    @staticmethod
    def format(event: Event) -> tuple[str, str]:
        syms = " ".join(f"${s}" for s in event.symbols[:5]) or "(no ticker)"
        title = f"{event.priority} {syms}: {event.title or event.kind}"[:ALERT_TITLE_MAX]
        parts = [f"source={event.source} kind={event.kind}"]
        if event.rule_hits:
            parts.append("rules=" + ",".join(event.rule_hits))
        cls = event.meta.get("classification")
        if isinstance(cls, dict):
            parts.append(
                f"haiku={cls.get('event_type', '?')}/{cls.get('relevance', '?')}/m{cls.get('materiality', '?')}"
                f" {cls.get('suggested_action', '')}: {str(cls.get('rationale', ''))[:200]}"
            )
        if event.body:
            parts.append(event.body[:300])
        if event.url:
            parts.append(event.url)
        return title, "\n".join(parts)[:ALERT_BODY_MAX]

    # ---- internals -------------------------------------------------------------------------------------------
    @staticmethod
    def _cooldown_keys(event: Event) -> list[str]:
        return [s.upper() for s in event.symbols] or [f"kind:{event.kind}"]

    def _cooling_key(self, event: Event, now: datetime) -> str | None:
        """The first of the event's symbols still inside the cooldown window, or None."""
        window = timedelta(minutes=self.cooldown_min)
        for key in self._cooldown_keys(event):
            last = self._last_push.get(key)
            if last is not None and now - last < window:
                return key
        return None

    def _note_push(self, event: Event, now: datetime) -> None:
        for key in self._cooldown_keys(event):
            self._last_push[key] = now
        self._push_times.append(now)
        self._prune_pushes(now)

    def _prune_pushes(self, now: datetime) -> None:
        cutoff = now - timedelta(hours=1)
        while self._push_times and self._push_times[0] < cutoff:
            self._push_times.popleft()
