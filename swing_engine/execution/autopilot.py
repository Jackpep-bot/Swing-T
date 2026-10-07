"""Autopilot: executes the day's exits and entries on the paper account without a human in the loop.

``run_autopilot(settings, secrets, as_of, broker, intents, reviews=None, exit_actions=None, dry_run=False)``:

0. One run at a time: an exclusive lock on ``<ledger dir>/autopilot.lock`` is held for the whole run (a second,
   overlapping run aborts instead of reading the same cap and overwriting the audit).
1. ``OrderManager.reconcile()`` first; if the broker cannot be read nothing else happens.
2. Kill switch (``risk.kill_switch_file``) tripped -> every entry, close and stop change is refused. The only
   broker calls allowed are cancels of unfilled ``swing-*`` entries (the stale ones from the position manager
   plus every other resting unfilled entry, whatever its age): a resting GTC entry would otherwise keep working
   for up to 90 days and open new positions while the switch is set. Filled positions keep their bracket legs.
3. Approval mode. Orders are approved automatically ONLY on a paper broker (``AlpacaBroker`` with ``paper=True``
   or ``PaperSimBroker``) when ``execution.auto_submit_paper``; ``approved_by="autopilot:paper"``. A live broker
   additionally needs ``execution.auto_submit_live`` AND env ``SWING_ALLOW_LIVE=yes`` (``autopilot:live``).
   Anything else stages the plan to ``<store dir>/runs/pending/<date>.json`` for a human and touches nothing;
   ``swing paper --approve NAME`` then executes exactly that plan through :func:`run_pending` (mode
   ``approved``, ``approved_by=NAME``).
4. Review vetoes. With ``execution.require_review_approval`` and reviews present, an intent whose review says
   ``reject`` or ``needs_more_info`` is dropped. Reviews are enums; they can only remove an intent, never change
   a number on it (prices, stops and share counts come from ``strategies/`` and ``risk/``).
5. Exits before entries (``execution.position_manager.ExitAction``: cancel stale entries, close, tighten stops;
   ``flag`` items are only reported).
6. Entries through ``OrderManager.submit`` (persisted ``LimitState`` from ``risk.limits_state_file``; idempotent
   on ``client_order_id`` via the order ledger), at most ``execution.max_new_orders_per_day`` new orders per
   ``as_of`` across runs. Submitted AND errored entries count (a broker call that raised may still have been
   accepted), counted from the audit file plus any intent of this run that the ledger shows an autopilot
   already sent (a run killed before its audit write).
7. Full audit appended to ``<store dir>/runs/autopilot/<date>.json``.

``dry_run`` reconciles and plans (statuses ``planned``) but never mutates the broker or the limits state.
Entry orders are GTC brackets; see ``execution.alpaca_broker`` for the time-in-force reasoning and doc links.
"""
from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel, Field

from swing_engine.core.config import Secrets, Settings
from swing_engine.core.models import OrderIntent, Review, ReviewDecision
from swing_engine.execution.alpaca_broker import LIVE_OVERRIDE_ENV, LIVE_OVERRIDE_VALUE, AlpacaBroker
from swing_engine.execution.ledger import OrderLedger
from swing_engine.execution.order_manager import DUPLICATE, OrderManager, OrderRefused
from swing_engine.execution.paper_sim import PaperSimBroker
from swing_engine.execution.position_manager import ExitAction, ExitKind, entry_cancels_on_kill
from swing_engine.risk import killswitch
from swing_engine.risk.killswitch import resolve_state_path
from swing_engine.risk.limits import LimitState

log = structlog.get_logger(__name__)

RUNS_DIRNAME = "runs"
AUTOPILOT_KIND = "autopilot"
PENDING_KIND = "pending"
APPROVER_PREFIX = "autopilot:"
APPROVER_PAPER = f"{APPROVER_PREFIX}paper"
APPROVER_LIVE = f"{APPROVER_PREFIX}live"
MIN_HUMAN_APPROVER_LEN = 2  # same rule as `swing paper --approve`
VETO_DECISIONS = frozenset({ReviewDecision.REJECT, ReviewDecision.NEEDS_MORE_INFO})
ENTRY = "entry"
LOCK_FILENAME = "autopilot.lock"
KILL_ALLOWED_EXITS = frozenset({ExitKind.CANCEL_ORDER})  # cancelling an unfilled entry only removes exposure


class AutopilotMode(StrEnum):
    PAPER = "paper"  # auto-approved on a paper broker
    LIVE = "live"  # auto-approved live (auto_submit_live + SWING_ALLOW_LIVE=yes)
    APPROVED = "approved"  # a staged plan executed with a named human approver (run_pending)
    STAGED = "staged"  # written to runs/pending for a human
    DRY_RUN = "dry_run"
    KILLED = "killed"  # kill switch tripped
    ABORTED = "aborted"  # reconcile failed or another run holds the lock


class Outcome(StrEnum):
    SUBMITTED = "submitted"
    DONE = "done"  # exit executed
    DUPLICATE = "duplicate"
    VETOED = "vetoed"
    CAPPED = "capped"
    REFUSED = "refused"
    ERROR = "error"
    STAGED = "staged"
    PLANNED = "planned"
    FLAGGED = "flagged"


class ActionResult(BaseModel):
    kind: str  # "entry" or an ExitKind value
    symbol: str
    status: Outcome
    client_order_id: str | None = None
    strategy: str | None = None
    reason: str = ""
    response: dict[str, Any] = Field(default_factory=dict)


class AutopilotReport(BaseModel):
    as_of: date
    broker: str
    paper: bool
    mode: AutopilotMode
    approved_by: str | None = None
    dry_run: bool = False
    kill_switch: bool = False
    started_at: datetime
    finished_at: datetime | None = None
    account: dict[str, Any] = Field(default_factory=dict)
    reconcile: dict[str, Any] = Field(default_factory=dict)
    exits: list[ActionResult] = Field(default_factory=list)
    entries: list[ActionResult] = Field(default_factory=list)
    new_orders_before: int = 0
    max_new_orders_per_day: int = 0
    limits: dict[str, Any] = Field(default_factory=dict)
    staged_path: str | None = None
    audit_path: str | None = None
    errors: list[str] = Field(default_factory=list)

    def count(self, status: Outcome, entries: bool = True) -> int:
        return sum(r.status is status for r in (self.entries if entries else self.exits))

    @property
    def submitted(self) -> int:
        return self.count(Outcome.SUBMITTED)

    def summary(self) -> dict[str, Any]:
        def tally(items: list[ActionResult]) -> dict[str, int]:
            out: dict[str, int] = {}
            for r in items:
                out[r.status.value] = out.get(r.status.value, 0) + 1
            return out

        return {"mode": self.mode.value, "entries": tally(self.entries), "exits": tally(self.exits)}


# ----------------------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------------------
def is_paper_broker(broker: Any) -> bool:
    """Fail closed: only the in-memory simulator and an Alpaca session constructed with paper=True count."""
    if isinstance(broker, PaperSimBroker):
        return True
    return isinstance(broker, AlpacaBroker) and broker.paper is True


def runs_dir(settings: Settings) -> Path:
    return resolve_state_path(settings.data.store_path).parent / RUNS_DIRNAME


def run_path(settings: Settings, kind: str, as_of: date) -> Path:
    return runs_dir(settings) / kind / f"{as_of.isoformat()}.json"


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)
    return path


def _prior_runs(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except ValueError:
        log.error("autopilot_audit_unreadable", path=str(path))
        return []
    runs = data.get("runs") if isinstance(data, dict) else None
    return list(runs) if isinstance(runs, list) else []


CAP_COUNTED = frozenset({Outcome.SUBMITTED.value, Outcome.ERROR.value})  # an errored submit may be live


def counted_order_ids(prior_runs: Iterable[Mapping[str, Any]]) -> set[str]:
    """client_order_ids that earlier (non dry-run) runs on this as_of submitted or errored on."""
    return {
        str(entry.get("client_order_id"))
        for run in prior_runs
        if not run.get("dry_run")
        for entry in run.get("entries") or []
        if entry.get("status") in CAP_COUNTED
    }


def new_orders_submitted(prior_runs: Iterable[Mapping[str, Any]]) -> int:
    """New entry orders already sent (or possibly sent) on this as_of by earlier non dry-run autopilot runs."""
    return len(counted_order_ids(prior_runs))


def _ledger_sent(ledger: OrderLedger, intents: Iterable[OrderIntent], counted: set[str]) -> set[str]:
    """Intents of this run the ledger shows an autopilot already sent, missing from the audit (a run that died
    before its audit write, or a submit whose outcome never got recorded)."""
    out: set[str] = set()
    for intent in intents:
        cid = intent.client_order_id
        if cid in counted:
            continue
        row = ledger.get(cid)
        if row is not None and str(row.get("approved_by") or "").startswith(APPROVER_PREFIX):
            out.add(cid)
    return out


def lock_path(settings: Settings) -> Path:
    return resolve_state_path(settings.execution.ledger_file).parent / LOCK_FILENAME


@contextmanager
def _exclusive(path: Path) -> Iterator[bool]:
    """Non-blocking exclusive flock; yields False when another process holds it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as fh:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _vetoes(settings: Settings, reviews: Iterable[Review] | None) -> dict[tuple[str, str], ReviewDecision]:
    if not settings.execution.require_review_approval or not reviews:
        return {}
    return {(r.symbol, r.strategy): r.decision for r in reviews if r.decision in VETO_DECISIONS}


def _mode(settings: Settings, paper: bool, dry_run: bool, env: Mapping[str, str]) -> tuple[AutopilotMode, str | None]:
    cfg = settings.execution
    if dry_run:
        return AutopilotMode.DRY_RUN, None
    if paper:
        return (AutopilotMode.PAPER, APPROVER_PAPER) if cfg.auto_submit_paper else (AutopilotMode.STAGED, None)
    if cfg.auto_submit_live and env.get(LIVE_OVERRIDE_ENV) == LIVE_OVERRIDE_VALUE:
        return AutopilotMode.LIVE, APPROVER_LIVE
    return AutopilotMode.STAGED, None


def _account(broker: Any) -> dict[str, Any]:
    try:
        raw = dict(broker.account())
    except Exception as exc:  # noqa: BLE001 - informational only; LimitState re-reads it per order
        return {"error": str(exc)}
    return {k: raw.get(k) for k in ("equity", "last_equity", "cash", "buying_power", "paper") if k in raw}


# ----------------------------------------------------------------------------------------------------------
# exits and entries
# ----------------------------------------------------------------------------------------------------------
def _exit_result(action: ExitAction, status: Outcome, reason: str = "", response: Any = None) -> ActionResult:
    return ActionResult(
        kind=action.kind.value, symbol=action.symbol, status=status, client_order_id=action.client_order_id,
        strategy=action.strategy, reason=reason or f"{action.reason.value}: {action.detail}".rstrip(": "),
        response=dict(response) if isinstance(response, Mapping) else ({"value": response} if response else {}),
    )


def _execute_exit(manager: OrderManager, action: ExitAction, approver: str) -> ActionResult:
    try:
        if action.kind is ExitKind.CANCEL_ORDER:
            response = manager.cancel_order(action.order_id, action.client_order_id)
        elif action.kind is ExitKind.CLOSE:
            # no qty: flatten the whole live position (the planned qty is a snapshot that a partial fill can outdate)
            response = manager.close_position(
                action.symbol, approver, qty=None, price=action.ref_price, reason=action.reason.value
            )
        elif action.kind is ExitKind.REPLACE_STOP:
            if action.new_stop is None:
                raise OrderRefused("replace_stop without new_stop", action.symbol)
            response = manager.replace_stop(action.symbol, action.new_stop, approver, order_id=action.order_id)
        elif action.kind is ExitKind.PLACE_STOP:
            if action.new_stop is None:
                raise OrderRefused("place_stop without new_stop", action.symbol)
            response = manager.place_stop(action.symbol, action.new_stop, approver)
        else:
            return _exit_result(action, Outcome.FLAGGED)
    except OrderRefused as exc:
        return _exit_result(action, Outcome.REFUSED, exc.reason)
    except Exception as exc:  # noqa: BLE001 - one failed exit must not stop the others
        log.error("autopilot_exit_failed", symbol=action.symbol, kind=action.kind.value, error=str(exc))
        return _exit_result(action, Outcome.ERROR, f"{type(exc).__name__}: {exc}")
    return _exit_result(action, Outcome.DONE, response=response)


def _entry_result(intent: OrderIntent, status: Outcome, reason: str = "", response: Any = None) -> ActionResult:
    return ActionResult(
        kind=ENTRY, symbol=intent.symbol, status=status, client_order_id=intent.client_order_id,
        strategy=intent.strategy, reason=reason, response=dict(response) if isinstance(response, Mapping) else {},
    )


def _submit_entry(manager: OrderManager, intent: OrderIntent, approver: str) -> ActionResult:
    try:
        response = manager.submit(intent, approved_by=approver)
    except OrderRefused as exc:
        return _entry_result(intent, Outcome.REFUSED, exc.reason)
    except Exception as exc:  # noqa: BLE001
        log.error("autopilot_submit_failed", symbol=intent.symbol, error=str(exc))
        return _entry_result(intent, Outcome.ERROR, f"{type(exc).__name__}: {exc}")
    if response.get("status") == DUPLICATE:
        return _entry_result(intent, Outcome.DUPLICATE, "client_order_id already in the ledger", response)
    return _entry_result(intent, Outcome.SUBMITTED, response=response)


def _plan_entries(
    report: AutopilotReport,
    manager: OrderManager,
    intents: list[OrderIntent],
    vetoes: Mapping[tuple[str, str], ReviewDecision],
    closing: set[str],
    approver: str | None,
) -> None:
    cap = report.max_new_orders_per_day
    used = report.new_orders_before
    for intent in intents:
        decision = vetoes.get((intent.symbol, intent.strategy))
        if decision is not None:
            report.entries.append(_entry_result(intent, Outcome.VETOED, f"review decision {decision.value}"))
            continue
        if manager.ledger.get(intent.client_order_id) is not None:
            report.entries.append(_entry_result(intent, Outcome.DUPLICATE, "client_order_id already in the ledger"))
            continue
        if intent.symbol in closing:
            report.entries.append(_entry_result(intent, Outcome.REFUSED, "an exit for this symbol runs today"))
            continue
        if used >= cap:
            report.entries.append(_entry_result(intent, Outcome.CAPPED, f"max_new_orders_per_day={cap} reached"))
            continue
        if approver is None:
            status = Outcome.PLANNED if report.mode is AutopilotMode.DRY_RUN else Outcome.STAGED
            report.entries.append(_entry_result(intent, status))
            used += 1
            continue
        result = _submit_entry(manager, intent, approver)
        report.entries.append(result)
        if result.status.value in CAP_COUNTED:
            used += 1


def _killed(
    report: AutopilotReport, manager: OrderManager, exits: list[ExitAction], approver: str | None, why: str
) -> list[ExitAction]:
    """Kill-switch path: only unfilled-entry cancels run (planned stale cancels plus a sweep of every resting
    unfilled ``swing-*`` entry). Returns the cancels that were staged for a human."""
    try:
        sweep = entry_cancels_on_kill(manager.broker.open_orders())
    except Exception as exc:  # noqa: BLE001 - reconcile just read the broker; report and keep the planned cancels
        report.errors.append(f"kill-switch sweep could not list open orders: {type(exc).__name__}: {exc}")
        sweep = []
    planned = {a.order_id or a.client_order_id for a in exits if a.kind is ExitKind.CANCEL_ORDER}
    actions = [*exits, *(a for a in sweep if (a.order_id or a.client_order_id) not in planned)]
    staged: list[ExitAction] = []
    for action in actions:
        if action.kind is ExitKind.FLAG:
            report.exits.append(_exit_result(action, Outcome.FLAGGED))
        elif action.kind not in KILL_ALLOWED_EXITS:
            report.exits.append(_exit_result(action, Outcome.REFUSED, why))
        elif approver is None:
            report.exits.append(_exit_result(action, Outcome.PLANNED if report.dry_run else Outcome.STAGED))
            if not report.dry_run:
                staged.append(action)
        else:
            report.exits.append(_execute_exit(manager, action, approver))
    return staged


def _stage(settings: Settings, report: AutopilotReport, intents: list[OrderIntent], exits: list[ExitAction]) -> Path:
    staged_ids = {r.client_order_id for r in report.entries if r.status is Outcome.STAGED}
    payload = {
        "as_of": report.as_of.isoformat(),
        "broker": report.broker,
        "paper": report.paper,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "why": "automatic approval is only allowed on a paper broker (or live with auto_submit_live and "
        f"{LIVE_OVERRIDE_ENV}={LIVE_OVERRIDE_VALUE}); execute exactly this plan with "
        f"`swing paper --approve NAME --as-of {report.as_of.isoformat()}`",
        "intents": [i.model_dump(mode="json") for i in intents if i.client_order_id in staged_ids],
        "exit_actions": [a.model_dump(mode="json") for a in exits if a.kind is not ExitKind.FLAG],
    }
    return _write_json(run_path(settings, PENDING_KIND, report.as_of), payload)


def load_pending(settings: Settings, as_of: date) -> tuple[list[OrderIntent], list[ExitAction]] | None:
    """The staged plan for ``as_of`` (``runs/pending/<date>.json``), or None when nothing was staged."""
    path = run_path(settings, PENDING_KIND, as_of)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8") or "{}")
    intents = [OrderIntent.model_validate(i) for i in data.get("intents") or []]
    exits = [ExitAction.model_validate(a) for a in data.get("exit_actions") or []]
    return intents, exits


def run_pending(
    settings: Settings, secrets: Secrets, as_of: date, broker: Any, approved_by: str, *,
    ledger: OrderLedger | None = None,
) -> AutopilotReport:
    """Execute exactly the staged plan for ``as_of`` with a named human approver: the staged exits, then the
    staged intents (already filtered by review vetoes and the daily cap when they were staged). Every other gate
    (kill switch, limits, ledger idempotency, the cap) applies again. Raises FileNotFoundError when nothing was
    staged for ``as_of``."""
    plan = load_pending(settings, as_of)
    if plan is None:
        raise FileNotFoundError(f"no staged plan at {run_path(settings, PENDING_KIND, as_of)}")
    intents, exits = plan
    return run_autopilot(settings, secrets, as_of, broker, intents, None, exits, ledger=ledger, approved_by=approved_by)


def _audit(settings: Settings, report: AutopilotReport, prior: list[dict[str, Any]]) -> Path:
    path = run_path(settings, AUTOPILOT_KIND, report.as_of)
    report.audit_path = str(path)
    runs = [*prior, report.model_dump(mode="json")]
    return _write_json(path, {"as_of": report.as_of.isoformat(), "runs": runs})


# ----------------------------------------------------------------------------------------------------------
# entry point
# ----------------------------------------------------------------------------------------------------------
def run_autopilot(
    settings: Settings,
    secrets: Secrets,
    as_of: date | None,
    broker: Any,
    intents: Iterable[OrderIntent],
    reviews: Iterable[Review] | None = None,
    exit_actions: Iterable[ExitAction] | None = None,
    dry_run: bool = False,
    *,
    ledger: OrderLedger | None = None,
    env: Mapping[str, str] | None = None,
    approved_by: str | None = None,
) -> AutopilotReport:
    """Reconcile, then exits, then entries; see the module docstring for every gate. Never raises for a
    single order: refusals and broker errors are recorded on the report. ``secrets`` is accepted for the
    contract (brokers are built by the caller) and is not read here. ``approved_by`` (a human name, used by
    :func:`run_pending`) replaces the automatic paper/live approval rules; it cannot be combined with
    ``dry_run``."""
    del secrets  # brokers arrive constructed; nothing here needs a key
    as_of_d = as_of or date.today()
    intents_l = list(intents)
    exits_l = list(exit_actions or [])
    environ: Mapping[str, str] = os.environ if env is None else env
    paper = is_paper_broker(broker)
    cfg = settings.execution
    if approved_by is not None:
        human = approved_by.strip()
        if len(human) < MIN_HUMAN_APPROVER_LEN or human.startswith(APPROVER_PREFIX) or dry_run:
            raise ValueError(f"a staged plan needs a human approver name, got {approved_by!r} (dry_run={dry_run})")
        mode, approver = AutopilotMode.APPROVED, human
    else:
        mode, approver = _mode(settings, paper, dry_run, environ)
    report = AutopilotReport(
        as_of=as_of_d, broker=str(getattr(broker, "name", type(broker).__name__)), paper=paper, mode=mode,
        approved_by=approver, dry_run=dry_run, started_at=datetime.now(UTC),
        max_new_orders_per_day=cfg.max_new_orders_per_day,
    )
    with _exclusive(lock_path(settings)) as locked:
        if not locked:
            report.mode, report.approved_by = AutopilotMode.ABORTED, None
            report.errors.append(f"another autopilot run holds {lock_path(settings)}; nothing was sent")
            report.finished_at = datetime.now(UTC)
            log.error("autopilot_locked", lock=str(lock_path(settings)))
            return report
        return _run_locked(settings, report, broker, intents_l, reviews, exits_l, approver, ledger)


def _run_locked(
    settings: Settings,
    report: AutopilotReport,
    broker: Any,
    intents_l: list[OrderIntent],
    reviews: Iterable[Review] | None,
    exits_l: list[ExitAction],
    approver: str | None,
    ledger: OrderLedger | None,
) -> AutopilotReport:
    cfg = settings.execution
    dry_run = report.dry_run
    prior = _prior_runs(run_path(settings, AUTOPILOT_KIND, report.as_of))
    kill_path = settings.risk.kill_switch_file
    limits = LimitState(settings.risk, as_of=None, state_path=None if dry_run else settings.risk.limits_state_file)
    own_ledger = ledger is None
    order_ledger = ledger if ledger is not None else OrderLedger(cfg.ledger_file)
    counted = counted_order_ids(prior)
    report.new_orders_before = len(counted | _ledger_sent(order_ledger, intents_l, counted))
    manager = OrderManager(broker, limits, kill_path, ledger=order_ledger)
    try:
        try:
            report.reconcile = manager.reconcile()
        except Exception as exc:  # noqa: BLE001 - an unreadable broker means no orders today
            report.mode, report.approved_by = AutopilotMode.ABORTED, None
            report.errors.append(f"reconcile failed: {type(exc).__name__}: {exc}")
            log.error("autopilot_reconcile_failed", error=str(exc))
            return report
        report.account = _account(broker)
        if killswitch.is_tripped(kill_path):
            report.mode, report.approved_by, report.kill_switch = AutopilotMode.KILLED, None, True
            why = f"kill switch tripped at {resolve_state_path(kill_path)}"
            staged = _killed(report, manager, exits_l, approver, why)
            report.entries = [_entry_result(i, Outcome.REFUSED, why) for i in intents_l]
            if staged:
                report.staged_path = str(_stage(settings, report, [], staged))
            log.warning("autopilot_killed", path=str(resolve_state_path(kill_path)),
                        cancels=sum(r.status is Outcome.DONE for r in report.exits))
            return report

        for action in exits_l:  # exits before entries
            if action.kind is ExitKind.FLAG:
                report.exits.append(_exit_result(action, Outcome.FLAGGED))
            elif approver is None:
                status = Outcome.PLANNED if dry_run else Outcome.STAGED
                report.exits.append(_exit_result(action, status))
            else:
                report.exits.append(_execute_exit(manager, action, approver))
        closing = {a.symbol for a in exits_l if a.kind is ExitKind.CLOSE}
        _plan_entries(report, manager, intents_l, _vetoes(settings, reviews), closing, approver)
        if report.mode is AutopilotMode.STAGED:
            report.staged_path = str(_stage(settings, report, intents_l, exits_l))
        report.limits = limits.snapshot()
        return report
    finally:
        report.finished_at = datetime.now(UTC)
        _audit(settings, report, prior)
        if own_ledger:
            order_ledger.close()
        log.info(
            "autopilot_done", as_of=str(report.as_of), mode=report.mode.value, broker=report.broker,
            submitted=report.submitted, summary=report.summary(), audit=report.audit_path,
        )
