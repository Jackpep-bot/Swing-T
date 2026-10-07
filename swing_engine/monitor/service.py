"""Asyncio supervisor: one task per feed -> queue -> pipeline; market-hours-aware staleness watchdog; digest timer;
graceful shutdown on SIGINT/SIGTERM. `dry_run` wires the console deliverer and the file feed only.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import signal
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from swing_engine.core import registry
from swing_engine.core.config import ROOT, Secrets, Settings
from swing_engine.core.interfaces import Deliverer, Feed, Rule
from swing_engine.core.models import Event, Priority

from .adapters._base import stable_id
from .adapters.file_feed import FileFeed
from .alerts import AlertPolicy
from .classify import HaikuClassifier
from .constants import (
    AUDIT_PATH_DEFAULT,
    QUEUE_MAXSIZE,
    REPLAY_FILE_DEFAULT,
    SHUTDOWN_GRACE_S,
    STALENESS_DEFAULT_S,
    STALENESS_THRESHOLD_S,
    WATCHDOG_INTERVAL_S,
)
from .dedup import Deduper
from .delivery.console import ConsoleDeliverer
from .eventlog import EventLog
from .hours import is_market_hours
from .matcher import Matcher
from .pipeline import Pipeline
from .smallcap import SmallCapTrack

log = structlog.get_logger(__name__)
REPLAY_ENV = "SWING_MONITOR_REPLAY_FILE"


def resolve_path(path: str | Path) -> str:
    """Relative settings paths (event log, audit file, replay fixture) are relative to the repo root, not the CWD."""
    p = Path(path)
    return str(p if p.is_absolute() else ROOT / p)


def build_rules(names: Sequence[str] | None = None) -> list[Rule]:
    return [registry.get("rule", n)() for n in (names or registry.names("rule"))]


def build_deliverers(secrets: Secrets, dry_run: bool) -> list[Deliverer]:
    out: list[Deliverer] = [ConsoleDeliverer()]
    if dry_run:
        return out
    if secrets.telegram_bot_token and secrets.telegram_chat_id:
        out.append(registry.get("deliverer", "telegram")(secrets.telegram_bot_token, secrets.telegram_chat_id))
    if secrets.pushover_user_key and secrets.pushover_app_token:
        out.append(registry.get("deliverer", "pushover")(secrets.pushover_user_key, secrets.pushover_app_token))
    return out


def build_feeds(settings: Settings, secrets: Secrets, dry_run: bool, names: Sequence[str] | None = None) -> list[Feed]:
    if dry_run:
        path = os.environ.get(REPLAY_ENV, REPLAY_FILE_DEFAULT)
        return [FileFeed(resolve_path(path), rebase_received=True)]
    feeds: list[Feed] = []
    key, secret = secrets.alpaca_api_key or "", secrets.alpaca_secret_key or ""
    for name in names or settings.monitor.feeds:
        cls = registry.get("feed", name)
        if name == "alpaca_news":
            feeds.append(cls(key, secret))
        elif name == "alpaca_stocks":
            feeds.append(cls(key, secret, symbols=settings.monitor.watchlist or ["*"]))
        elif name == "alpaca_account":
            feeds.append(cls(key, secret, paper=secrets.alpaca_paper))
        elif name == "edgar":
            feeds.append(cls(secrets.edgar_user_agent))
        else:
            feeds.append(cls())
    return feeds


class MonitorService:
    def __init__(
        self,
        feeds: Sequence[Feed],
        pipeline: Pipeline,
        clock: Callable[[], datetime] | None = None,
        watchdog_interval_s: float = WATCHDOG_INTERVAL_S,
        staleness: dict[str, float] | None = None,
        stop_when_feeds_end: bool = False,
    ):
        self.feeds = list(feeds)
        self.pipeline = pipeline
        self.clock = clock or (lambda: datetime.now(UTC))
        self.watchdog_interval_s = watchdog_interval_s
        self.staleness = {**STALENESS_THRESHOLD_S, **(staleness or {})}
        self.stop_when_feeds_end = stop_when_feeds_end
        self._queue: asyncio.Queue[Event | None] = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task[Any]] = []
        self.last_seen: dict[str, datetime] = {}
        self.stale_alerted: set[str] = set()
        self.processed = 0
        self._t0 = self.clock()

    # ---- lifecycle --------------------------------------------------------------------------------------------
    async def run(self) -> None:
        self._install_signals()
        feed_tasks = [asyncio.create_task(self._feed_task(f), name=f"feed:{f.name}") for f in self.feeds]
        self._tasks = [
            *feed_tasks,
            asyncio.create_task(self._consumer(), name="consumer"),
            asyncio.create_task(self._watchdog(), name="watchdog"),
            asyncio.create_task(self._digest_timer(), name="digest"),
        ]
        if self.stop_when_feeds_end:
            self._tasks.append(asyncio.create_task(self._stop_after(feed_tasks), name="feeds-done"))
        log.info("monitor.start", feeds=[f.name for f in self.feeds], rules=[r.name for r in self.pipeline.rules])
        await self._stop.wait()
        await self.shutdown()

    def stop(self) -> None:
        self._stop.set()

    async def shutdown(self) -> None:
        log.info("monitor.shutdown", processed=self.processed, stats=self.pipeline.stats)
        for f in self.feeds:
            stop = getattr(f, "stop", None)
            if callable(stop):
                stop()
        await self._queue.put(None)
        for t in self._tasks:
            if not t.done() and t.get_name() != "consumer":
                t.cancel()
        consumer = next((t for t in self._tasks if t.get_name() == "consumer"), None)
        if consumer is not None:
            with contextlib.suppress(TimeoutError, asyncio.CancelledError):
                await asyncio.wait_for(consumer, timeout=SHUTDOWN_GRACE_S)
        for t in self._tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t
        with contextlib.suppress(Exception):
            await self.pipeline.flush_digest_if_due(force=True)
        if self.pipeline.eventlog is not None:
            self.pipeline.eventlog.close()

    def _install_signals(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError, RuntimeError, ValueError):
                loop.add_signal_handler(sig, self.stop)

    # ---- tasks --------------------------------------------------------------------------------------------------
    async def _feed_task(self, feed: Feed) -> None:
        try:
            async for ev in feed.events():
                self.last_seen[feed.name] = self.clock()
                self.stale_alerted.discard(feed.name)
                await self._queue.put(ev)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - feeds own their reconnects; a crash here is a bug worth surfacing
            log.exception("feed.crashed", feed=feed.name)
            await self._queue.put(self._synthetic(feed.name, "feed_crashed", Priority.P3))

    async def _consumer(self) -> None:
        while True:
            item = await self._queue.get()
            if item is None:
                break
            try:
                await self.pipeline.process(item)
                self.processed += 1
            except Exception:  # noqa: BLE001 - never let one event stop the consumer
                log.exception("pipeline.failed", event_id=item.event_id)

    async def _watchdog(self) -> None:
        while not self._stop.is_set():
            await asyncio.sleep(self.watchdog_interval_s)
            await self.check_staleness()

    async def check_staleness(self, now: datetime | None = None) -> list[str]:
        now = now or self.clock()
        if not is_market_hours(now):
            return []
        stale: list[str] = []
        for f in self.feeds:
            if f.name == "file":
                continue
            last = self.last_seen.get(f.name)
            threshold = self.staleness.get(f.name, STALENESS_DEFAULT_S)
            age = (now - last).total_seconds() if last else None
            if age is not None and age <= threshold:
                continue
            if last is None and (now - self._started_at).total_seconds() <= threshold:
                continue
            stale.append(f.name)
            if f.name not in self.stale_alerted:
                self.stale_alerted.add(f.name)
                await self._queue.put(self._synthetic(f.name, "feed_dead", Priority.P3, age))
        return stale

    async def _digest_timer(self) -> None:
        while not self._stop.is_set():
            await asyncio.sleep(self.watchdog_interval_s)
            with contextlib.suppress(Exception):
                await self.pipeline.flush_digest_if_due()

    async def _stop_after(self, feed_tasks: list[asyncio.Task[Any]]) -> None:
        await asyncio.gather(*feed_tasks, return_exceptions=True)
        await self._queue.put(None)
        self._stop.set()

    def _synthetic(self, feed: str, what: str, priority: Priority, age: float | None = None) -> Event:
        now = self.clock()
        return Event(
            event_id=stable_id("monitor", what, feed, now.isoformat()),
            source="monitor",
            kind="ops",
            ts_source=now,
            ts_received=now,
            title=f"{what}: {feed}" + (f" (silent {age:.0f}s)" if age else ""),
            meta={"feed": feed, "what": what, "age_s": age},
            priority=priority,
            rule_hits=[what],
        )

    @property
    def _started_at(self) -> datetime:
        return self._t0


class OpsRule(Rule):
    """Ops events from the service itself (feed dead, kill switch) keep the priority they were created with."""

    name = "ops_passthrough"

    def evaluate(self, event: Event, ctx: dict[str, Any]) -> tuple[str, str] | None:
        if event.kind != "ops":
            return None
        return str(event.meta.get("what", "ops")), str(event.priority)


def build_pipeline(settings: Settings, secrets: Secrets, dry_run: bool, deliverers: Sequence[Deliverer] | None = None) -> Pipeline:
    mon = settings.monitor
    rules: list[Rule] = [*build_rules(), OpsRule()]
    classifier = None
    if not dry_run and secrets.anthropic_api_key:
        classifier = HaikuClassifier(model=mon.classify_model, api_key=secrets.anthropic_api_key)
    policy = AlertPolicy(cooldown_min=mon.per_ticker_cooldown_min, hourly_cap=mon.hourly_alert_cap,
                         quiet_hours_et=tuple(mon.quiet_hours_et))
    watch = {s.upper() for s in mon.watchlist}
    matcher = Matcher(tickers=watch, keywords=mon.keywords) if (watch or mon.keywords) else None
    eventlog = EventLog(":memory:" if dry_run else resolve_path(settings.data.event_log_path))
    smallcap = SmallCapTrack(mon.smallcap) if mon.smallcap.get("enabled", True) else None
    return Pipeline(
        rules=rules,
        classifier=classifier,
        policy=policy,
        deliverers=deliverers if deliverers is not None else build_deliverers(secrets, dry_run),
        eventlog=eventlog,
        deduper=Deduper(),
        matcher=matcher,
        ctx={"held": set(), "watchlist": watch, "settings": mon},
        audit_path=None if dry_run else resolve_path(AUDIT_PATH_DEFAULT),
        smallcap=smallcap,
    )


async def run_monitor_async(settings: Settings, secrets: Secrets, dry_run: bool = False, feeds: Sequence[str] | None = None) -> MonitorService:
    pipeline = build_pipeline(settings, secrets, dry_run)
    feed_objs = build_feeds(settings, secrets, dry_run, feeds)
    service = MonitorService(feed_objs, pipeline, stop_when_feeds_end=dry_run)
    await service.run()
    return service


def run_monitor(settings: Settings, secrets: Secrets, dry_run: bool = False, feeds: Sequence[str] | None = None) -> None:
    """Entry point for `swing monitor run`. Blocks until SIGINT/SIGTERM (or until the file feed ends in dry_run)."""
    asyncio.run(run_monitor_async(settings, secrets, dry_run=dry_run, feeds=feeds))
