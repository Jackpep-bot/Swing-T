"""CLI shells for `swing nightly --broker/--execute` and `swing autopilot` (ops.nightly replaced by fakes; the
hermetic settings/secrets/registry fixture from tests/test_cli.py). No network, no real broker."""
from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from swing_engine import cli
from swing_engine.core.config import load_settings
from swing_engine.ops.nightly import NightlyReport, StepResult, StepStatus
from tests import test_cli as cli_tests
from tests.test_cli import AS_OF, AS_OF_DATE, FakeBroker, fake_module, runner

workdir = cli_tests.workdir


def report(*steps: StepResult) -> NightlyReport:
    return NightlyReport(
        as_of=AS_OF_DATE, provider="fake_provider", dry_run=False, started_at=datetime(2026, 10, 2, tzinfo=UTC),
        steps=list(steps), report_path="/tmp/runs/cycle/2026-10-02.json",
    )


def with_execution(workdir: Path, monkeypatch: pytest.MonkeyPatch, **execution: Any) -> None:
    path = workdir / "settings.yaml"
    raw = yaml.safe_load(path.read_text())
    raw["execution"] = execution
    path.write_text(yaml.safe_dump(raw))
    load_settings.cache_clear()


# ----------------------------------------------------------------------------------------------------------
# nightly
# ----------------------------------------------------------------------------------------------------------
def test_nightly_passes_broker_and_execute(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def run_nightly(settings, secrets, as_of, provider, equity, dry_run, *, broker=None, execute=None, **_):
        seen.update(broker=broker, execute=execute, dry_run=dry_run)
        return report(StepResult(name="execute", status=StepStatus.OK, detail="paper: entries {'submitted': 2}"))

    fake_module(monkeypatch, "ops.nightly", run_nightly=run_nightly)
    result = runner.invoke(cli.app, ["nightly", "--as-of", AS_OF, "--broker", FakeBroker.name, "--execute"])
    assert result.exit_code == 0, result.output
    assert isinstance(seen["broker"], FakeBroker) and seen["execute"] is True and seen["dry_run"] is False
    assert "execute via fake_broker" in result.output and "submitted" in result.output


def test_nightly_execute_defaults_to_settings_and_no_execute_overrides(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with_execution(workdir, monkeypatch, broker=FakeBroker.name, nightly_execute=True)
    seen: list[dict[str, Any]] = []

    def run_nightly(settings, secrets, as_of, provider, equity, dry_run, *, broker=None, execute=None, **_):
        seen.append({"broker": broker, "execute": execute})
        return report()

    fake_module(monkeypatch, "ops.nightly", run_nightly=run_nightly)
    assert runner.invoke(cli.app, ["nightly", "--as-of", AS_OF]).exit_code == 0
    assert runner.invoke(cli.app, ["nightly", "--as-of", AS_OF, "--no-execute"]).exit_code == 0
    assert isinstance(seen[0]["broker"], FakeBroker) and seen[0]["execute"] is True
    assert seen[1]["execute"] is False


def test_nightly_without_broker_keeps_the_old_contract(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def run_nightly(settings, secrets, as_of, provider, equity, dry_run, *, broker=None, execute=None, **_):
        seen.update(broker=broker, execute=execute)
        return report()

    fake_module(monkeypatch, "ops.nightly", run_nightly=run_nightly)
    assert runner.invoke(cli.app, ["nightly", "--as-of", AS_OF]).exit_code == 0
    assert seen == {"broker": None, "execute": False}  # model defaults: no broker, nightly_execute off


def test_unopenable_broker_still_runs_data_steps_then_fails_when_executing(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Any] = []

    def run_nightly(settings, secrets, as_of, provider, equity, dry_run, *, broker=None, execute=None, **_):
        calls.append(broker)
        return report()

    fake_module(monkeypatch, "ops.nightly", run_nightly=run_nightly)
    executing = runner.invoke(cli.app, ["nightly", "--as-of", AS_OF, "--broker", "nope", "--execute"])
    assert executing.exit_code == cli.EXIT_USAGE and "unavailable" in executing.output
    reading = runner.invoke(cli.app, ["nightly", "--as-of", AS_OF, "--broker", "nope", "--no-execute"])
    dry = runner.invoke(cli.app, ["nightly", "--as-of", AS_OF, "--broker", "nope", "--execute", "--dry-run"])
    assert reading.exit_code == 0 and dry.exit_code == 0 and calls == [None, None, None]


# ----------------------------------------------------------------------------------------------------------
# autopilot
# ----------------------------------------------------------------------------------------------------------
def test_autopilot_runs_the_cycle_and_prints_the_summary(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def run_cycle(settings, secrets, as_of, broker, dry_run):
        seen.update(as_of=as_of, broker=broker, dry_run=dry_run)
        return report(
            StepResult(name="size", status=StepStatus.OK, detail="2 intents"),
            StepResult(name="positions", status=StepStatus.OK, detail="0 exit actions"),
            StepResult(name="execute", status=StepStatus.OK, detail="paper",
                       data={"mode": "paper", "submitted": 2, "approved_by": "autopilot:paper"}),
        )

    fake_module(monkeypatch, "ops.nightly", run_cycle=run_cycle)
    result = runner.invoke(cli.app, ["autopilot", "--as-of", AS_OF, "--broker", FakeBroker.name, "--dry-run"])
    assert result.exit_code == 0, result.output
    assert seen["as_of"] == AS_OF_DATE and isinstance(seen["broker"], FakeBroker) and seen["dry_run"] is True
    assert "autopilot:paper" in result.output and "positions" in result.output and "dry run" in result.output


def test_autopilot_defaults_today_and_settings_broker(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with_execution(workdir, monkeypatch, broker=FakeBroker.name)
    seen: dict[str, Any] = {}

    def run_cycle(settings, secrets, as_of, broker, dry_run):
        seen.update(as_of=as_of, broker=broker, dry_run=dry_run)
        return report()

    fake_module(monkeypatch, "ops.nightly", run_cycle=run_cycle)
    result = runner.invoke(cli.app, ["autopilot"])
    assert result.exit_code == 0, result.output
    assert seen["as_of"] == date.today() and isinstance(seen["broker"], FakeBroker) and seen["dry_run"] is False


def test_autopilot_needs_a_broker_and_fails_on_failed_steps(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module(
        monkeypatch, "ops.nightly",
        run_cycle=lambda *a: report(StepResult(name="execute", status=StepStatus.FAIL, detail="reconcile failed")),
    )  # fmt: skip
    no_broker = runner.invoke(cli.app, ["autopilot", "--as-of", AS_OF])
    assert no_broker.exit_code == cli.EXIT_USAGE and "no broker" in no_broker.output
    failed = runner.invoke(cli.app, ["autopilot", "--as-of", AS_OF, "--broker", FakeBroker.name])
    assert failed.exit_code == cli.EXIT_FAILED and "reconcile failed" in failed.output


def test_autopilot_has_help() -> None:
    result = runner.invoke(cli.app, ["autopilot", "--help"])
    assert result.exit_code == 0 and "--dry-run" in result.output and "--broker" in result.output
