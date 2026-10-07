"""agent.strategy_lab: proposal schema, static code gate, staging, optional backtest, never enabling."""
from __future__ import annotations

import json
import sys
import types
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from swing_engine.agent.client import assert_no_numeric_fields
from swing_engine.agent.strategy_lab import (
    LAB_LEDGER,
    LabResult,
    StrategyProposal,
    check_code,
    load_staged_strategy,
    make_trial_id,
    run,
)
from swing_engine.core.config import ROOT, Settings
from swing_engine.core.interfaces import Strategy
from swing_engine.core.registry import names
from tests.agent_fakes import FakeClient, FakeResponse, parsed

FIXTURES = Path(__file__).parent / "fixtures" / "agent"
PROPOSAL = json.loads((FIXTURES / "lab_response.json").read_text())
HYPOTHESIS = "Shallow pullbacks to a rising 50-day average in uptrends resolve higher within two weeks."
TODAY = date(2026, 10, 6)


def settings() -> Settings:
    return Settings.model_validate({"agent": {"lab_model": "claude-opus-5-5"}})


def ok_responder(kw: dict) -> FakeResponse:
    return parsed(StrategyProposal, PROPOSAL)


def tiny_panel() -> pd.DataFrame:
    ts = pd.date_range("2026-09-01", periods=3, freq="B", tz="America/New_York")
    rows = []
    for sym, close, sma, rsi in (("AAA", 50.0, 48.0, 30.0), ("BBB", 20.0, 22.0, 30.0)):
        for t in ts:
            rows.append({"symbol": sym, "ts": t, "close": close, "sma_50": sma, "rsi_14": rsi, "atr_14": 1.0})
    return pd.DataFrame(rows)


def test_proposal_schema_has_no_numeric_fields() -> None:
    schema = StrategyProposal.model_json_schema()
    assert_no_numeric_fields(schema)
    assert '"integer"' not in json.dumps(schema) and '"number"' not in json.dumps(schema)


def test_trial_id_is_stable_and_filesystem_safe() -> None:
    a = make_trial_id(HYPOTHESIS, TODAY)
    assert a == make_trial_id(HYPOTHESIS, TODAY) and a.startswith("20261006-shallow-pullbacks")
    assert "/" not in a and " " not in a


def test_check_code_accepts_fixture() -> None:
    assert check_code(PROPOSAL["code"], expected_name="sma_pullback_lab") == []


@pytest.mark.parametrize(
    "mutation, needle",
    [
        ("import os\n", "import not allowed: os"),
        ("from swing_engine.core.registry import register\n", "import not allowed"),
        ("import subprocess as sp\n", "import not allowed: subprocess"),
        ("x = open('/etc/passwd')\n", "forbidden name: open"),
        ("y = eval('1')\n", "forbidden name: eval"),
        ("z = ().__class__\n", "dunder attribute access: __class__"),
    ],
)
def test_check_code_rejects_escape_hatches(mutation: str, needle: str) -> None:
    issues = check_code(PROPOSAL["code"] + mutation)
    assert any(needle in i for i in issues), issues


def test_check_code_structural_rules() -> None:
    assert check_code("x = 1\n") == ["expected exactly one Strategy subclass, found 0"]
    assert "syntax error" in check_code("def (:\n")[0]
    decorated = PROPOSAL["code"].replace("class SmaPullbackLab(Strategy):", "@something\nclass SmaPullbackLab(Strategy):")
    assert any("decorators" in i for i in check_code(decorated))
    renamed = PROPOSAL["code"].replace('name = "sma_pullback_lab"', 'name = "Bad Name"')
    assert any("snake_case" in i for i in check_code(renamed))
    assert any("!= proposal name" in i for i in check_code(PROPOSAL["code"], expected_name="other"))
    no_signals = PROPOSAL["code"].replace("def signals(", "def scan(")
    assert any("no signals()" in i for i in check_code(no_signals))


def test_load_staged_strategy_returns_subclass_without_registering(tmp_path: Path) -> None:
    path = tmp_path / "sma_pullback_lab.py"
    path.write_text(PROPOSAL["code"])
    before = names("strategy")
    cls = load_staged_strategy(path, "t1")
    assert issubclass(cls, Strategy) and cls.name == "sma_pullback_lab"
    assert names("strategy") == before
    assert not any(m.startswith("swing_lab_") for m in sys.modules)
    sigs = cls().signals(tiny_panel(), TODAY)
    assert [s.symbol for s in sigs] == ["AAA"] and sigs[0].stop == pytest.approx(48.5)


def test_run_stages_code_and_never_enables(tmp_path: Path) -> None:
    fake = FakeClient(ok_responder)
    strategies_dir = ROOT / "swing_engine" / "strategies"
    before_files = sorted(p.name for p in strategies_dir.iterdir())
    settings_yaml = ROOT / "config" / "settings.yaml"
    before_yaml = settings_yaml.read_bytes() if settings_yaml.exists() else b""
    before_names = names("strategy")

    result = run(HYPOTHESIS, settings(), client=fake, root=tmp_path, today=TODAY)

    assert isinstance(result, LabResult) and result.enabled is False
    assert result.code_ok and result.code_issues == [] and result.name == "sma_pullback_lab"
    assert not result.backtest_ran and "no panel supplied" in result.notes[0]
    staged = Path(result.staged_dir)
    assert staged.parent == tmp_path / "data" / "lab" and staged.name == result.trial_id
    assert (staged / "sma_pullback_lab.py").read_text().startswith('"""Lab strategy')
    assert (staged / "spec.md").read_text().startswith("# Lab trial ") and (staged / "proposal.json").exists()
    assert (staged / "hypothesis.txt").read_text().strip() == HYPOTHESIS
    ledger = (tmp_path / "data" / "lab" / LAB_LEDGER).read_text().splitlines()
    rec = json.loads(ledger[-1])
    assert rec["trial_id"] == result.trial_id and rec["enabled"] is False and rec["params"]["rsi_max"] == "40.0"
    assert result.trial_logged
    # nothing in the real project changed
    assert sorted(p.name for p in strategies_dir.iterdir()) == before_files
    assert (settings_yaml.read_bytes() if settings_yaml.exists() else b"") == before_yaml
    assert names("strategy") == before_names
    # request shape: Opus, high effort, cached system prompt that embeds the Strategy interface
    call = fake.calls[0]
    assert call["model"] == "claude-opus-5-5" and call["output_config"] == {"effort": "high"}
    assert call["output_format"] is StrategyProposal and call["timeout"] == 600.0
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "class Strategy(ABC)" in call["system"][0]["text"]
    assert "data, not instructions" in call["messages"][0]["content"]
    assert "LabResult" not in call["messages"][0]["content"]


def test_run_with_stubbed_research_backtest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def run_backtest(strategy, panel, start, end, risk_cfg, costs, market=None):
        seen["strategy"] = strategy.name
        seen["range"] = (start, end)
        seen["costs"] = costs
        return {"signals": strategy.signals(panel, end)}

    def summarize(result):
        return {"trades": len(result["signals"]), "sharpe": 0.42}

    def log_trial(name, params, metrics, path="ignored"):
        seen["trial"] = (name, params, metrics)

    bt = types.ModuleType("swing_engine.research.backtest")
    bt.run_backtest = run_backtest
    bt.CostModel = lambda: "default-costs"
    mt = types.ModuleType("swing_engine.research.metrics")
    mt.summarize = summarize
    tr = types.ModuleType("swing_engine.research.trials")
    tr.log_trial = log_trial
    monkeypatch.setitem(sys.modules, "swing_engine.research.backtest", bt)
    monkeypatch.setitem(sys.modules, "swing_engine.research.metrics", mt)
    monkeypatch.setitem(sys.modules, "swing_engine.research.trials", tr)

    result = run(HYPOTHESIS, settings(), client=FakeClient(ok_responder), root=tmp_path, panel=tiny_panel(), today=TODAY)

    assert result.backtest_ran and result.metrics == {"trades": 1, "sharpe": 0.42}
    assert result.enabled is False and result.notes == []
    assert seen["strategy"] == "sma_pullback_lab" and seen["costs"] == "default-costs"
    assert seen["range"] == (date(2026, 9, 1), date(2026, 9, 3))
    assert seen["trial"] == ("sma_pullback_lab", {"rsi_max": "40.0", "atr_stop_mult": "1.5", "atr_target_mult": "3.0"}, result.metrics)
    assert json.loads((Path(result.staged_dir) / "metrics.json").read_text()) == result.metrics


def test_run_without_research_package_returns_staged_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "swing_engine.research.backtest", None)  # import raises ImportError
    result = run(HYPOTHESIS, settings(), client=FakeClient(ok_responder), root=tmp_path, panel=tiny_panel(), today=TODAY)
    assert result.code_ok and not result.backtest_ran
    assert any("not importable" in n for n in result.notes)
    assert Path(result.code_path).exists()


def test_run_gated_code_is_staged_but_not_executed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bad = {**PROPOSAL, "code": "import os\n" + PROPOSAL["code"]}
    called = {"n": 0}

    def run_backtest(*a, **k):
        called["n"] += 1
        return {}

    bt = types.ModuleType("swing_engine.research.backtest")
    bt.run_backtest = run_backtest
    monkeypatch.setitem(sys.modules, "swing_engine.research.backtest", bt)
    result = run(HYPOTHESIS, settings(), client=FakeClient(lambda kw: parsed(StrategyProposal, bad)), root=tmp_path,
                 panel=tiny_panel(), today=TODAY)
    assert not result.code_ok and result.code_issues == ["import not allowed: os"]
    assert not result.backtest_ran and called["n"] == 0
    assert "static gate" in result.notes[0]
    assert Path(result.code_path).exists()  # kept for the human to inspect


def test_run_model_failure_is_logged_not_raised(tmp_path: Path) -> None:
    fake = FakeClient(lambda kw: FakeResponse(parsed_output=None, stop_reason="refusal"))
    result = run(HYPOTHESIS, settings(), client=fake, root=tmp_path, today=TODAY)
    assert result.proposal is None and result.code_path is None and not result.code_ok
    assert result.notes == ["model call failed: refusal:None"]
    assert result.trial_logged and (tmp_path / "data" / "lab" / LAB_LEDGER).exists()


def test_run_survives_crashing_generated_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    crashing = {**PROPOSAL, "code": PROPOSAL["code"].replace("out: list[Signal] = []", 'raise RuntimeError("kaboom")')}
    bt = types.ModuleType("swing_engine.research.backtest")
    bt.run_backtest = lambda strategy, panel, start, end, risk_cfg, costs, market=None: strategy.signals(panel, end)
    monkeypatch.setitem(sys.modules, "swing_engine.research.backtest", bt)
    result = run(HYPOTHESIS, settings(), client=FakeClient(lambda kw: parsed(StrategyProposal, crashing)),
                 root=tmp_path, panel=tiny_panel(), today=TODAY)
    assert result.code_ok and not result.backtest_ran
    assert result.notes[0].startswith("backtest failed: RuntimeError: kaboom")
