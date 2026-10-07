"""ops.nightly: the full pipeline on the sample provider in a tmp tree (no network), plus failure isolation,
the post-review intent filter, the ranker hand-off and the guarantee that orders only leave through the
execute step (execution.autopilot); see tests/test_ops_nightly_execute.py for the execute path."""

from __future__ import annotations

import json
import pickle
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import yaml

from swing_engine.core import registry
from swing_engine.core.config import Secrets, Settings
from swing_engine.core.interfaces import Strategy
from swing_engine.core.models import OrderIntent, Review, ReviewDecision, Signal
from swing_engine.data.store import Store
from swing_engine.ops import nightly
from swing_engine.ops.nightly import NightlyReport, StepStatus, run_nightly
from tests.agent_fakes import FakeClient

AS_OF = date(2026, 9, 30)
EQUITY = 50_000.0
SYMBOLS = ["SPY", "ACME", "ACQD", "AMBR", "ARBR", "BLUE"]
HISTORY_YEARS = 2


# ----------------------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------------------
def make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    raw: dict[str, Any] = {
        "data": {"store_path": str(tmp_path / "data" / "swing.duckdb"), "bar_provider": "sample", "history_years": HISTORY_YEARS},
        "universe": {"static_symbols": SYMBOLS},
        "risk": {"kill_switch_file": str(tmp_path / "state" / "KILL"), "limits_state_file": str(tmp_path / "state" / "limits.json")},
        "execution": {"ledger_file": str(tmp_path / "state" / "orders.sqlite")},
        "strategies": {
            "sr_bounce": {"enabled": True},
            "pullback_trend": {"enabled": True},
            "rsi2_meanrev": {"enabled": True, "min_reward_risk": 0.0},
        },
    }
    for key, value in overrides.items():
        raw[key] = {**raw.get(key, {}), **value}
    (tmp_path / "settings.yaml").write_text(yaml.safe_dump(raw))
    return Settings.model_validate(raw)


def no_secrets() -> Secrets:
    return Secrets(_env_file=None)


def with_anthropic() -> Secrets:
    return Secrets(_env_file=None, anthropic_api_key="sk-ant-test")


def run_file(tmp_path: Path, kind: str) -> Path:
    return tmp_path / "data" / "runs" / kind / f"{AS_OF.isoformat()}.json"


def statuses(report: NightlyReport) -> dict[str, str]:
    return report.summary()


class FakeRanker:
    """Not a research.ranker.RankerModel, so the loader's pickle fallback is exercised."""

    def predict(self, panel_as_of: pd.DataFrame) -> pd.Series:
        return pd.Series(panel_as_of["close"].to_numpy(dtype=float), index=panel_as_of.index)


class BoomStrategy(Strategy):
    name = "boom"

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        raise RuntimeError("strategy exploded")


class ReadOnlyBroker:
    """A broker that reports equity and positions and refuses to submit anything."""

    def __init__(self, equity: float) -> None:
        self.equity = equity
        self.submits = 0

    def account(self) -> dict[str, Any]:
        return {"equity": self.equity, "status": "ACTIVE"}

    def positions(self) -> list[Any]:
        return []

    def open_orders(self) -> list[dict[str, Any]]:
        return []

    def submit(self, intent: OrderIntent) -> dict[str, Any]:
        self.submits += 1
        raise AssertionError("a dry-run nightly must never submit an order")


# ----------------------------------------------------------------------------------------------------------
# full pipeline
# ----------------------------------------------------------------------------------------------------------
def test_full_pipeline_dry_run_on_sample_provider(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    report = run_nightly(settings, no_secrets(), AS_OF, "sample", EQUITY, True, journal_root=tmp_path)

    assert [s.name for s in report.steps] == list(nightly.STEP_NAMES)
    assert statuses(report) == {
        "ingest": "ok", "features": "ok", "scan": "ok", "rank": "skip", "size": "ok", "review": "skip",
        "positions": "skip", "execute": "skip", "journal": "ok",
    }  # fmt: skip
    assert report.ok and report.failed == [] and report.dry_run and report.provider == "sample"
    assert "no broker" in report.step("positions").detail and "dry run" in report.step("execute").detail
    assert all(s.elapsed_s >= 0 for s in report.steps) and report.elapsed_s > 0
    assert "swing rank train" in report.step("rank").detail and "dry run" in report.step("review").detail

    ingest = report.step("ingest")
    assert ingest.data["symbols_with_bars"] == len(SYMBOLS) and ingest.data["bars_written"] > 0
    assert ingest.data["error_count"] == 0 and "errors" not in ingest.data
    assert report.step("features").data["symbols"] == len(SYMBOLS)
    scan = report.step("scan")
    assert scan.data["signals"] > 0 and scan.data["failures"] == {} and set(scan.data["per_strategy"]) == set(settings.strategies)
    assert scan.data["universe"] == len(SYMBOLS)  # static_symbols drive the screen
    size = report.step("size")
    assert size.data["equity"] == EQUITY and size.data["intents"] > 0
    assert report.step("journal").data["narrative"] is False

    signals = [Signal.model_validate(r) for r in json.loads(run_file(tmp_path, "signals").read_text())]
    assert signals and all(s.as_of == AS_OF for s in signals)
    assert [s.score for s in signals] == sorted((s.score for s in signals), reverse=True)
    intents = [OrderIntent.model_validate(r) for r in json.loads(run_file(tmp_path, "intents").read_text())]
    assert intents and all(i.qty > 0 and i.risk_dollars <= EQUITY * settings.risk.risk_per_trade_pct / 100 + 1e-9 for i in intents)
    assert not run_file(tmp_path, "reviews").exists()
    journal = tmp_path / "data" / "journal" / f"{AS_OF.isoformat()}.md"
    assert journal.exists() and report.files["journal"] == str(journal)

    report_path = run_file(tmp_path, "nightly")
    assert report.report_path == str(report_path) and report_path.exists()
    saved = json.loads(report_path.read_text())
    assert saved["as_of"] == AS_OF.isoformat() and [s["name"] for s in saved["steps"]] == list(nightly.STEP_NAMES)
    assert saved["files"]["signals"] == str(run_file(tmp_path, "signals"))

    with Store(str(tmp_path / "data" / "swing.duckdb")) as store:
        assert store.count("bars") > 0 and store.count(nightly.PANEL_TABLE) == store.count("bars")


def test_second_run_is_incremental_and_size_skips_without_equity(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    first = run_nightly(settings, no_secrets(), AS_OF, "sample", EQUITY, True, journal_root=tmp_path)
    second = run_nightly(settings, no_secrets(), AS_OF, None, None, True, journal_root=tmp_path)
    assert second.provider == "sample"  # default from settings.data.bar_provider
    assert second.step("ingest").data["bars_written"] < first.step("ingest").data["bars_written"]
    assert second.step("size").status is StepStatus.SKIP and "--equity" in second.step("size").detail
    assert statuses(second)["scan"] == "ok" and statuses(second)["journal"] == "ok"


def test_equity_override_from_settings_is_used(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, risk={"account_equity_override": 25_000.0})
    report = run_nightly(settings, no_secrets(), AS_OF, "sample", None, True, journal_root=tmp_path)
    assert report.step("size").status is StepStatus.OK and report.step("size").data["equity"] == 25_000.0


# ----------------------------------------------------------------------------------------------------------
# rank hand-off
# ----------------------------------------------------------------------------------------------------------
def test_rank_step_scores_cross_section_and_tags_signals(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    model_path = tmp_path / "data" / nightly.RANKER_FILENAME
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(pickle.dumps(FakeRanker()))
    report = run_nightly(settings, no_secrets(), AS_OF, "sample", EQUITY, True, journal_root=tmp_path)
    rank = report.step("rank")
    assert rank.status is StepStatus.OK, rank.detail
    with Store(str(tmp_path / "data" / "swing.duckdb")) as store:
        panel = store.read_table(nightly.PANEL_TABLE)
    latest = panel.loc[panel["ts"] == panel["ts"].max()]  # one sample name delists before as_of: not scored
    assert rank.data["scored"] == latest["symbol"].nunique() >= len(SYMBOLS) - 1
    assert rank.data["signals_tagged"] == report.step("scan").data["signals"]
    scores = json.loads(run_file(tmp_path, "rank").read_text())
    assert [r["symbol"] for r in scores] == [r["symbol"] for r in sorted(scores, key=lambda r: -r["score"])]
    signals = [Signal.model_validate(r) for r in json.loads(run_file(tmp_path, "signals").read_text())]
    by_symbol = {r["symbol"]: r["score"] for r in scores}
    assert all(s.features[nightly.RANK_FEATURE] == by_symbol[s.symbol] for s in signals)


def test_broken_ranker_fails_only_the_rank_step(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    model_path = tmp_path / "data" / nightly.RANKER_FILENAME
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"not a pickle")
    report = run_nightly(settings, no_secrets(), AS_OF, "sample", EQUITY, True, journal_root=tmp_path)
    assert report.step("rank").status is StepStatus.FAIL and not report.ok and report.failed == ["rank"]
    assert statuses(report)["size"] == "ok" and statuses(report)["journal"] == "ok"
    assert run_file(tmp_path, "nightly").exists()


# ----------------------------------------------------------------------------------------------------------
# review: enums only, filters intents, never sizes
# ----------------------------------------------------------------------------------------------------------
def test_review_filters_intents_by_decision_and_journal_degrades_without_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = make_settings(tmp_path)
    seen: dict[str, Any] = {}

    def fake_review(signals: list[Signal], context: Any, cfg: Settings, client: Any = None, **_: Any) -> list[Review]:
        seen.update(count=len(signals), context=context, client=client)
        out = []
        for i, s in enumerate(signals):
            decision = ReviewDecision.APPROVE_FOR_RISK_CHECK if i == 0 else ReviewDecision.REJECT
            out.append(
                Review(
                    symbol=s.symbol, strategy=s.strategy, thesis="t", catalyst_within_hold_window=False,
                    news_contradicts_setup=False, liquidity_concern=False, decision=decision,
                )
            )  # fmt: skip
        return out

    monkeypatch.setattr("swing_engine.agent.review.review_candidates", fake_review)
    journal_client = FakeClient(lambda kw: ValueError("no API in tests"))
    sentinel = object()
    report = run_nightly(
        settings, with_anthropic(), AS_OF, "sample", EQUITY, False,
        review_client=sentinel, journal_client=journal_client, journal_root=tmp_path,
    )  # fmt: skip
    review = report.step("review")
    assert review.status is StepStatus.OK, review.detail
    n_signals = report.step("scan").data["signals"]
    assert seen["count"] == min(n_signals, settings.agent.max_candidates_per_day) and seen["client"] is sentinel
    assert review.data["decisions"] == {"approve_for_risk_check": 1, "reject": n_signals - 1}
    assert review.data["intents_dropped"] == report.step("size").data["intents"] - 1
    reviews = [Review.model_validate(r) for r in json.loads(run_file(tmp_path, "reviews").read_text())]
    intents = [OrderIntent.model_validate(r) for r in json.loads(run_file(tmp_path, "intents").read_text())]
    approved = {(r.symbol, r.strategy) for r in reviews if r.decision is ReviewDecision.APPROVE_FOR_RISK_CHECK}
    assert len(intents) == 1 and {(i.symbol, i.strategy) for i in intents} == approved
    # the journal asked for prose, the fake client failed, the entry still got written (tables only)
    journal = report.step("journal")
    assert journal.status is StepStatus.OK and journal.data["narrative"] is True
    assert journal_client.calls and (tmp_path / "data" / "journal" / f"{AS_OF.isoformat()}.md").exists()


def test_review_skips_without_key_and_dry_run_skips_even_with_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = make_settings(tmp_path)
    calls: list[int] = []
    monkeypatch.setattr("swing_engine.agent.review.review_candidates", lambda *a, **k: calls.append(1) or [])
    no_key = run_nightly(settings, no_secrets(), AS_OF, "sample", EQUITY, False, journal_root=tmp_path, journal_client=FakeClient(lambda kw: ValueError("x")))
    assert no_key.step("review").status is StepStatus.SKIP and "ANTHROPIC_API_KEY" in no_key.step("review").detail
    dry = run_nightly(settings, with_anthropic(), AS_OF, "sample", EQUITY, True, journal_root=tmp_path)
    assert dry.step("review").status is StepStatus.SKIP and dry.step("journal").data["narrative"] is False
    assert calls == []


def test_review_failure_keeps_intents_and_journal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = make_settings(tmp_path)

    def broken(*a: Any, **k: Any) -> list[Review]:
        raise RuntimeError("API down apikey=sk-ant-test")

    monkeypatch.setattr("swing_engine.agent.review.review_candidates", broken)
    report = run_nightly(
        settings, with_anthropic(), AS_OF, "sample", EQUITY, False,
        journal_root=tmp_path, journal_client=FakeClient(lambda kw: ValueError("x")),
    )  # fmt: skip
    review = report.step("review")
    assert review.status is StepStatus.FAIL and "RuntimeError" in review.detail and "sk-ant-test" not in review.detail
    assert report.failed == ["review"] and statuses(report)["journal"] == "ok"
    intents = json.loads(run_file(tmp_path, "intents").read_text())
    assert len(intents) == report.step("size").data["intents"]  # nothing dropped without reviews


# ----------------------------------------------------------------------------------------------------------
# isolation and the no-orders guarantee
# ----------------------------------------------------------------------------------------------------------
def test_failures_are_isolated_and_the_report_is_still_written(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    with Store(":memory:") as store:
        report = run_nightly(settings, no_secrets(), AS_OF, "no_such_provider", EQUITY, True, store=store, journal_root=tmp_path)
    assert statuses(report) == {
        "ingest": "fail", "features": "fail", "scan": "fail", "rank": "skip", "size": "skip", "review": "skip",
        "positions": "skip", "execute": "skip", "journal": "ok",
    }  # fmt: skip
    assert "no_such_provider" in report.step("ingest").detail
    assert "no bars" in report.step("features").detail and "no signals" in report.step("size").detail
    assert report.failed == ["ingest", "features", "scan"] and not report.ok
    saved = json.loads(run_file(tmp_path, "nightly").read_text())
    assert [s["status"] for s in saved["steps"]] == ["fail", "fail", "fail", "skip", "skip", "skip", "skip", "skip", "ok"]


def test_strategy_failure_is_isolated_inside_scan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry.discover()
    monkeypatch.setitem(registry._REGISTRY["strategy"], BoomStrategy.name, BoomStrategy)
    settings = make_settings(tmp_path, strategies={"boom": {"enabled": True}})
    report = run_nightly(settings, no_secrets(), AS_OF, "sample", EQUITY, True, journal_root=tmp_path)
    scan = report.step("scan")
    assert scan.status is StepStatus.OK and "boom" in scan.data["failures"] and "strategy exploded" in scan.data["failures"]["boom"]
    assert "boom" not in scan.data["per_strategy"] and scan.data["signals"] > 0


def test_every_strategy_failing_fails_the_scan_step(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry.discover()
    monkeypatch.setitem(registry._REGISTRY["strategy"], BoomStrategy.name, BoomStrategy)
    settings = make_settings(tmp_path)
    settings.strategies.clear()
    settings.strategies["boom"] = {"enabled": True}
    report = run_nightly(settings, no_secrets(), AS_OF, "sample", EQUITY, True, journal_root=tmp_path)
    assert report.step("scan").status is StepStatus.FAIL and "every strategy failed" in report.step("scan").detail
    assert report.step("size").status is StepStatus.SKIP


def test_dry_run_broker_is_read_only_and_never_asked_to_submit(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    broker = ReadOnlyBroker(equity=75_000.0)
    report = run_nightly(settings, no_secrets(), AS_OF, "sample", None, True, broker=broker, execute=True, journal_root=tmp_path)
    size = report.step("size")
    assert size.status is StepStatus.OK and size.data["equity"] == 75_000.0 and size.data["open_positions"] == 0
    assert report.step("positions").status is StepStatus.OK and report.step("execute").status is StepStatus.SKIP
    assert broker.submits == 0
    imports = [ln for ln in Path(nightly.__file__).read_text().splitlines() if ln.startswith(("import ", "from "))]
    assert not any("execution" in ln for ln in imports)  # execution is loaded lazily by the execute step only


def test_nightly_module_never_submits_directly() -> None:
    """Orders leave the nightly only through execution.autopilot (loaded lazily by the execute step)."""
    source = Path(nightly.__file__).read_text()
    assert "swing_engine.execution" not in source and ".submit(" not in source
    assert "execution.autopilot.run_autopilot" in source
