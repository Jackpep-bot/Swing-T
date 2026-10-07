"""execution.autopilot on paper_sim (and a fail-closed unknown broker): approval mode, kill switch, limits,
review vetoes, daily cap, idempotency, exits before entries, dry run and the audit trail. No network."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from swing_engine.core.config import Secrets, Settings
from swing_engine.core.interfaces import Broker
from swing_engine.core.models import OrderIntent, Position, Review, ReviewDecision, Side
from swing_engine.execution.autopilot import (
    APPROVER_PAPER,
    AutopilotMode,
    _exclusive,
    is_paper_broker,
    lock_path,
    new_orders_submitted,
    run_autopilot,
    run_path,
    run_pending,
)
from swing_engine.execution.ledger import OrderLedger
from swing_engine.execution.paper_sim import PaperSimBroker
from swing_engine.execution.position_manager import ExitAction, ExitKind, ExitReason

AS_OF = date(2026, 9, 30)
SECRETS = Secrets(_env_file=None)


def make_settings(tmp_path: Path, risk: dict[str, Any] | None = None, **execution: Any) -> Settings:
    return Settings.model_validate(
        {
            "data": {"store_path": str(tmp_path / "data" / "swing.duckdb")},
            "risk": {
                "kill_switch_file": str(tmp_path / "state" / "KILL"),
                "limits_state_file": str(tmp_path / "state" / "limits.json"),
                **(risk or {}),
            },
            "execution": {"ledger_file": str(tmp_path / "state" / "orders.sqlite"), **execution},
        }
    )


def intent(symbol: str, strategy: str = "sr_bounce", qty: int = 50) -> OrderIntent:
    return OrderIntent(
        symbol=symbol, side=Side.LONG, qty=qty, entry_limit=101.0, stop=95.0, target=120.0, strategy=strategy,
        client_order_id=f"swing-{strategy}-{symbol}-{AS_OF:%Y%m%d}-long", risk_dollars=qty * 6.0,
    )


def review(symbol: str, decision: ReviewDecision, strategy: str = "sr_bounce") -> Review:
    return Review(
        symbol=symbol, strategy=strategy, thesis="t", catalyst_within_hold_window=False,
        news_contradicts_setup=False, liquidity_concern=False, decision=decision,
    )


def statuses(results: list[Any]) -> dict[str, str]:
    return {r.symbol: r.status.value for r in results}


def audit(tmp_path: Path) -> dict[str, Any]:
    return json.loads((tmp_path / "data" / "runs" / "autopilot" / f"{AS_OF}.json").read_text())


# ----------------------------------------------------------------------------------------------------------
# paper auto-approval, idempotency, cap
# ----------------------------------------------------------------------------------------------------------
def test_paper_sim_auto_submits_with_autopilot_approver_and_audits(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    broker = PaperSimBroker()
    report = run_autopilot(settings, SECRETS, AS_OF, broker, [intent("AAA"), intent("BBB")])
    assert report.mode is AutopilotMode.PAPER and report.paper and report.approved_by == APPROVER_PAPER
    assert statuses(report.entries) == {"AAA": "submitted", "BBB": "submitted"} and report.submitted == 2
    assert {o["symbol"] for o in broker.open_orders()} == {"AAA", "BBB"}
    ledger = OrderLedger(settings.execution.ledger_file)
    assert {r["approved_by"] for r in ledger.all()} == {APPROVER_PAPER}
    ledger.close()
    saved = audit(tmp_path)
    assert saved["as_of"] == AS_OF.isoformat() and len(saved["runs"]) == 1
    assert saved["runs"][0]["mode"] == "paper" and report.audit_path == str(run_path(settings, "autopilot", AS_OF))
    assert "checked" in report.reconcile and report.account["equity"] == broker.equity()
    assert (tmp_path / "state" / "limits.json").exists()  # LimitState is persisted


def test_rerun_is_idempotent_and_does_not_consume_the_cap(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    broker = PaperSimBroker()
    run_autopilot(settings, SECRETS, AS_OF, broker, [intent("AAA")])
    again = run_autopilot(settings, SECRETS, AS_OF, broker, [intent("AAA"), intent("BBB")])
    assert statuses(again.entries) == {"AAA": "duplicate", "BBB": "submitted"}
    assert again.new_orders_before == 1 and len(broker.open_orders()) == 2
    assert len(audit(tmp_path)["runs"]) == 2 and new_orders_submitted(audit(tmp_path)["runs"]) == 2


def test_max_new_orders_per_day_across_runs(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, max_new_orders_per_day=2)
    broker = PaperSimBroker()
    first = run_autopilot(settings, SECRETS, AS_OF, broker, [intent("AAA"), intent("BBB"), intent("CCC")])
    assert statuses(first.entries) == {"AAA": "submitted", "BBB": "submitted", "CCC": "capped"}
    second = run_autopilot(settings, SECRETS, AS_OF, broker, [intent("DDD")])
    assert second.new_orders_before == 2 and statuses(second.entries) == {"DDD": "capped"}
    assert {o["symbol"] for o in broker.open_orders()} == {"AAA", "BBB"}


def test_limit_refusals_do_not_consume_the_cap(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, risk={"max_position_pct": 10.0}, max_new_orders_per_day=1)
    broker = PaperSimBroker()  # 100k equity: 200 sh x 101 = 20% of equity is refused by LimitState
    report = run_autopilot(settings, SECRETS, AS_OF, broker, [intent("BIG", qty=200), intent("OK")])
    assert statuses(report.entries) == {"BIG": "refused", "OK": "submitted"}
    assert "limit check failed" in report.entries[0].reason and "exceeds max" in report.entries[0].reason


# ----------------------------------------------------------------------------------------------------------
# vetoes, kill switch, dry run, mode selection
# ----------------------------------------------------------------------------------------------------------
def test_review_vetoes_drop_reject_and_needs_more_info_only(tmp_path: Path) -> None:
    intents = [intent("REJ"), intent("MORE"), intent("YES"), intent("NOREV")]
    reviews = [
        review("REJ", ReviewDecision.REJECT),
        review("MORE", ReviewDecision.NEEDS_MORE_INFO),
        review("YES", ReviewDecision.APPROVE_FOR_RISK_CHECK),
        review("NOREV", ReviewDecision.REJECT, strategy="other_strategy"),  # different (symbol, strategy)
    ]
    report = run_autopilot(make_settings(tmp_path), SECRETS, AS_OF, PaperSimBroker(), intents, reviews)
    assert statuses(report.entries) == {"REJ": "vetoed", "MORE": "vetoed", "YES": "submitted", "NOREV": "submitted"}
    assert "reject" in report.entries[0].reason
    off = make_settings(tmp_path / "off", require_review_approval=False)
    report = run_autopilot(off, SECRETS, AS_OF, PaperSimBroker(), intents, reviews)
    assert report.submitted == len(intents)


def test_kill_switch_refuses_everything(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    (tmp_path / "state").mkdir(parents=True)
    (tmp_path / "state" / "KILL").write_text("incident\n")
    broker = PaperSimBroker()
    broker._positions["OLD"] = Position(symbol="OLD", qty=10, avg_entry=10.0, side=Side.LONG, stop=9.0)
    close = ExitAction(kind=ExitKind.CLOSE, symbol="OLD", reason=ExitReason.TIME_STOP, qty=10, ref_price=10.0)
    report = run_autopilot(settings, SECRETS, AS_OF, broker, [intent("AAA")], exit_actions=[close])
    assert report.mode is AutopilotMode.KILLED and report.kill_switch and report.approved_by is None
    assert statuses(report.entries) == {"AAA": "refused"} and statuses(report.exits) == {"OLD": "refused"}
    assert "kill switch" in report.entries[0].reason
    assert broker.open_orders() == [] and [p.symbol for p in broker.positions()] == ["OLD"]
    assert audit(tmp_path)["runs"][0]["mode"] == "killed"


def test_dry_run_plans_without_touching_broker_or_limits(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, max_new_orders_per_day=1)
    broker = PaperSimBroker()
    broker._positions["OLD"] = Position(symbol="OLD", qty=10, avg_entry=10.0, side=Side.LONG, stop=9.0)
    stop = ExitAction(kind=ExitKind.REPLACE_STOP, symbol="OLD", reason=ExitReason.BREAKEVEN, new_stop=10.0)
    report = run_autopilot(settings, SECRETS, AS_OF, broker, [intent("AAA"), intent("BBB")], exit_actions=[stop],
                           dry_run=True)
    assert report.mode is AutopilotMode.DRY_RUN and report.dry_run and report.approved_by is None
    assert statuses(report.entries) == {"AAA": "planned", "BBB": "capped"} and statuses(report.exits) == {"OLD": "planned"}
    assert broker.open_orders() == [] and broker.positions()[0].stop == 9.0
    assert not (tmp_path / "state" / "limits.json").exists()
    assert new_orders_submitted(audit(tmp_path)["runs"]) == 0  # a dry run never counts against the cap


class UnknownBroker(Broker):
    name = "mystery"

    def __init__(self) -> None:
        self.submits = 0

    def account(self) -> dict[str, Any]:
        return {"equity": 100_000.0}

    def positions(self) -> list[Position]:
        return []

    def submit(self, intent: OrderIntent) -> dict[str, Any]:
        self.submits += 1
        raise AssertionError("an unknown broker must never be auto-approved")

    def open_orders(self) -> list[dict[str, Any]]:
        return []

    def cancel(self, order_id: str) -> None:
        raise AssertionError("never")


def test_unknown_broker_is_treated_as_live_and_staged(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    broker = UnknownBroker()
    assert not is_paper_broker(broker) and is_paper_broker(PaperSimBroker())
    close = ExitAction(kind=ExitKind.CLOSE, symbol="X", reason=ExitReason.EARNINGS, qty=1, ref_price=1.0)
    flag = ExitAction(kind=ExitKind.FLAG, symbol="Y", reason=ExitReason.ORPHAN)
    report = run_autopilot(settings, SECRETS, AS_OF, broker, [intent("AAA")], exit_actions=[close, flag],
                           env={"SWING_ALLOW_LIVE": "yes"})  # auto_submit_live is False
    assert report.mode is AutopilotMode.STAGED and broker.submits == 0
    assert statuses(report.entries) == {"AAA": "staged"} and statuses(report.exits) == {"X": "staged", "Y": "flagged"}
    pending = json.loads(Path(report.staged_path).read_text())
    assert report.staged_path == str(run_path(settings, "pending", AS_OF))
    assert [i["symbol"] for i in pending["intents"]] == ["AAA"] and [a["symbol"] for a in pending["exit_actions"]] == ["X"]


def test_paper_without_auto_submit_paper_is_staged(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, auto_submit_paper=False)
    broker = PaperSimBroker()
    report = run_autopilot(settings, SECRETS, AS_OF, broker, [intent("AAA")])
    assert report.mode is AutopilotMode.STAGED and broker.open_orders() == [] and report.staged_path


def test_reconcile_failure_aborts(tmp_path: Path) -> None:
    class Broken(PaperSimBroker):
        def open_orders(self) -> list[dict[str, Any]]:
            raise ConnectionError("broker down")

    broker = Broken()
    report = run_autopilot(make_settings(tmp_path), SECRETS, AS_OF, broker, [intent("AAA")])
    assert report.mode is AutopilotMode.ABORTED and report.entries == [] and "broker down" in report.errors[0]
    assert broker._orders == {} and audit(tmp_path)["runs"][0]["mode"] == "aborted"


# ----------------------------------------------------------------------------------------------------------
# exits before entries
# ----------------------------------------------------------------------------------------------------------
def test_exits_run_before_entries_on_paper_sim(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, risk={"max_open_positions": 2})
    broker = PaperSimBroker(slippage_bps=0.0)
    broker._positions["OUT"] = Position(symbol="OUT", qty=10, avg_entry=10.0, side=Side.LONG, stop=9.0)
    broker._positions["TRL"] = Position(symbol="TRL", qty=10, avg_entry=10.0, side=Side.LONG, stop=9.0)
    broker.submit(intent("STALE"))
    exits = [
        ExitAction(kind=ExitKind.CANCEL_ORDER, symbol="STALE", reason=ExitReason.STALE_ENTRY, order_id="sim-1",
                   client_order_id=intent("STALE").client_order_id),
        ExitAction(kind=ExitKind.CLOSE, symbol="OUT", reason=ExitReason.STRATEGY_EXIT, qty=10, ref_price=12.0),
        ExitAction(kind=ExitKind.REPLACE_STOP, symbol="TRL", reason=ExitReason.BREAKEVEN, new_stop=10.0),
        ExitAction(kind=ExitKind.REPLACE_STOP, symbol="TRL", reason=ExitReason.TRAIL, new_stop=8.0),  # looser
    ]
    report = run_autopilot(settings, SECRETS, AS_OF, broker, [intent("OUT"), intent("NEW")], exit_actions=exits)
    assert [(r.kind, r.status.value) for r in report.exits] == [
        ("cancel_order", "done"), ("close", "done"), ("replace_stop", "done"), ("replace_stop", "refused"),
    ]  # fmt: skip
    assert "loosen" in report.exits[3].reason
    assert broker.closed_trades[0]["symbol"] == "OUT" and broker.closed_trades[0]["exit"] == 12.0
    assert {p.symbol: p.stop for p in broker.positions()} == {"TRL": 10.0}
    # OUT is being exited today (no same-day re-entry); NEW fits only because OUT's slot was freed first
    assert statuses(report.entries) == {"OUT": "refused", "NEW": "submitted"}
    assert broker.get_order(intent("STALE").client_order_id)["status"] == "canceled"


def test_close_without_reference_price_is_refused_on_paper_sim(tmp_path: Path) -> None:
    broker = PaperSimBroker()
    broker._positions["OUT"] = Position(symbol="OUT", qty=10, avg_entry=10.0, side=Side.LONG)
    close = ExitAction(kind=ExitKind.CLOSE, symbol="OUT", reason=ExitReason.TIME_STOP, qty=10)
    report = run_autopilot(make_settings(tmp_path), SECRETS, AS_OF, broker, [], exit_actions=[close])
    assert statuses(report.exits) == {"OUT": "refused"} and "reference price" in report.exits[0].reason
    assert [p.symbol for p in broker.positions()] == ["OUT"]


@pytest.mark.parametrize("as_of", [None, AS_OF])
def test_as_of_defaults_to_today(tmp_path: Path, as_of: date | None) -> None:
    report = run_autopilot(make_settings(tmp_path), SECRETS, as_of, PaperSimBroker(), [])
    assert report.as_of == (as_of or date.today()) and report.entries == [] and report.audit_path


# ----------------------------------------------------------------------------------------------------------
# regressions: kill-switch cancels, cap accounting, run lock, staged plan, re-armed stops
# ----------------------------------------------------------------------------------------------------------
def trip(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "KILL").write_text("incident\n")


def test_kill_switch_still_cancels_every_unfilled_entry(tmp_path: Path) -> None:
    """A tripped KILL must not keep GTC entries alive: planned stale cancels run and every other resting
    unfilled swing-* entry is swept; closes, stop changes and new entries stay refused."""
    settings = make_settings(tmp_path)
    broker = PaperSimBroker()
    broker.submit(intent("STALE"))  # sim-1: the position manager's stale-entry cancel
    broker.submit(intent("FRESH"))  # sim-2: placed last night, not stale yet -> swept by the kill path
    broker.submit(OrderIntent(symbol="MAN", side=Side.LONG, qty=1, entry_limit=10.0, stop=9.0, target=None,
                              strategy="manual", client_order_id="manual-1", risk_dollars=1.0))  # not ours
    broker._positions["OLD"] = Position(symbol="OLD", qty=10, avg_entry=10.0, side=Side.LONG, stop=9.0)
    trip(tmp_path)
    exits = [
        ExitAction(kind=ExitKind.CANCEL_ORDER, symbol="STALE", reason=ExitReason.STALE_ENTRY, order_id="sim-1",
                   client_order_id=intent("STALE").client_order_id),
        ExitAction(kind=ExitKind.CLOSE, symbol="OLD", reason=ExitReason.TIME_STOP, qty=10, ref_price=10.0),
        ExitAction(kind=ExitKind.REPLACE_STOP, symbol="OLD", reason=ExitReason.BREAKEVEN, new_stop=10.0),
    ]
    report = run_autopilot(settings, SECRETS, AS_OF, broker, [intent("NEW")], exit_actions=exits)
    assert report.mode is AutopilotMode.KILLED and report.kill_switch
    assert [(r.kind, r.symbol, r.status.value) for r in report.exits] == [
        ("cancel_order", "STALE", "done"), ("close", "OLD", "refused"), ("replace_stop", "OLD", "refused"),
        ("cancel_order", "FRESH", "done"),
    ]  # fmt: skip
    assert report.exits[3].reason.startswith("kill_switch")
    assert statuses(report.entries) == {"NEW": "refused"}
    assert [o["symbol"] for o in broker.open_orders()] == ["MAN"]  # only the manual order is left working
    assert [p.symbol for p in broker.positions()] == ["OLD"] and broker.positions()[0].stop == 9.0


def test_kill_switch_dry_run_only_plans_the_cancels(tmp_path: Path) -> None:
    broker = PaperSimBroker()
    broker.submit(intent("FRESH"))
    trip(tmp_path)
    report = run_autopilot(make_settings(tmp_path), SECRETS, AS_OF, broker, [], dry_run=True)
    assert statuses(report.exits) == {"FRESH": "planned"} and len(broker.open_orders()) == 1


def test_errored_submit_consumes_the_daily_cap(tmp_path: Path) -> None:
    """A submit that raised after the broker accepted it is still a live order: it must use up the cap."""

    class TimesOut(PaperSimBroker):
        def submit(self, order: OrderIntent) -> dict[str, Any]:
            result = super().submit(order)
            if order.symbol == "AAA":
                raise TimeoutError("read timed out")  # accepted at the broker, response lost
            return result

    settings = make_settings(tmp_path, max_new_orders_per_day=1)
    broker = TimesOut()
    report = run_autopilot(settings, SECRETS, AS_OF, broker, [intent("AAA"), intent("BBB"), intent("CCC")])
    assert statuses(report.entries) == {"AAA": "error", "BBB": "capped", "CCC": "capped"}
    assert len(broker.open_orders()) == 1
    again = run_autopilot(settings, SECRETS, AS_OF, broker, [intent("DDD")])
    assert again.new_orders_before == 1 and statuses(again.entries) == {"DDD": "capped"}


def test_run_that_died_before_its_audit_still_counts_against_the_cap(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, max_new_orders_per_day=2)
    broker = PaperSimBroker()
    run_autopilot(settings, SECRETS, AS_OF, broker, [intent("AAA"), intent("BBB")])
    run_path(settings, "autopilot", AS_OF).unlink()  # SIGKILL / power loss before the audit write
    again = run_autopilot(settings, SECRETS, AS_OF, broker, [intent("AAA"), intent("BBB"), intent("CCC")])
    assert again.new_orders_before == 2
    assert statuses(again.entries) == {"AAA": "duplicate", "BBB": "duplicate", "CCC": "capped"}
    assert len(broker.open_orders()) == 2


def test_overlapping_run_aborts_on_the_lock(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    broker = PaperSimBroker()
    with _exclusive(lock_path(settings)) as held:
        assert held
        report = run_autopilot(settings, SECRETS, AS_OF, broker, [intent("AAA")])
    assert report.mode is AutopilotMode.ABORTED and "holds" in report.errors[0] and broker.open_orders() == []
    assert run_autopilot(settings, SECRETS, AS_OF, broker, [intent("AAA")]).submitted == 1  # lock released


def test_staged_plan_is_executed_exactly_by_a_named_human(tmp_path: Path) -> None:
    """`swing paper --approve` must run the staged plan (vetoes and cap applied, exits included), not the
    unfiltered intents file."""
    settings = make_settings(tmp_path, auto_submit_paper=False, max_new_orders_per_day=1)
    broker = PaperSimBroker()
    broker.submit(intent("STALE"))  # sim-1
    exits = [ExitAction(kind=ExitKind.CANCEL_ORDER, symbol="STALE", reason=ExitReason.STALE_ENTRY,
                        order_id="sim-1", client_order_id=intent("STALE").client_order_id)]
    intents = [intent("REJ"), intent("AAA"), intent("BBB")]
    staged = run_autopilot(settings, SECRETS, AS_OF, broker, intents, [review("REJ", ReviewDecision.REJECT)], exits)
    assert staged.mode is AutopilotMode.STAGED
    assert statuses(staged.entries) == {"REJ": "vetoed", "AAA": "staged", "BBB": "capped"}
    assert "swing paper --approve" in json.loads(Path(staged.staged_path).read_text())["why"]
    with pytest.raises(ValueError, match="human approver"):
        run_pending(settings, SECRETS, AS_OF, broker, APPROVER_PAPER)
    report = run_pending(settings, SECRETS, AS_OF, broker, "jane")
    assert report.mode is AutopilotMode.APPROVED and report.approved_by == "jane"
    assert statuses(report.entries) == {"AAA": "submitted"} and [r.status.value for r in report.exits] == ["done"]
    assert {o["symbol"] for o in broker.open_orders()} == {"AAA"}
    ledger = OrderLedger(settings.execution.ledger_file)
    assert {r["symbol"]: r["approved_by"] for r in ledger.all()} == {"AAA": "jane"}
    ledger.close()
    with pytest.raises(FileNotFoundError):
        run_pending(settings, SECRETS, date(2026, 10, 1), broker, "jane")


def test_place_stop_rearms_an_unprotected_position_but_not_under_the_kill_switch(tmp_path: Path) -> None:
    broker = PaperSimBroker()
    broker._positions["BARE"] = Position(symbol="BARE", qty=10, avg_entry=10.0, side=Side.LONG)
    arm = ExitAction(kind=ExitKind.PLACE_STOP, symbol="BARE", reason=ExitReason.NO_STOP, new_stop=9.0)
    report = run_autopilot(make_settings(tmp_path), SECRETS, AS_OF, broker, [], exit_actions=[arm])
    assert statuses(report.exits) == {"BARE": "done"} and broker.positions()[0].stop == 9.0
    again = run_autopilot(make_settings(tmp_path), SECRETS, AS_OF, broker, [], exit_actions=[arm])
    assert statuses(again.exits) == {"BARE": "refused"} and "already has a stop" in again.exits[0].reason
    broker.positions()[0].stop = None
    trip(tmp_path)
    killed = run_autopilot(make_settings(tmp_path), SECRETS, AS_OF, broker, [], exit_actions=[arm])
    assert statuses(killed.exits) == {"BARE": "refused"} and broker.positions()[0].stop is None
