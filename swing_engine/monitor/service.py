"""Asyncio supervisor: one task per feed -> queue -> pipeline; market-hours-aware staleness watchdog; digest timer;
graceful shutdown on SIGINT/SIGTERM. `dry_run` wires the console deliverer and the file feed only.

Flow control: the single consumer only runs the synchronous half of the pipeline (`Pipeline.prepare`: dedup,
event log, rules) and hands classification + delivery (`Pipeline.finish`) to background tasks. P0-P2 share a
bounded pool of `PIPELINE_WORKERS`; a P3 always gets its own task immediately, so a burst of 8-K filings
waiting on Haiku can never delay a halt on a held position.

Liveness: the watchdog judges a feed by transport activity (`ReconnectingFeed.last_activity_at`: any received
frame or completed poll), falling back to emitted events for feeds without it, and only inside the ET window in
which silence is suspicious for that feed (`STALENESS_WINDOW_ET`).
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import signal
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

import structlog

from swing_engine.core import registry
from swing_engine.core.config import ROOT, Secrets, Settings
from swing_engine.core.interfaces import Deliverer, Feed, Rule
from swing_engine.core.models import Event, Priority

from .adapters._base import stable_id
from .adapters.alpaca_stocks import BarTriggerEngine, reference_from_panel
from .adapters.file_feed import FileFeed
from .alerts import AlertPolicy
from .classify import HaikuClassifier
from .constants import (
    AUDIT_PATH_DEFAULT,
    PIPELINE_WORKERS,
    QUEUE_MAXSIZE,
    REGULAR_CLOSE,
    REPLAY_FILE_DEFAULT,
    SHUTDOWN_DRAIN_S,
    SHUTDOWN_GRACE_S,
    STALENESS_DEFAULT_S,
    STALENESS_THRESHOLD_S,
    STALENESS_WINDOW_DEFAULT_ET,
    STALENESS_WINDOW_ET,
    WATCHDOG_INTERVAL_S,
)
from .dedup import Deduper
from .delivery.console import ConsoleDeliverer
from .eventlog import EventLog
from .hours import is_market_hours, session_phase, to_et
from .matcher import Matcher
from .pipeline import Pipeline, PipelineResult
from .smallcap import SmallCapTrack

log = structlog.get_logger(__name__)
REPLAY_ENV = "SWING_MONITOR_REPLAY_FILE"
#: store table `swing features` caches; its last row per symbol seeds the bar-trigger reference data
BAR_REFERENCE_TABLE = "panel"
STOCKS_FEED = "alpaca_stocks"


def resolve_path(path: str | Path) -> str:
    """Relative settings paths (event log, audit file, replay fixture) are relative to the repo root, not the CWD."""
    p = Path(path)
    return str(p if p.is_absolute() else ROOT / p)


def _utc_iso(ts: datetime) -> str:
    """ISO-8601 in UTC, so per-feed replay cursors compare correctly as strings."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC).isoformat()


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


def load_held_symbols(secrets: Secrets) -> set[str]:
    """Symbols the paper account holds right now, from the broker. Empty (and logged) when unavailable."""
    if not (secrets.alpaca_api_key and secrets.alpaca_secret_key):
        log.warning("held_positions_unavailable", reason="no alpaca keys; ctx['held'] starts empty")
        return set()
    try:
        from swing_engine.execution.alpaca_broker import AlpacaBroker

        broker = AlpacaBroker(secrets=secrets)
        held = {str(p.symbol).upper() for p in broker.positions()}
    except Exception as exc:  # noqa: BLE001 - the monitor must start even when the broker is down
        log.warning("held_positions_unavailable", error=f"{type(exc).__name__}: {exc}"[:200])
        return set()
    log.info("held_positions_loaded", held=sorted(held))
    return held


def load_bar_reference(settings: Settings) -> dict[str, dict[str, float]]:
    """Per-symbol {prev_close, avg_vol_20d, avg_vol_50d, high_52w} from the cached feature panel in the store."""
    path = Path(resolve_path(settings.data.store_path))
    if not path.exists():
        log.warning("bar_reference_unavailable", reason="no store", path=str(path))
        return {}
    try:
        from swing_engine.data.store import Store

        store = Store(str(path))
        try:
            panel = store.read_table(BAR_REFERENCE_TABLE)
        finally:
            store.close()
    except Exception as exc:  # noqa: BLE001 - bars are optional input; the monitor still runs without them
        log.warning("bar_reference_unavailable", error=f"{type(exc).__name__}: {exc}"[:200])
        return {}
    return reference_from_panel(panel)


def build_bar_engine(
    settings: Settings,
    held: set[str] | None = None,
    reference: dict[str, dict[str, float]] | None = None,
) -> BarTriggerEngine:
    ref = reference if reference is not None else load_bar_reference(settings)
    engine = BarTriggerEngine(reference=ref, held=held if held is not None else set())
    log.info("bar_engine_ready", reference_symbols=len(ref), held=len(engine.held))
    return engine


def build_feeds(
    settings: Settings,
    secrets: Secrets,
    dry_run: bool,
    names: Sequence[str] | None = None,
    *,
    held: set[str] | None = None,
    reference: dict[str, dict[str, float]] | None = None,
) -> list[Feed]:
    """Feed objects for `names` (default settings.monitor.feeds). `held` should be the pipeline's live set so
    the bar-trigger engine's adverse-move rule follows fills; `reference` overrides the store lookup (tests)."""
    if dry_run:
        path = os.environ.get(REPLAY_ENV, REPLAY_FILE_DEFAULT)
        return [FileFeed(resolve_path(path), rebase_received=True)]
    feeds: list[Feed] = []
    key, secret = secrets.alpaca_api_key or "", secrets.alpaca_secret_key or ""
    for name in names or settings.monitor.feeds:
        cls = registry.get("feed", name)
        if name == "alpaca_news":
            feeds.append(cls(key, secret))
        elif name == STOCKS_FEED:
            engine = build_bar_engine(settings, held=held, reference=reference)
            feeds.append(cls(key, secret, symbols=settings.monitor.watchlist or ["*"], engine=engine))
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
        workers: int = PIPELINE_WORKERS,
        windows: dict[str, tuple[time, time]] | None = None,
    ):
        self.feeds = list(feeds)
        self.pipeline = pipeline
        self.clock = clock or (lambda: datetime.now(UTC))
        self.watchdog_interval_s = watchdog_interval_s
        self.staleness = {**STALENESS_THRESHOLD_S, **(staleness or {})}
        self.windows = {**STALENESS_WINDOW_ET, **(windows or {})}
        self.stop_when_feeds_end = stop_when_feeds_end
        self._queue: asyncio.Queue[Event | None] = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task[Any]] = []
        self._inflight: set[asyncio.Task[Any]] = set()
        self._slots = asyncio.Semaphore(max(1, workers))
        self.last_seen: dict[str, datetime] = {}
        self.stale_alerted: set[str] = set()
        self.cursors: dict[str, str] = {}
        self._persisted_cursors: dict[str, str] = {}
        self.processed = 0
        self.inflight_cancelled = 0
        self._t0 = self.clock()
        self._session_date: date = to_et(self._t0).date()

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
        """Two-phase drain: feeds stop and the consumer empties the queue (rules only), then in-flight
        classification / deliveries get `SHUTDOWN_DRAIN_S` to finish before anything is cancelled."""
        log.info("monitor.shutdown_begin", processed=self.processed, queued=self._queue.qsize())
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
        self.pipeline.draining = True  # whatever is still queued for finish() skips the Haiku round trip
        self.inflight_cancelled = await self._drain_inflight()
        for t in self._tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t
        with contextlib.suppress(Exception):
            await self.pipeline.flush_digest_if_due(force=True)
        self._persist_cursors()
        log.info(
            "monitor.shutdown",
            processed=self.processed,
            stats=self.pipeline.stats,
            inflight_cancelled=self.inflight_cancelled,
        )
        await self._close_deliverers()
        if self.pipeline.eventlog is not None:
            self.pipeline.eventlog.close()

    async def _drain_inflight(self) -> int:
        pending = set(self._inflight)
        if not pending:
            return 0
        _done, pending = await asyncio.wait(pending, timeout=SHUTDOWN_DRAIN_S)
        for t in pending:
            t.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
            log.warning("monitor.inflight_cancelled", count=len(pending))
        return len(pending)

    async def _close_deliverers(self) -> None:
        for d in self.pipeline.deliverers.values():
            aclose = getattr(d, "aclose", None)
            if callable(aclose):
                with contextlib.suppress(Exception):
                    await aclose()

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
                cursor = _utc_iso(ev.ts_source)
                if cursor > self.cursors.get(feed.name, ""):
                    self.cursors[feed.name] = cursor
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
                res = self.pipeline.prepare(item)
            except Exception:  # noqa: BLE001 - never let one event stop the consumer
                log.exception("pipeline.failed", event_id=item.event_id)
                continue
            self.processed += 1
            if not res.dropped:
                self._spawn_finish(res)

    def _spawn_finish(self, res: PipelineResult) -> None:
        """P3 finishes in its own task right away; everything else waits for one of the worker slots."""
        if str(res.event.priority) == Priority.P3:
            coro = self.pipeline.finish(res)
        else:
            coro = self._finish_gated(res)
        task = asyncio.create_task(self._finish_guarded(coro, res.event.event_id), name=f"finish:{res.event.event_id[:16]}")
        self._inflight.add(task)
        task.add_done_callback(self._inflight.discard)

    async def _finish_gated(self, res: PipelineResult) -> PipelineResult:
        async with self._slots:
            return await self.pipeline.finish(res)

    async def _finish_guarded(self, coro: Any, event_id: str) -> None:
        try:
            await coro
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - one failed delivery must not take the service down
            log.exception("pipeline.finish_failed", event_id=event_id)

    @property
    def inflight(self) -> int:
        return len(self._inflight)

    async def _watchdog(self) -> None:
        while not self._stop.is_set():
            await asyncio.sleep(self.watchdog_interval_s)
            now = self.clock()
            self.roll_session(now)
            self._persist_cursors()
            await self.check_staleness(now)

    def roll_session(self, now: datetime | None = None) -> bool:
        """At the first tick of a new ET date: reset per-session small-cap memory and stale-alert latches."""
        today = to_et(now or self.clock()).date()
        if today == self._session_date:
            return False
        self._session_date = today
        self.stale_alerted.clear()
        track = self.pipeline.smallcap
        reset = getattr(track, "reset_session", None)
        if callable(reset):
            reset()
        log.info("monitor.session_rollover", session=today.isoformat())
        return True

    def _persist_cursors(self) -> None:
        eventlog = self.pipeline.eventlog
        if eventlog is None:
            return
        for name, cursor in self.cursors.items():
            if self._persisted_cursors.get(name) == cursor:
                continue
            with contextlib.suppress(Exception):
                eventlog.set_cursor(name, cursor)
                self._persisted_cursors[name] = cursor

    def _window_open(self, name: str, now: datetime) -> bool:
        """Is silence from `name` suspicious at `now`? Regular-hours feeds only during `regular` (early closes
        included); the rest inside their ET window and never when the session is closed."""
        phase = session_phase(now)
        if phase == "closed":
            return False
        lo, hi = self.windows.get(name, STALENESS_WINDOW_DEFAULT_ET)
        if hi <= REGULAR_CLOSE and phase != "regular":
            return False
        return lo <= to_et(now).time() < hi

    def _last_alive(self, feed: Feed) -> datetime | None:
        last = self.last_seen.get(feed.name)
        activity = getattr(feed, "last_activity_at", None)
        if isinstance(activity, datetime) and (last is None or activity > last):
            return activity
        return last

    async def check_staleness(self, now: datetime | None = None) -> list[str]:
        now = now or self.clock()
        if not is_market_hours(now):
            return []
        stale: list[str] = []
        for f in self.feeds:
            if f.name == "file" or not self._window_open(f.name, now):
                continue
            last = self._last_alive(f)
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


def build_pipeline(
    settings: Settings,
    secrets: Secrets,
    dry_run: bool,
    deliverers: Sequence[Deliverer] | None = None,
    held: Iterable[str] | None = None,
) -> Pipeline:
    """`held` seeds ctx["held"]; when omitted it is read from the broker (live runs) or left empty (dry runs).
    The pipeline keeps it current from `alpaca_account` trade updates afterwards."""
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
    if held is not None:
        held_set = {s.upper() for s in held}
    else:
        held_set = set() if dry_run else load_held_symbols(secrets)
    return Pipeline(
        rules=rules,
        classifier=classifier,
        policy=policy,
        deliverers=deliverers if deliverers is not None else build_deliverers(secrets, dry_run),
        eventlog=eventlog,
        deduper=Deduper(),
        matcher=matcher,
        ctx={"held": held_set, "watchlist": watch, "settings": mon},
        audit_path=None if dry_run else resolve_path(AUDIT_PATH_DEFAULT),
        smallcap=smallcap,
    )


async def run_monitor_async(settings: Settings, secrets: Secrets, dry_run: bool = False, feeds: Sequence[str] | None = None) -> MonitorService:
    pipeline = build_pipeline(settings, secrets, dry_run)
    # the same set object: fills reported on alpaca_account update both the rules and the bar-trigger engine
    feed_objs = build_feeds(settings, secrets, dry_run, feeds, held=pipeline.ctx["held"])
    service = MonitorService(feed_objs, pipeline, stop_when_feeds_end=dry_run)
    await service.run()
    return service


def run_monitor(settings: Settings, secrets: Secrets, dry_run: bool = False, feeds: Sequence[str] | None = None) -> None:
    """Entry point for `swing monitor run`. Blocks until SIGINT/SIGTERM (or until the file feed ends in dry_run)."""
    asyncio.run(run_monitor_async(settings, secrets, dry_run=dry_run, feeds=feeds))
