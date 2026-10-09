"""ops.notify: nightly summary step, weekly report, research summary and `swing notify-test`, with a fake sender."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from swing_engine.cli import app
from swing_engine.core.config import Secrets
from swing_engine.ops import nightly, notify
from swing_engine.ops.nightly import NightlyReport, StepResult, StepStatus

AS_OF = date(2026, 10, 9)


class FakeSender:
    def __init__(self, ok: bool = True, boom: bool = False) -> None:
        self.sent: list[tuple[str, str]] = []
        self.ok, self.boom = ok, boom

    def __call__(self, title: str, body: str) -> bool:
        if self.boom:
            raise RuntimeError("network down")
        self.sent.append((title, body))
        return self.ok


def ctx(report: NightlyReport, sender: FakeSender | None, dry_run: bool = False) -> nightly._Context:
    return nightly._Context(settings=None, secrets=Secrets(_env_file=None), as_of=AS_OF, provider="sample",  # type: ignore[arg-type]
                            equity=None, dry_run=dry_run, store=None, broker=None, review_client=None,
                            journal_client=None, journal_root=None, report=report, notify_sender=sender)


def make_report(tmp_path: Path, weekly: bool = False) -> NightlyReport:
    report = NightlyReport(as_of=AS_OF, provider="sample", dry_run=False, started_at=pd.Timestamp.now(tz="UTC"))
    report.regime = {"regime": "healthy_uptrend", "allowed": {"sr_bounce": 1.0, "rsi2": 0.5}}
    report.steps = [
        StepResult(name="ingest", status=StepStatus.OK),
        StepResult(name="float", status=StepStatus.SKIP, detail="sample"),
        StepResult(name="scan", status=StepStatus.FAIL, detail="ValueError: bad bars"),
        StepResult(name="shadow", status=StepStatus.OK, data={"recorded": 7, "graded": 3}),
        StepResult(name="execute", status=StepStatus.OK,
                   data={"submitted": 2, "entries": {"submitted": 2}, "exits": {"done": 1}}),
    ]
    report.files["journal"] = str(tmp_path / "2026-10-09.md")
    if weekly:
        path = tmp_path / "weekly-2026-W41.md"
        path.write_text("# Weekly\n\n\n| a | b |\n|---|---|\n| 1 | 2 |\n" + "line\n" * 2000)
        report.files["weekly"] = str(path)
    return report


def test_nightly_message_names_only_non_ok_steps(tmp_path: Path) -> None:
    title, body = notify.nightly_message(make_report(tmp_path), [("sr_bounce", 4, 0.61), ("rsi2", 2, -0.2)])
    assert title == "Nightly 2026-10-09: 1 step(s) FAILED"
    assert body.splitlines() == [
        "regime: healthy_uptrend | allowed: sr_bounce x1, rsi2 x0.5",
        "FAIL scan: ValueError: bad bars",
        "skipped: float",
        "paper orders: 2 submitted; entries submitted 2; exits done 1",
        "shadow: 7 recorded, 3 graded",
        "top shadow graded today (net R/trade): sr_bounce +0.61R (4), rsi2 -0.20R (2)",
        f"journal: {tmp_path / '2026-10-09.md'}",
    ]
    assert "ingest" not in body


def test_notify_step_sends_summary_and_weekly(tmp_path: Path) -> None:
    sender = FakeSender()
    step = nightly._run_step(ctx(make_report(tmp_path, weekly=True), sender), "notify", nightly._step_notify)
    assert step.status is StepStatus.OK and step.data["weekly"] is True
    assert [t for t, _ in sender.sent] == ["Nightly 2026-10-09: 1 step(s) FAILED", "Weekly report 2026-W41"]
    weekly_body = sender.sent[1][1]
    assert len(weekly_body) <= notify.BODY_BUDGET and "truncated; full report:" in weekly_body
    assert "|---|" not in weekly_body and "\n\n\n" not in weekly_body


@pytest.mark.parametrize("sender", [FakeSender(ok=False), FakeSender(boom=True)])
def test_notify_failure_never_fails_the_nightly(tmp_path: Path, sender: FakeSender) -> None:
    report = make_report(tmp_path)
    step = nightly._run_step(ctx(report, sender), "notify", nightly._step_notify)
    assert step.status is StepStatus.SKIP and "nightly:" in step.detail


def test_notify_skips_dry_run_and_missing_secrets(tmp_path: Path) -> None:
    sender = FakeSender()
    dry = nightly._run_step(ctx(make_report(tmp_path), sender, dry_run=True), "notify", nightly._step_notify)
    assert dry.status is StepStatus.SKIP and sender.sent == []
    none = nightly._run_step(ctx(make_report(tmp_path), None), "notify", nightly._step_notify)
    assert none.status is StepStatus.SKIP and "TELEGRAM" in none.detail
    assert nightly.STEP_NAMES[-1] == "notify" and "notify" not in nightly.CYCLE_STEP_NAMES


def test_research_summary() -> None:
    board = pd.DataFrame([
        {"strategy": f"s{i}", "window": 2024, "horizon": 10, "n": 100 + i, "net_r": 0.1 * i, "t": 1.5,
         "haircut_sharpe": -0.2} for i in range(7)
    ])
    sender = FakeSender()
    assert notify.notify_research_summary(board.iloc[0:0], 794, board, sender=sender) is True
    title, body = sender.sent[0]
    lines = body.splitlines()
    assert title == "Research rebuild done" and lines[:3] == ["survivors: none", "trials: 794", "top 5 leaderboard rows:"]
    assert lines[3] == "- s0 10d [2024]: n 100, net_r +0.000, t +1.500, haircut_sharpe -0.200" and len(lines) == 8
    surv = notify.research_message(board.iloc[:2], 10, [])[1].splitlines()[0]
    assert surv == "survivors (2): s0@10d, s1@10d"
    assert notify.notify_research_summary(0, 1, [], sender=FakeSender(boom=True)) is False
    assert notify.notify_research_summary(0, 1, [], secrets=Secrets(_env_file=None)) is False


def test_notify_test_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    dry = runner.invoke(app, ["notify-test", "--dry-run"])
    assert dry.exit_code == 0 and notify.TEST_TITLE in dry.output
    sender = FakeSender()
    monkeypatch.setattr(notify, "telegram_sender", lambda secrets: sender)
    sent = runner.invoke(app, ["notify-test"])
    assert sent.exit_code == 0 and "sent" in sent.output and sender.sent[0][0] == notify.TEST_TITLE
    monkeypatch.setattr(notify, "telegram_sender", lambda secrets: None)
    missing = runner.invoke(app, ["notify-test"])
    assert missing.exit_code == 1 and "TELEGRAM" in missing.output


def test_shadow_top_today_ranks_exits_on_the_day() -> None:
    def row(strategy: str, r: float, exit_day: date) -> dict[str, object]:
        return {"strategy": strategy, "entry": 100.0, "entry_price": 100.0, "stop": 95.0, "hit_10d": "target_hit", "result_r_10d": r,
                "exit_date_10d": exit_day}

    class FakeStore:
        def has_table(self, name: str) -> bool:
            return True

        def read_table(self, name: str) -> pd.DataFrame:
            return pd.DataFrame([row("a", 1.0, AS_OF), row("a", 0.0, AS_OF), row("b", 2.0, AS_OF),
                                 row("c", -1.0, AS_OF), row("d", 5.0, date(2026, 10, 8))])

    top = notify.shadow_top_today(FakeStore(), AS_OF, n=2)
    assert [(s, n) for s, n, _ in top] == [("b", 1), ("a", 2)] and top[0][2] < 2.0  # net of round-trip cost
