"""CLI tests for the ops commands (`swing doctor`, `swing nightly`, `swing monitor outcomes`).

Same approach as tests/test_cli.py: Typer CliRunner, no network, the ops modules replaced by in-process fakes
installed in sys.modules so the commands are tested as thin shells. One test runs the real offline doctor.
"""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from swing_engine import cli
from swing_engine.ops.doctor import Check, CheckStatus
from swing_engine.ops.nightly import NightlyReport, StepResult, StepStatus
from tests import test_cli as cli_tests
from tests.test_cli import AS_OF, AS_OF_DATE, fake_module, runner

workdir = cli_tests.workdir  # the hermetic settings/secrets/registry fixture, re-exported under the same name


def make_report(*steps: StepResult, **extra: Any) -> NightlyReport:
    return NightlyReport(
        as_of=AS_OF_DATE,
        provider="fake_provider",
        dry_run=False,
        started_at=datetime(2026, 10, 2, 22, 0, tzinfo=UTC),
        steps=list(steps),
        report_path="/tmp/runs/nightly/2026-10-02.json",
        **extra,
    )


# ----------------------------------------------------------------------------------------------------------
# help
# ----------------------------------------------------------------------------------------------------------
def test_help_lists_ops_commands() -> None:
    top = runner.invoke(cli.app, ["--help"])
    assert top.exit_code == 0 and "doctor" in top.output and "nightly" in top.output
    monitor = runner.invoke(cli.app, ["monitor", "--help"])
    assert monitor.exit_code == 0 and "outcomes" in monitor.output


@pytest.mark.parametrize("args", [["doctor"], ["nightly"], ["monitor", "outcomes"]])
def test_ops_commands_have_help(args: list[str]) -> None:
    result = runner.invoke(cli.app, [*args, "--help"])
    assert result.exit_code == 0 and "Usage" in result.output


# ----------------------------------------------------------------------------------------------------------
# doctor
# ----------------------------------------------------------------------------------------------------------
def test_doctor_prints_checks_and_passes_flags(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def run_doctor(settings, secrets, live_checks, *, send_test=False, settings_path=None, **_):
        seen.update(live=live_checks, send_test=send_test, settings_path=settings_path, provider=settings.data.bar_provider)
        return [
            Check(name="env_file", status=CheckStatus.OK, detail="present"),
            Check(name="secret:MASSIVE_API_KEY", status=CheckStatus.WARN, detail="missing"),
            Check(name="live", status=CheckStatus.SKIP, detail="pass --live"),
        ]

    fake_module(monkeypatch, "ops.doctor", run_doctor=run_doctor)
    result = runner.invoke(cli.app, ["doctor"])
    assert result.exit_code == 0, result.output
    assert seen == {"live": False, "send_test": False, "settings_path": workdir / "settings.yaml", "provider": "fake_provider"}
    assert "env_file" in result.output and "MASSIVE_API_KEY" in result.output and "missing" in result.output
    assert "ok=1" in result.output and "skip=1" in result.output and "warn=1" in result.output

    result = runner.invoke(cli.app, ["doctor", "--live", "--send-test"])
    assert result.exit_code == 0, result.output
    assert seen["live"] is True and seen["send_test"] is True


def test_doctor_exit_code_one_on_any_failure(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module(
        monkeypatch,
        "ops.doctor",
        run_doctor=lambda *a, **k: [
            Check(name="python", status=CheckStatus.OK, detail="3.12"),
            Check(name="live:massive", status=CheckStatus.FAIL, detail="HTTP 401: credentials rejected"),
        ],
    )
    result = runner.invoke(cli.app, ["doctor", "--live"])
    assert result.exit_code == cli.EXIT_FAILED
    assert "credentials rejected" in result.output and "fail=1" in result.output


def test_doctor_send_test_requires_live(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[int] = []
    fake_module(monkeypatch, "ops.doctor", run_doctor=lambda *a, **k: called.append(1) or [])
    result = runner.invoke(cli.app, ["doctor", "--send-test"])
    assert result.exit_code == cli.EXIT_USAGE and "--live" in result.output
    assert called == []


def test_doctor_real_offline_run_is_green(workdir: Path) -> None:
    """The real ops.doctor against the hermetic workdir: no network, nothing may fail."""
    result = runner.invoke(cli.app, ["doctor"])
    assert result.exit_code == 0, result.output
    for name in ("settings_yaml", "store_path", "calendar", "kill_switch", "python", "package:pandas"):
        assert name in result.output
    assert "fail=" not in result.output


# ----------------------------------------------------------------------------------------------------------
# nightly
# ----------------------------------------------------------------------------------------------------------
def test_nightly_passes_args_and_prints_steps(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def run_nightly(settings, secrets, as_of, provider, equity, dry_run):
        seen.update(as_of=as_of, provider=provider, equity=equity, dry_run=dry_run)
        return make_report(
            StepResult(name="ingest", status=StepStatus.OK, elapsed_s=1.25, detail="2,698 bars"),
            StepResult(name="rank", status=StepStatus.SKIP, detail="no ranker"),
            files={"signals": "/tmp/runs/signals/2026-10-02.json"},
        )

    fake_module(monkeypatch, "ops.nightly", run_nightly=run_nightly)
    args = ["nightly", "--as-of", AS_OF, "--provider", "sample", "--equity", "50000", "--dry-run"]
    result = runner.invoke(cli.app, args)
    assert result.exit_code == 0, result.output
    assert seen == {"as_of": AS_OF_DATE, "provider": "sample", "equity": 50000.0, "dry_run": True}
    assert "ingest" in result.output and "2,698 bars" in result.output and "1.25" in result.output
    assert "no ranker" in result.output and "dry run" in result.output
    assert "Files written" in result.output and "runs/signals" in result.output and "runs/nightly" in result.output


def test_nightly_defaults_to_today_and_settings_provider(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def run_nightly(settings, secrets, as_of, provider, equity, dry_run):
        seen.update(as_of=as_of, provider=provider, equity=equity, dry_run=dry_run)
        return make_report()

    fake_module(monkeypatch, "ops.nightly", run_nightly=run_nightly)
    result = runner.invoke(cli.app, ["nightly"])
    assert result.exit_code == 0, result.output
    assert seen == {"as_of": date.today(), "provider": "fake_provider", "equity": None, "dry_run": False}


def test_nightly_exit_code_one_when_a_step_failed(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module(
        monkeypatch,
        "ops.nightly",
        run_nightly=lambda *a, **k: make_report(
            StepResult(name="ingest", status=StepStatus.OK),
            StepResult(name="scan", status=StepStatus.FAIL, detail="RuntimeError: every strategy failed"),
            StepResult(name="journal", status=StepStatus.OK),
        ),
    )
    result = runner.invoke(cli.app, ["nightly", "--as-of", AS_OF])
    assert result.exit_code == cli.EXIT_FAILED
    assert "every strategy failed" in result.output and "failed steps: scan" in result.output


def test_nightly_bad_date_is_usage_error(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module(monkeypatch, "ops.nightly", run_nightly=lambda *a, **k: make_report())
    result = runner.invoke(cli.app, ["nightly", "--as-of", "tonight"])
    assert result.exit_code != 0 and "ISO date" in result.output


def test_nightly_missing_module_gives_clear_error(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "swing_engine.ops.nightly", None)
    result = runner.invoke(cli.app, ["nightly"])
    assert result.exit_code == cli.EXIT_MISSING_MODULE and "swing_engine.ops.nightly" in result.output


# ----------------------------------------------------------------------------------------------------------
# monitor outcomes
# ----------------------------------------------------------------------------------------------------------
def test_monitor_outcomes_prints_whatever_columns_come_back(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def compute_outcomes(settings, days):
        seen.update(days=days, provider=settings.data.bar_provider)
        return pd.DataFrame(
            {"rule": ["halt", "gap"], "alerts": [3, 5], "hit_rate": [0.6667, 0.4], "avg_fwd_1d": [0.0123, -0.0045]}
        )

    fake_module(monkeypatch, "monitor.outcomes", compute_outcomes=compute_outcomes)
    result = runner.invoke(cli.app, ["monitor", "outcomes", "--days", "5"])
    assert result.exit_code == 0, result.output
    assert seen == {"days": 5, "provider": "fake_provider"}
    for text in ("rule", "alerts", "hit_rate", "avg_fwd_1d", "halt", "gap", "0.6667", "last 5 days", "2 rows"):
        assert text in result.output, text


def test_monitor_outcomes_default_days_and_empty_frame(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def compute_outcomes(settings, days):
        seen["days"] = days
        return pd.DataFrame()

    fake_module(monkeypatch, "monitor.outcomes", compute_outcomes=compute_outcomes)
    result = runner.invoke(cli.app, ["monitor", "outcomes"])
    assert result.exit_code == 0, result.output
    assert seen["days"] == cli.DEFAULT_OUTCOMES_DAYS and "no alert outcomes" in result.output


def test_monitor_outcomes_accepts_list_of_dicts(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module(monkeypatch, "monitor.outcomes", compute_outcomes=lambda settings, days: [{"rule": "ssr", "alerts": 1}])
    result = runner.invoke(cli.app, ["monitor", "outcomes"])
    assert result.exit_code == 0, result.output
    assert "ssr" in result.output and "alerts" in result.output


def test_monitor_outcomes_missing_module_prints_clear_message(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "swing_engine.monitor.outcomes", None)
    result = runner.invoke(cli.app, ["monitor", "outcomes"])
    assert result.exit_code == cli.EXIT_MISSING_MODULE
    assert "swing_engine.monitor.outcomes" in result.output and "implemented yet" in result.output


def test_monitor_outcomes_missing_function_prints_clear_message(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module(monkeypatch, "monitor.outcomes")  # module exists, compute_outcomes does not
    result = runner.invoke(cli.app, ["monitor", "outcomes"])
    assert result.exit_code == cli.EXIT_MISSING_MODULE and "compute_outcomes" in result.output
