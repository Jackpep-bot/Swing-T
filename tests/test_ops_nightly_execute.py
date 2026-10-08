"""ops.nightly positions -> execute steps and run_cycle (`swing autopilot`) on the sample provider with the
in-memory paper_sim broker. No network; every state file lives under tmp_path."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from swing_engine.core.config import Secrets, Settings
from swing_engine.core.models import Position, Review, ReviewDecision, Side
from swing_engine.execution.paper_sim import PaperSimBroker
from swing_engine.ops import nightly
from swing_engine.ops.nightly import NightlyReport, StepStatus, latest_signals_date, run_cycle, run_nightly
from tests import test_ops_nightly as nightly_tests
from tests.agent_fakes import FakeClient
from tests.test_ops_nightly import AS_OF, make_settings, no_secrets

contract = nightly_tests.contract  # autouse stubs for the breadth / playbook / shadow modules (contract_fn)


def runs(tmp_path: Path, kind: str, day: date = AS_OF) -> Path:
    return tmp_path / "data" / "runs" / kind / f"{day.isoformat()}.json"


def status(report: NightlyReport, step: str) -> str:
    found = report.step(step)
    assert found is not None, step
    return found.status.value


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # wide position cap so the sample signals are not all refused by LimitState on a 100k paper_sim account
    return make_settings(tmp_path, risk={"max_position_pct": 50.0}, execution={"nightly_execute": False})


def nightly_run(settings: Settings, tmp_path: Path, broker: Any, dry_run: bool, **kw: Any) -> NightlyReport:
    return run_nightly(settings, no_secrets(), AS_OF, "sample", None, dry_run, broker=broker, journal_root=tmp_path, **kw)


# ----------------------------------------------------------------------------------------------------------
# nightly
# ----------------------------------------------------------------------------------------------------------
def test_nightly_executes_on_paper_sim_with_equity_from_the_broker(settings: Settings, tmp_path: Path) -> None:
    broker = PaperSimBroker(starting_cash=80_000.0)
    report = nightly_run(settings, tmp_path, broker, False, execute=True)
    assert [s.name for s in report.steps] == list(nightly.STEP_NAMES)
    assert status(report, "size") == "ok" and report.step("size").data["equity"] == 80_000.0
    assert status(report, "positions") == "ok" and status(report, "execute") == "ok", report.step("execute").detail
    execute = report.step("execute").data
    assert execute["mode"] == "paper" and execute["approved_by"] == "autopilot:paper" and execute["submitted"] >= 1
    assert len(broker.open_orders()) == execute["submitted"]
    assert report.files["autopilot"] == str(runs(tmp_path, "autopilot")) and runs(tmp_path, "exits").exists()
    audit = json.loads(runs(tmp_path, "autopilot").read_text())
    assert audit["runs"][0]["entries"] and audit["runs"][0]["broker"] == "paper_sim"
    assert report.ok, report.failed


def test_nightly_never_executes_on_dry_run(settings: Settings, tmp_path: Path) -> None:
    broker = PaperSimBroker()
    report = nightly_run(settings, tmp_path, broker, True, execute=True)
    assert status(report, "execute") == "skip" and "dry run" in report.step("execute").detail
    assert broker.open_orders() == [] and not runs(tmp_path, "autopilot").exists()


def test_execute_defaults_to_settings(settings: Settings, tmp_path: Path) -> None:
    off = nightly_run(settings, tmp_path, PaperSimBroker(), False)
    assert status(off, "execute") == "skip" and "disabled" in off.step("execute").detail
    on_settings = settings.model_copy(update={"execution": settings.execution.model_copy(update={"nightly_execute": True})})
    broker = PaperSimBroker()
    on = nightly_run(on_settings, tmp_path, broker, False)
    assert status(on, "execute") == "ok" and broker.open_orders()
    forced_off = nightly_run(on_settings, tmp_path, PaperSimBroker(), False, execute=False)
    assert status(forced_off, "execute") == "skip"


def test_execute_without_broker_is_skipped(settings: Settings, tmp_path: Path) -> None:
    report = run_nightly(settings, no_secrets(), AS_OF, "sample", 50_000.0, False, execute=True, journal_root=tmp_path)
    assert status(report, "positions") == "skip" and status(report, "execute") == "skip"
    assert "no broker" in report.step("execute").detail


def test_positions_step_feeds_exits_to_execute(settings: Settings, tmp_path: Path) -> None:
    broker = PaperSimBroker()
    broker._positions["MANU"] = Position(symbol="MANU", qty=5, avg_entry=10.0, side=Side.LONG)  # orphan
    report = nightly_run(settings, tmp_path, broker, False, execute=True)
    positions = report.step("positions")
    assert positions.status is StepStatus.OK and positions.data["flagged"] == ["MANU"]
    assert report.step("execute").data["exits"] == {"flagged": 1}
    assert [a["kind"] for a in json.loads(runs(tmp_path, "exits").read_text())] == ["flag"]


def test_kill_switch_makes_execute_refuse_everything(settings: Settings, tmp_path: Path) -> None:
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "KILL").write_text("stop\n")
    broker = PaperSimBroker()
    report = nightly_run(settings, tmp_path, broker, False, execute=True)
    execute = report.step("execute")
    assert execute.status is StepStatus.OK and execute.data["mode"] == "killed" and execute.data["submitted"] == 0
    assert broker.open_orders() == []


def test_nightly_review_vetoes_reach_the_autopilot(settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_all(signals: list[Any], context: Any, cfg: Settings, client: Any = None, **_: Any) -> list[Review]:
        return [
            Review(symbol=s.symbol, strategy=s.strategy, thesis="t", catalyst_within_hold_window=False,
                   news_contradicts_setup=False, liquidity_concern=False, decision=ReviewDecision.REJECT)
            for s in signals
        ]  # fmt: skip

    monkeypatch.setattr("swing_engine.agent.review.review_candidates", reject_all)
    broker = PaperSimBroker()
    secrets = Secrets(_env_file=None, anthropic_api_key="sk-ant-test")
    report = run_nightly(settings, secrets, AS_OF, "sample", None, False, broker=broker, execute=True,
                         journal_root=tmp_path, journal_client=FakeClient(lambda kw: ValueError("offline")))
    assert status(report, "review") == "ok" and status(report, "execute") == "ok"
    assert report.step("execute").data["submitted"] == 0 and broker.open_orders() == []


def test_failed_review_holds_entries_but_execute_still_runs(settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*a: Any, **k: Any) -> list[Review]:
        raise RuntimeError("API down")

    monkeypatch.setattr("swing_engine.agent.review.review_candidates", broken)
    broker = PaperSimBroker()
    secrets = Secrets(_env_file=None, anthropic_api_key="sk-ant-test")
    report = run_nightly(settings, secrets, AS_OF, "sample", None, False, broker=broker, execute=True,
                         journal_root=tmp_path, journal_client=FakeClient(lambda kw: ValueError("offline")))
    assert status(report, "review") == "fail" and status(report, "execute") == "ok"
    execute = report.step("execute")
    held = report.step("size").data["intents"]
    assert held >= 1 and execute.data["entries_held_review_failed"] == held and "review step failed" in execute.detail
    assert execute.data["submitted"] == 0 and broker.open_orders() == []
    off = settings.model_copy(update={"execution": settings.execution.model_copy(update={"require_review_approval": False})})
    unguarded = run_nightly(off, secrets, AS_OF, "sample", None, False, broker=PaperSimBroker(), execute=True,
                            journal_root=tmp_path, journal_client=FakeClient(lambda kw: ValueError("offline")))
    assert unguarded.step("execute").data["entries_held_review_failed"] == 0


def test_review_and_journal_clients_come_from_secrets(settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The .env key lives in Secrets, not os.environ, so the steps must build their clients from it."""
    built: list[tuple[str, Any]] = []
    review_sentinel, journal_sentinel = object(), FakeClient(lambda kw: ValueError("offline"))

    def fake_async(secrets: Any = None) -> Any:
        built.append(("async", secrets))
        return review_sentinel

    def fake_sync(secrets: Any = None) -> Any:
        built.append(("sync", secrets))
        return journal_sentinel

    seen: dict[str, Any] = {}

    def fake_review(signals: list[Any], context: Any, cfg: Settings, client: Any = None, **_: Any) -> list[Review]:
        seen["client"] = client
        return []

    monkeypatch.setattr("swing_engine.agent.client.get_async_client", fake_async)
    monkeypatch.setattr("swing_engine.agent.client.get_client", fake_sync)
    monkeypatch.setattr("swing_engine.agent.review.review_candidates", fake_review)
    secrets = Secrets(_env_file=None, anthropic_api_key="sk-ant-test")
    report = run_nightly(settings, secrets, AS_OF, "sample", 50_000.0, False, journal_root=tmp_path)
    assert status(report, "review") == "ok" and status(report, "journal") == "ok"
    assert seen["client"] is review_sentinel and journal_sentinel.calls
    assert built == [("async", secrets), ("sync", secrets)]


# ----------------------------------------------------------------------------------------------------------
# run_cycle (`swing autopilot`)
# ----------------------------------------------------------------------------------------------------------
def test_cycle_sizes_latest_saved_signals_and_executes(settings: Settings, tmp_path: Path) -> None:
    nightly_run(settings, tmp_path, None, True)  # dry nightly: saves today's signals, no orders
    later = AS_OF + timedelta(days=1)
    assert latest_signals_date(settings, later) == AS_OF and latest_signals_date(settings, AS_OF - timedelta(days=1)) is None
    broker = PaperSimBroker()
    report = run_cycle(settings, no_secrets(), later, broker)
    assert [s.name for s in report.steps] == list(nightly.CYCLE_STEP_NAMES)
    assert status(report, "size") == "ok" and status(report, "positions") == "ok" and status(report, "execute") == "ok"
    assert report.step("execute").data["submitted"] >= 1 and broker.open_orders()
    assert report.files["signals_used"] == str(runs(tmp_path, "signals")) and runs(tmp_path, "cycle", later).exists()
    assert runs(tmp_path, "intents", later).exists()


def test_cycle_dry_run_plans_only(settings: Settings, tmp_path: Path) -> None:
    nightly_run(settings, tmp_path, None, True)
    broker = PaperSimBroker()
    report = run_cycle(settings, no_secrets(), AS_OF, broker, dry_run=True)
    execute = report.step("execute")
    assert execute.status is StepStatus.OK and execute.data["mode"] == "dry_run" and execute.data["submitted"] == 0
    assert "planned" in execute.data["entries"] and broker.open_orders() == []


def test_cycle_holds_intents_without_a_review_when_reviews_exist(settings: Settings, tmp_path: Path) -> None:
    nightly_run(settings, tmp_path, None, True)  # saves signals, no reviews (dry run)
    signals = json.loads(runs(tmp_path, "signals").read_text())
    assert len(signals) >= 2
    first = signals[0]
    review = Review(symbol=first["symbol"], strategy=first["strategy"], thesis="t", catalyst_within_hold_window=False,
                    news_contradicts_setup=False, liquidity_concern=False, decision=ReviewDecision.APPROVE_FOR_RISK_CHECK)
    runs(tmp_path, "reviews").parent.mkdir(parents=True, exist_ok=True)
    runs(tmp_path, "reviews").write_text(json.dumps([review.model_dump(mode="json")]))
    broker = PaperSimBroker()
    report = run_cycle(settings, no_secrets(), AS_OF, broker)
    execute = report.step("execute")
    sized = report.step("size").data["intents"]
    assert execute.status is StepStatus.OK and execute.data["entries_held_unreviewed"] == sized - 1
    assert {o["symbol"] for o in broker.open_orders()} <= {first["symbol"]}


def test_cycle_with_stale_or_missing_signals_still_manages_positions(settings: Settings, tmp_path: Path) -> None:
    broker = PaperSimBroker()
    missing = run_cycle(settings, no_secrets(), AS_OF, broker, store=_EmptyStore())
    assert status(missing, "size") == "skip" and "no saved signals" in missing.step("size").detail
    assert status(missing, "execute") == "ok"  # exits still run (here: nothing to do)

    nightly_run(settings, tmp_path, None, True)
    too_old = AS_OF + timedelta(days=settings.execution.max_signal_age_days + 1)
    stale = run_cycle(settings, no_secrets(), too_old, broker)
    assert status(stale, "size") == "skip" and "max_signal_age_days" in stale.step("size").detail
    assert status(stale, "positions") == "ok" and broker.open_orders() == []


class _EmptyStore:
    """A store with an empty panel table (positions still run; nothing is held)."""

    def has_table(self, name: str) -> bool:
        return False

    def read_table(self, name: str, where: Any = None) -> Any:
        return pd.DataFrame({"symbol": ["SPY"], "ts": [pd.Timestamp(AS_OF)], "close": [1.0]})


# ----------------------------------------------------------------------------------------------------------
# regressions: fail-closed entry gates
# ----------------------------------------------------------------------------------------------------------
def test_cycle_after_a_crashed_review_holds_entries(settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`swing autopilot` must not submit unreviewed entries the nightly's fail-closed gate held back."""
    def broken(*a: Any, **k: Any) -> list[Review]:
        raise RuntimeError("API down")

    monkeypatch.setattr("swing_engine.agent.review.review_candidates", broken)
    secrets = Secrets(_env_file=None, anthropic_api_key="sk-ant-test")
    nightly = run_nightly(settings, secrets, AS_OF, "sample", 100_000.0, False, journal_root=tmp_path,
                          journal_client=FakeClient(lambda kw: ValueError("offline")))
    assert status(nightly, "review") == "fail" and not runs(tmp_path, "reviews").exists()
    assert json.loads(runs(tmp_path, "review_status").read_text())["status"] == "fail"
    broker = PaperSimBroker()
    report = run_cycle(settings, no_secrets(), AS_OF + timedelta(days=1), broker)
    execute = report.step("execute")
    sized = report.step("size").data["intents"]
    assert sized >= 1 and execute.status is StepStatus.OK and execute.data["entries_held_review_failed"] == sized
    assert "failed" in execute.detail and execute.data["submitted"] == 0 and broker.open_orders() == []

    # a review that never finished (process died mid-call) also holds; one skipped on purpose does not
    runs(tmp_path, "review_status").write_text(json.dumps({"status": "running"}))
    assert run_cycle(settings, no_secrets(), AS_OF, PaperSimBroker()).step("execute").data["submitted"] == 0
    runs(tmp_path, "review_status").write_text(json.dumps({"status": "skip", "detail": "ANTHROPIC_API_KEY not set"}))
    assert run_cycle(settings, no_secrets(), AS_OF, PaperSimBroker()).step("execute").data["submitted"] >= 1


def test_cycle_falls_back_to_the_nightly_report_when_no_review_marker_exists(settings: Settings, tmp_path: Path) -> None:
    nightly_run(settings, tmp_path, None, True)
    runs(tmp_path, "review_status").unlink()
    payload = {"steps": [{"name": "review", "status": "fail", "detail": "RuntimeError: API down"}]}
    runs(tmp_path, "nightly").write_text(json.dumps(payload))
    report = run_cycle(settings, no_secrets(), AS_OF, PaperSimBroker())
    assert report.step("execute").data["submitted"] == 0 and "API down" in report.step("execute").detail


def test_failed_positions_step_holds_new_entries(settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*a: Any, **k: Any) -> list[Any]:
        raise KeyError("missing_feature")

    monkeypatch.setattr("swing_engine.execution.position_manager.review_positions", broken)
    broker = PaperSimBroker()
    report = nightly_run(settings, tmp_path, broker, False, execute=True)
    assert status(report, "positions") == "fail" and status(report, "execute") == "ok"
    execute = report.step("execute")
    assert execute.data["entries_held_positions_failed"] >= 1 and "positions step failed" in execute.detail
    assert execute.data["submitted"] == 0 and broker.open_orders() == []


def test_llm_disabled_skips_review_and_journal_prose(settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_: Any, **__: Any) -> Any:
        raise AssertionError("no Claude client may be built when agent.llm_enabled is false")

    monkeypatch.setattr("swing_engine.agent.client.get_async_client", boom)
    monkeypatch.setattr("swing_engine.agent.client.get_client", boom)
    off = settings.model_copy(update={"agent": settings.agent.model_copy(update={"llm_enabled": False})})
    report = run_nightly(off, Secrets(_env_file=None, anthropic_api_key="sk-ant-test"), AS_OF, "sample", 50_000.0,
                         False, journal_root=tmp_path)
    assert status(report, "review") == "skip" and "llm_enabled" in report.step("review").detail
    assert status(report, "journal") == "ok"
