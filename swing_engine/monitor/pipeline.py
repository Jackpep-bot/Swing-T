"""Pipeline: normalize -> dedup -> event log -> stage-1 rules -> priority -> Haiku stage-2 -> alert policy -> delivery.

Haiku may only (a) drop a non-held P1/P2 to P0 when it says relevance "none", or (b) lift a P1 to P2 when it says
relevance "high" with materiality >= 4. It never touches P3 and never adds symbols.

The work is split in two so the service can keep the queue moving: ``prepare`` is synchronous (no network:
normalize, dedup, event log, rules, small-cap bookkeeping) and ``finish`` awaits the slow parts (classification,
delivery, audit). ``process`` runs both inline for tests and replay. P3 deliveries go to every channel
concurrently, so a slow or rate-limited channel never delays the emergency push on another.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from swing_engine.core.interfaces import Deliverer, Rule
from swing_engine.core.models import Classification, Event, Priority

from .alerts import AlertDecision, AlertPolicy
from .constants import CLASSIFY_UPGRADE_MATERIALITY, PRIORITY_RANK
from .dedup import Deduper
from .eventlog import EventLog
from .matcher import Matcher
from .rules.market_wide_suppression import (
    CIRCUIT_BREAKER_HIT,
    SUPPRESSED_HIT,
    expire_suppression,
    note_circuit_breaker,
)

log = structlog.get_logger(__name__)

CLASSIFY_KINDS: frozenset[str] = frozenset({"news", "filing", "halt", "social", "bar_trigger"})
DIGEST_FALLBACK_CHANNELS: tuple[str, ...] = ("telegram", "console")
POSITION_QTY_KEY = "position_qty"


@dataclass
class PipelineResult:
    event: Event
    dropped: bool = False
    drop_reason: str = ""
    classification: Classification | None = None
    decision: AlertDecision | None = None
    delivered: list[str] = field(default_factory=list)

    @property
    def priority(self) -> str:
        return str(self.event.priority)


class Pipeline:
    def __init__(
        self,
        rules: Sequence[Rule],
        classifier: Any | None = None,
        policy: AlertPolicy | None = None,
        deliverers: Iterable[Deliverer] | None = None,
        eventlog: EventLog | None = None,
        deduper: Deduper | None = None,
        matcher: Matcher | None = None,
        ctx: dict[str, Any] | None = None,
        audit_path: str | Path | None = None,
        smallcap: Any | None = None,
        classify_min_priority: str = "P1",
        digest_channels: Sequence[str] = DIGEST_FALLBACK_CHANNELS,
        clock: Callable[[], datetime] | None = None,
    ):
        self.rules = list(rules)
        self.classifier = classifier
        self.policy = policy or AlertPolicy()
        self.deliverers: dict[str, Deliverer] = {d.name: d for d in (deliverers or [])}
        self.eventlog = eventlog
        self.deduper = deduper or Deduper()
        self.matcher = matcher
        self.ctx: dict[str, Any] = ctx if ctx is not None else {}
        self.ctx["held"] = {s.upper() for s in self.ctx.get("held", ())}
        self.ctx["watchlist"] = {s.upper() for s in self.ctx.get("watchlist", ())}
        self.ctx.setdefault("news_tagged", {})
        self.ctx.setdefault("form4_history", {})
        self.audit_path = Path(audit_path) if audit_path else None
        self.smallcap = smallcap
        self.classify_min = PRIORITY_RANK[classify_min_priority]
        self.digest_channels = tuple(digest_channels)
        self.clock = clock or (lambda: datetime.now(UTC))
        self.stats: dict[str, int] = {"received": 0, "dropped": 0, "classified": 0, "delivered": 0}
        #: set by the service during shutdown: skip classification so queued events drain quickly
        self.draining = False

    # ---- main entry ------------------------------------------------------------------------------------------
    async def process(self, event: Event) -> PipelineResult:
        """Full inline run (tests, replay): ``prepare`` then ``finish``."""
        res = self.prepare(event)
        if res.dropped:
            return res
        return await self.finish(res)

    def prepare(self, event: Event) -> PipelineResult:
        """Synchronous stages: normalize, dedup, event log, rules, small-cap memory. Never awaits."""
        self.stats["received"] += 1
        res = PipelineResult(event=event)
        self._normalize(event)
        reason = self.deduper.check(event)
        if reason:
            return self._drop(res, reason)
        if self.eventlog is not None and not self.eventlog.append(event):
            return self._drop(res, f"duplicate_id:{event.event_id}")
        self._touch_context(event)
        self._run_rules(event)
        if self.eventlog is not None:
            self.eventlog.update(event)
        if self.smallcap is not None:
            try:
                self.smallcap.observe(event)
            except Exception:  # noqa: BLE001 - a scorer bug must not stop delivery
                log.exception("smallcap.observe_failed", event_id=event.event_id)
        return res

    async def finish(self, res: PipelineResult) -> PipelineResult:
        """Slow stages: Haiku classification (P1/P2 only), alert decision, delivery, audit."""
        event = res.event
        if self._should_classify(event):
            res.classification = await self._classify(event)
            if self.eventlog is not None:
                self.eventlog.update(event)
        res.decision = self.policy.decide(event, self.ctx)
        if res.decision.deliver:
            res.delivered = await self._deliver(event, res.decision)
        self._audit(res)
        return res

    async def flush_digest_if_due(self, force: bool = False) -> bool:
        if not force and not self.policy.digest_due():
            return False
        msg = self.policy.flush_digest()
        if msg is None:
            return False
        title, body = msg
        delivered = False
        for name in self.digest_channels:
            d = self.deliverers.get(name)
            if d is not None and await d.send(title, body, str(Priority.P1), {"digest": True}):
                delivered = True
                break
        return delivered

    # ---- stages ----------------------------------------------------------------------------------------------
    def _normalize(self, event: Event) -> None:
        event.symbols = sorted({s.upper().strip() for s in event.symbols if s and s.strip()})
        if self.matcher is not None and event.kind in ("news", "social", "filing"):
            symbols, keywords = self.matcher.match(f"{event.title}\n{event.body}")
            if symbols:
                event.symbols = sorted(set(event.symbols) | set(symbols))
            if keywords:
                event.meta["keywords"] = sorted(set(event.meta.get("keywords", [])) | set(keywords))

    def _touch_context(self, event: Event) -> None:
        self.ctx["now"] = event.ts_received
        if expire_suppression(self.ctx, event.ts_received):
            log.info("market_suppression_expired", at=event.ts_received.isoformat())
        if event.kind in ("news", "filing"):
            for s in event.symbols:
                self.ctx["news_tagged"][s] = event.ts_received
        elif event.kind == "account":
            self._update_held(event)

    def _update_held(self, event: Event) -> None:
        """Keep ``ctx["held"]`` current from broker trade updates (``position_qty`` after the fill)."""
        raw = event.meta.get(POSITION_QTY_KEY)
        if raw is None:
            return
        try:
            qty = float(raw)
        except (TypeError, ValueError):
            return
        held: set[str] = self.ctx["held"]
        for sym in event.symbols:
            if qty > 0:
                if sym not in held:
                    log.info("held.added", symbol=sym, position_qty=qty)
                held.add(sym)
            elif sym in held:
                log.info("held.removed", symbol=sym)
                held.discard(sym)

    def _run_rules(self, event: Event) -> None:
        hits: list[str] = []
        best = "P0"
        suppressed = False
        for rule in self.rules:
            try:
                out = rule.evaluate(event, self.ctx)
            except Exception:  # noqa: BLE001 - one bad rule must not kill the pipeline
                log.exception("rule.failed", rule=rule.name, event_id=event.event_id)
                continue
            if out is None:
                continue
            hit, prio = out
            hits.append(hit)
            if hit == SUPPRESSED_HIT:
                suppressed = True
                continue
            if hit == CIRCUIT_BREAKER_HIT:
                note_circuit_breaker(self.ctx, event.ts_received)
            if PRIORITY_RANK[prio] > PRIORITY_RANK[best]:
                best = prio
        if suppressed:
            best = "P0"
        event.rule_hits = hits
        event.priority = Priority(best)

    def _should_classify(self, event: Event) -> bool:
        if self.classifier is None or self.draining or event.kind not in CLASSIFY_KINDS:
            return False
        return PRIORITY_RANK[str(event.priority)] >= self.classify_min and str(event.priority) != Priority.P3

    async def _classify(self, event: Event) -> Classification | None:
        try:
            cls = await self.classifier.classify(event, self.ctx)
        except Exception:  # noqa: BLE001 - rules-only fallback on any classifier failure
            log.exception("classify.failed", event_id=event.event_id)
            return None
        if cls is None:
            event.rule_hits.append("haiku:fallback")
            return None
        self.stats["classified"] += 1
        event.meta["classification"] = cls.model_dump()
        held = bool(self.ctx["held"] & set(event.symbols))
        prio = str(event.priority)
        if cls.relevance == "none" and not held and prio in (Priority.P1, Priority.P2):
            event.priority = Priority.P0
            event.rule_hits.append("haiku:none")
        elif prio == Priority.P1 and cls.relevance == "high" and cls.materiality >= CLASSIFY_UPGRADE_MATERIALITY:
            event.priority = Priority.P2
            event.rule_hits.append("haiku:upgrade")
        return cls

    async def _send(self, name: str, deliverer: Deliverer, event: Event, title: str, body: str) -> tuple[str, bool]:
        try:
            ok = await deliverer.send(title, body, str(event.priority), {"url": event.url, "event_id": event.event_id})
        except Exception:  # noqa: BLE001 - keep trying the other channels
            log.exception("deliver.failed", channel=name, event_id=event.event_id)
            ok = False
        return name, bool(ok)

    async def _deliver(self, event: Event, decision: AlertDecision) -> list[str]:
        title, body = self.policy.format(event)
        targets = [(name, self.deliverers[name]) for name in decision.channels if name in self.deliverers]
        if str(event.priority) == Priority.P3 and len(targets) > 1:
            # emergency: every channel at once; a Telegram 429 must not delay the Pushover emergency push
            results = await asyncio.gather(*(self._send(n, d, event, title, body) for n, d in targets))
        else:
            results = [await self._send(n, d, event, title, body) for n, d in targets]
        delivered = [name for name, ok in results if ok]
        if delivered:
            self.stats["delivered"] += 1
        if self.eventlog is not None:
            self.eventlog.record_alert(event.event_id, str(event.priority), delivered, bool(delivered), decision.reason)
        return delivered

    def _drop(self, res: PipelineResult, reason: str) -> PipelineResult:
        res.dropped = True
        res.drop_reason = reason
        self.stats["dropped"] += 1
        log.debug("event.dropped", event_id=res.event.event_id, reason=reason)
        return res

    def _audit(self, res: PipelineResult) -> None:
        if self.audit_path is None or res.decision is None or not (res.decision.deliver or res.decision.digest):
            return
        e = res.event
        row = {
            "ts": self.clock().isoformat(),
            "event_id": e.event_id,
            "source": e.source,
            "kind": e.kind,
            "symbols": e.symbols,
            "priority": str(e.priority),
            "rule_hits": e.rule_hits,
            "title": e.title[:200],
            "channels": res.decision.channels,
            "delivered": res.delivered,
            "reason": res.decision.reason,
            "classification": e.meta.get("classification"),
        }
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
