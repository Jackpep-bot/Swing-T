"""research.drift (live vs replay), agent.weekly (report renderer, last-session rule) and the nightly weekly step."""
from __future__ import annotations

import json
import math
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from swing_engine.agent import weekly
from swing_engine.core.config import Settings
from swing_engine.data.store import Store
from swing_engine.ops import nightly
from swing_engine.research.drift import ABOVE, BELOW, drift_table

AS_OF = date(2026, 10, 9)  # Friday
ENTRY, STOP = 100.0, 95.0  # 5% stop: slippage cost = 2 x 10bp x 100 / 5 = 0.04R


def ledger(strategy: str, results: list[float], start: date, *, step_days: int = 1) -> pd.DataFrame:
    rows = []
    for i, r in enumerate(results):
        d = start + timedelta(days=i * step_days)
        row = {"strategy": strategy, "symbol": f"S{i}", "as_of": d, "entry": ENTRY, "stop": STOP}
        for h in (5, 10, 20):
            row.update({f"hit_{h}d": "time_exit", f"result_r_{h}d": r, f"exit_date_{h}d": d + timedelta(days=14)})
        rows.append(row)
    return pd.DataFrame(rows)


def noisy(mean: float, n: int) -> list[float]:
    return [mean + (0.5 if i % 2 else -0.5) for i in range(n)]


def test_drift_flags_live_below_and_above_replay_only_with_enough_live_trades() -> None:
    start = AS_OF - timedelta(days=60)
    live = pd.concat([
        ledger("bad", noisy(-0.5, 30), start),
        ledger("good", noisy(0.6, 30), start),
        ledger("thin", noisy(-0.5, 10), start),  # same drift, too few trades for a flag
        ledger("old", noisy(-0.5, 30), AS_OF - timedelta(days=400)),  # outside the window
    ])
    replay = pd.concat([ledger(s, noisy(0.1, 400), date(2025, 1, 2)) for s in ("bad", "good", "thin")])
    table = drift_table(live, replay, AS_OF).set_index("strategy")

    assert set(table.index) == {"bad", "good", "thin"}
    bad = table.loc["bad"]
    assert bad["n_10d"] == 30 and bad["replay_n_10d"] == 400
    assert bad["live_r_10d"] == pytest.approx(-0.54) and bad["replay_r_10d"] == pytest.approx(0.06)  # net of 0.04R
    assert bad["diff_10d"] == pytest.approx(-0.6) and bad["win_10d"] == pytest.approx(0.0)
    assert bad["flag_5d"] == BELOW and bad["flag"] == BELOW
    assert table.loc["good", "flag"] == ABOVE
    assert table.loc["thin", "flag"] == "" and table.loc["thin", "diff_10d"] == pytest.approx(-0.6)


def test_drift_without_replay_has_no_flag_and_nan_replay() -> None:
    table = drift_table(ledger("x", noisy(0.0, 25), AS_OF - timedelta(days=30)), pd.DataFrame(), AS_OF)
    assert table.loc[0, "flag"] == "" and math.isnan(table.loc[0, "replay_r_10d"]) and table.loc[0, "replay_n_10d"] == 0


def test_last_session_of_week() -> None:
    assert weekly.is_last_session_of_week(date(2026, 10, 9))  # Friday
    assert not weekly.is_last_session_of_week(date(2026, 10, 8))  # Thursday
    assert not weekly.is_last_session_of_week(date(2026, 10, 10))  # Saturday
    assert weekly.is_last_session_of_week(date(2026, 4, 2))  # Thursday before Good Friday
    assert weekly.iso_week(AS_OF) == "2026-W41"


def settings_for(tmp_path: Path) -> Settings:
    return Settings.model_validate({
        "data": {"store_path": str(tmp_path / "data" / "swing.duckdb")},
        "execution": {"ledger_file": str(tmp_path / "state" / "orders.sqlite")},
        "strategies": {"bad": {"enabled": True}, "good": {"enabled": False, "shadow_only": True}},
    })


def test_weekly_report_renders_sections_and_recommendations(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    live = pd.concat([ledger("bad", noisy(-0.5, 60), AS_OF - timedelta(days=80)),
                      ledger("good", noisy(0.6, 60), AS_OF - timedelta(days=80))])
    replay = pd.concat([ledger(s, noisy(0.1, 400), date(2025, 1, 2)) for s in ("bad", "good")])
    orders = [{"created_at": "2026-10-07T13:31:00+00:00", "symbol": "ACME", "side": "buy", "qty": 10,
               "strategy": "bad", "status": "filled", "broker_json": json.dumps({"raw": {"filled_avg_price": "101.5"}})}]
    actions = [{"day": "2026-10-07", "source": "autopilot", "kind": "entry", "symbol": "ACME", "strategy": "bad",
                "status": "submitted", "reason": ""}]
    text = weekly.render_report(AS_OF, settings, live, replay, orders, actions)

    assert text.startswith("# Weekly report 2026-W41 (2026-10-05 .. 2026-10-09)")
    assert "1 orders entered the ledger (1 filled); 1 actions reached the broker" in text and "101.50" in text
    assert "### Resolved this week" in text and "### To date" in text and "best **good** at +0.56R" in text
    assert "2 strategies compared; 1 below replay, 1 above." in text
    assert "**bad** (enabled): consider disabling." in text
    assert "**good** (shadow only): candidate for walk-forward." in text


def test_weekly_report_empty_inputs(tmp_path: Path) -> None:
    text = weekly.render_report(AS_OF, settings_for(tmp_path), pd.DataFrame(), pd.DataFrame(), [], [])
    assert "Nothing was sent to the paper broker this week." in text and "No live signals in the window." in text
    assert "None: no enabled strategy" in text


def test_nightly_weekly_step_runs_only_on_the_last_session(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    with Store(":memory:") as store:
        def ctx(day: date) -> nightly._Context:
            report = nightly.NightlyReport(as_of=day, provider="sample", dry_run=True, started_at=pd.Timestamp.now(tz="UTC"))
            return nightly._Context(settings=settings, secrets=None, as_of=day, provider="sample", equity=None,  # type: ignore[arg-type]
                                    dry_run=True, store=store, broker=None, review_client=None, journal_client=None,
                                    journal_root=tmp_path, report=report)

        skipped = nightly._run_step(ctx(date(2026, 10, 8)), "weekly", nightly._step_weekly)
        assert skipped.status is nightly.StepStatus.SKIP and "not the last session" in skipped.detail
        friday = ctx(AS_OF)
        ran = nightly._run_step(friday, "weekly", nightly._step_weekly)
    path = tmp_path / "data" / "journal" / "weekly-2026-W41.md"
    assert ran.status is nightly.StepStatus.OK and path.exists() and friday.report.files["weekly"] == str(path)
    assert nightly.STEP_NAMES[-2:] == ("weekly", "notify") and [n for n, _ in nightly.STEPS] == list(nightly.STEP_NAMES)
