"""ops.study: the daily markdown study built from the events table. In-memory / tmp stores only; no network."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from swing_engine.cli import app
from swing_engine.core.config import Settings
from swing_engine.data.store import Store
from swing_engine.ops import nightly, notify, receipts, study
from swing_engine.ops.nightly import StepStatus, run_nightly
from tests.test_ops_nightly import AS_OF, EQUITY, install_contract, make_settings, no_secrets
from tests.test_ops_notify import FakeSender

DAY = date(2026, 10, 9)
PREV = date(2026, 10, 8)
SIGNAL = {"side": "long", "entry": 50.0, "stop": 47.5, "target": 55.0, "reward_risk": 2.0}


def outcome(symbol: str, gross: float | None, net: float | None, hit: str = "target_hit", exit_day: date = DAY) -> dict:
    return {"horizon": 5, "hit": hit, "gross_r": gross, "net_r": net, "signal_as_of": PREV.isoformat(),
            "exit_date": exit_day.isoformat(), "taken": False,
            "gross_r_planned": None if gross is None else gross * 0.9, "cost_r": 0.1, "cost_note": "per-signal cost_bps (research.costs)"}


def seed(store: Store, settings: Settings) -> None:
    st = receipts.stamp(settings)
    ev = receipts.make_event
    cid = "swing-s1-AAA-20261009-long"
    rows = [
        ev(receipts.FIRE, "broker", "submitted", DAY, "s1", "AAA",
           {"regime": "healthy_uptrend", "multiplier": 0.5, "signal": SIGNAL,
            "intent": {"qty": 40, "client_order_id": cid}, "order": {"client_order_id": cid}}, key=cid, **st),
        ev(receipts.FIRE, "scan", "shadow-only signal", DAY, "s2", "BBB",
           {"regime": "healthy_uptrend", "shadow": True, "signal": {**SIGNAL, "target": None, "reward_risk": None}}, **st),
        ev(receipts.FIRE, "scan", "shadow-only signal", DAY, "s2", "CCC", {"shadow": True}, **st),
        ev(receipts.REFUSAL, "reward_risk", "reward_risk 1.00 below min 2.0", DAY, "s1", "DDD", **st),
        ev(receipts.REFUSAL, "reward_risk", "reward_risk 1.50 below min 2.0", DAY, "s1", "EEE", **st),
        ev(receipts.REFUSAL, "router", "multiplier 0 in this regime", DAY, "s3", **st),
        ev(receipts.EXIT, "time", "time_stop: held 10 sessions", DAY, "s1", "FFF", **st),
        ev(receipts.NOTE, "broker", "staged for a human approver", DAY, "s1", "GGG", **st),
        ev(receipts.OUTCOME, "target", "target_hit", DAY, "s1", "HHH", outcome("HHH", 2.0, 1.8), key="h|5d", **st),
        ev(receipts.OUTCOME, "stop", "stop_hit", DAY, "s1", "III", outcome("III", -1.0, -1.1, "stop_hit"), key="i|5d", **st),
        ev(receipts.OUTCOME, "fill", "open_through_stop", DAY, "s1", "JJJ", outcome("JJJ", None, None, "entry_skipped"),
           key="j|5d", **st),
        # stamped with another session, but exited on DAY: belongs to DAY's study
        ev(receipts.OUTCOME, "target", "target_hit", PREV, "s2", "KKK", outcome("KKK", 1.0, None), key="k|5d", **st),
        # another day entirely
        ev(receipts.OUTCOME, "stop", "stop_hit", PREV, "s2", "LLL", outcome("LLL", -1.0, -1.2, "stop_hit", PREV),
           key="l|5d", **st),
    ]
    assert receipts.write_events(store, rows) == len(rows)


def test_study_sections_numbers_and_determinism(tmp_path: Path) -> None:
    settings = Settings()
    with Store() as store:
        seed(store, settings)
        text = study.build_study(store, settings, DAY)
        assert text == study.build_study(store, settings, DAY)  # deterministic: no timestamps, sorted rows
        assert study.counts(study.day_events(store, DAY)) == {"fires": 3, "refusals": 3, "outcomes": 4}
        assert study.study_days(store) == [PREV, DAY]
        path = study.write_study(store, settings, DAY, tmp_path)
    assert path == tmp_path / "docs" / "studies" / "2026-10-09.md" and path.read_text(encoding="utf-8") == text
    lines = text.splitlines()
    assert lines[0] == "# Daily study: 2026-10-09"
    sig = receipts.stamp(settings)["engine_sig"]
    assert f"Engine signature(s) seen: `{sig}` (source: live). R values are gross AND net of modelled costs" in text
    assert "Market regime: healthy_uptrend (2 receipts)" in lines
    for heading in ("## Counts per strategy", "## Fires: chain lineage", "## Refusals by step", "## Exits",
                    "## Outcomes", "## Coverage"):
        assert heading in lines
    # counts: fires, of which shadow-only, refusals, exits, outcomes
    assert "| s1 | 1 | 0 | 2 | 1 | 3 |" in lines and "| s2 | 2 | 2 | 0 | 0 | 1 |" in lines
    assert "| s3 | 0 | 0 | 1 | 0 | 0 |" in lines and "| **total** | 3 | 2 | 3 | 1 | 4 |" in lines
    # lineage: only the fields the payload has
    assert ("- AAA s1 long: regime healthy_uptrend -> multiplier 0.5 -> entry 50.00 stop 47.50 target 55.00 (R:R 2.00) "
            "-> size 40 -> order swing-s1-AAA-20261009-long") in lines
    assert "- BBB s2 long: regime healthy_uptrend -> entry 50.00 stop 47.50 -> shadow only, no order" in lines
    assert "- CCC s2: shadow only, no order" in lines
    # refusals: grouped by step, numbers folded out of the reason, examples keep the exact text
    assert "- **reward_risk**: 2" in lines and "  - 2 x reward_risk N below min N" in lines
    assert "    - DDD s1: reward_risk 1.00 below min 2.0" in lines and "    - s3: multiplier 0 in this regime" in lines
    assert "- FFF s1 (time): time_stop: held 10 sessions" in lines
    # outcomes: s1 = 3 graded, 2 filled, 1 win, mean gross (2 - 1) / 2, mean net (1.8 - 1.1) / 2; s2's net is null
    assert "| s1 | 5d | 3 | 2 | 50% | +0.50 | +0.45 | +0.35 |" in lines
    assert "| s2 | 5d | 1 | 1 | 100% | +1.00 | +0.90 | - |" in lines
    assert "| JJJ | s1 | 5d | 2026-10-08 | 2026-10-09 | open_through_stop | - | - | 0.10 | - | no |" in lines
    assert "| KKK | s2 | 5d | 2026-10-08 | 2026-10-09 | target_hit | +1.00 | +0.90 | 0.10 | - | no |" in lines
    assert "LLL" not in text and "GGG" not in text
    assert "Cost basis: 4 x per-signal cost_bps (research.costs)" in lines
    assert "- symbols with at least one receipt: 11"  # GGG: the note's symbol in lines


def test_refusal_examples_are_capped() -> None:
    settings = Settings()
    st = receipts.stamp(settings)
    with Store() as store:
        receipts.write_events(store, [receipts.make_event(receipts.REFUSAL, "slot", "max open positions reached", DAY,
                                                          "s1", f"S{i:02d}", **st) for i in range(8)])
        lines = study.build_study(store, settings, DAY).splitlines()
    assert "  - 8 x max open positions reached" in lines
    assert [ln for ln in lines if ln.startswith("    - ")] == [f"    - S{i:02d} s1"
                                                              for i in range(study.MAX_EXAMPLES)]


def test_empty_day_and_missing_table_say_none(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    with Store() as store:
        empty = study.build_study(store, settings, DAY)  # no events table at all
        seed(store, settings)
        assert study.build_study(store, settings, date(2026, 1, 2)) == empty.replace("2026-10-09", "2026-01-02")
    lines = empty.splitlines()
    assert "Engine signature(s) seen: none." in empty and "Market regime: not recorded" in lines
    for heading in ("## Counts per strategy", "## Fires: chain lineage", "## Refusals by step", "## Exits",
                    "## Outcomes", "## Coverage"):
        assert lines[lines.index(heading) + 2] == "none"


def test_nightly_writes_the_study_and_telegram_names_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_contract(monkeypatch)  # stub breadth / playbook / shadow, as tests.test_ops_nightly does
    settings = make_settings(tmp_path)
    sender = FakeSender()
    with Store() as store:
        report = run_nightly(settings, no_secrets(), AS_OF, "sample", EQUITY, False, store=store, journal_root=tmp_path,
                             notify_sender=sender)
        events = study.day_events(store, AS_OF)
        expected = study.build_study(store, settings, AS_OF)
    names = [s.name for s in report.steps]
    assert names.index("study") == names.index("notify") - 1 and report.ok
    step = report.step("study")
    path = tmp_path / "docs" / "studies" / f"{AS_OF.isoformat()}.md"
    assert step.status is StepStatus.OK and report.files["study"] == str(path)
    assert path.read_text(encoding="utf-8") == expected and f"# Daily study: {AS_OF.isoformat()}" in expected
    n = study.counts(events)
    assert step.data == {"path": str(path), **n} and n["refusals"] > 0
    assert "## Coverage" in expected and "- bars: " in expected  # the sample store has bars for the session
    line = f"study: {path} ({n['fires']} fires, {n['refusals']} refusals, {n['outcomes']} outcomes)"
    assert line in sender.sent[0][1].splitlines()


def test_study_failure_is_a_skip_not_a_failed_night(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a: object, **k: object) -> Path:
        raise OSError("disk full")

    monkeypatch.setattr(study, "write_study", boom)
    report = nightly.NightlyReport(as_of=AS_OF, provider="sample", dry_run=True, started_at=pd.Timestamp.now(tz="UTC"))
    with Store() as store:
        ctx = nightly._Context(settings=make_settings(tmp_path), secrets=no_secrets(), as_of=AS_OF, provider="sample",
                               equity=None, dry_run=True, store=store, broker=None, review_client=None,
                               journal_client=None, journal_root=tmp_path, report=report)
        step = nightly._run_step(ctx, "study", nightly._step_study)
    assert step.status is StepStatus.SKIP and "disk full" in step.detail and report.ok
    assert "study:" not in notify.nightly_message(report)[1]


def test_cli_study_one_day_and_all(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, data={"studies_dir": str(tmp_path / "studies")})
    with Store(settings.data.store_path) as store:
        seed(store, settings)
    runner = CliRunner()
    base = ["--settings", str(tmp_path / "settings.yaml"), "study"]
    one = runner.invoke(app, [*base, "--as-of", "2026-10-09"])
    assert one.exit_code == 0, one.output
    assert sorted(p.name for p in (tmp_path / "studies").iterdir()) == ["2026-10-09.md"]
    first = (tmp_path / "studies" / "2026-10-09.md").read_text(encoding="utf-8")
    every = runner.invoke(app, [*base, "--all"])
    assert every.exit_code == 0, every.output
    assert sorted(p.name for p in (tmp_path / "studies").iterdir()) == ["2026-10-08.md", "2026-10-09.md"]
    assert (tmp_path / "studies" / "2026-10-09.md").read_text(encoding="utf-8") == first
    assert "LLL" in (tmp_path / "studies" / "2026-10-08.md").read_text(encoding="utf-8")
