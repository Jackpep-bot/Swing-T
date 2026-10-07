"""CLI shells for `swing regime`, `swing replay` and `swing shadow report`, plus the regime block in the
nightly/autopilot step report. Same approach as tests/test_cli.py: CliRunner, no network, the playbook /
replay / shadow / store modules replaced by in-process fakes in sys.modules (ops.nightly is the real one)."""

from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest
from pydantic import BaseModel, Field

from swing_engine import cli
from swing_engine.ops.nightly import NightlyReport, StepResult, StepStatus
from tests import test_cli as cli_tests
from tests.test_cli import AS_OF, AS_OF_DATE, FakeStore, fake_module, runner

workdir = cli_tests.workdir
store_file = cli_tests.store_file
START, END = "2026-01-02", "2026-09-30"


class FakeState(BaseModel):
    as_of: date
    spy_trend: str = "up"
    vol_regime: str = "normal"
    breadth: str = "neutral"
    regime: str = "narrow_uptrend"
    notes: list[str] = Field(default_factory=lambda: ["breadth below 50% above the 50-day"])


def install_playbook(monkeypatch: pytest.MonkeyPatch, table: dict[str, float]) -> dict[str, Any]:
    seen: dict[str, Any] = {}

    def market_breadth(panel: pd.DataFrame, *, exclude: Any = ()) -> pd.DataFrame:
        seen["breadth_symbols"] = sorted(panel["symbol"].unique())
        seen["exclude"] = tuple(exclude)
        return pd.DataFrame({"pct_above_50": [40.0]}, index=pd.DatetimeIndex([AS_OF], name="session"))

    def market_state(panel: pd.DataFrame, as_of: date, breadth: Any = None, settings: Any = None) -> FakeState:
        seen.update(as_of=as_of, breadth=breadth, max_ts=pd.to_datetime(panel["ts"]).max().date())
        return FakeState(as_of=as_of)

    def select_strategies(state: FakeState, settings: Any) -> dict[str, float]:
        seen["selected_for"] = state.regime
        return dict(table)

    fake_module(monkeypatch, "features.breadth", market_breadth=market_breadth)
    fake_module(monkeypatch, "strategies.playbook", market_state=market_state, select_strategies=select_strategies,
                MarketState=FakeState)
    return seen


# ----------------------------------------------------------------------------------------------------------
# help
# ----------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("args", [["regime"], ["replay"], ["shadow", "report"]])
def test_new_commands_have_help(args: list[str]) -> None:
    result = runner.invoke(cli.app, [*args, "--help"])
    assert result.exit_code == 0 and "Usage" in result.output


def test_top_level_help_lists_regime_replay_shadow() -> None:
    result = runner.invoke(cli.app, ["--help"])
    assert all(name in result.output for name in ("regime", "replay", "shadow"))


# ----------------------------------------------------------------------------------------------------------
# swing regime
# ----------------------------------------------------------------------------------------------------------
def test_regime_prints_state_and_allowed_strategies_with_scaled_risk(
    store_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = install_playbook(monkeypatch, {"fake_strat": 0.5})
    result = runner.invoke(cli.app, ["regime", "--as-of", AS_OF])
    assert result.exit_code == 0, result.output
    assert "narrow_uptrend" in result.output and "breadth below 50%" in result.output
    assert "fake_strat" in result.output and "allowed" in result.output and "0.50" in result.output
    assert seen["as_of"] == AS_OF_DATE and seen["max_ts"] <= AS_OF_DATE and seen["selected_for"] == "narrow_uptrend"
    assert seen["breadth_symbols"] == ["AAA", "BBB"] and seen["exclude"] == ("SPY", "QQQ", "IWM")
    assert seen["breadth"] is not None  # the CLI hands the playbook the screened breadth, like the nightly


def test_regime_shows_blocked_strategies(store_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_playbook(monkeypatch, {})
    result = runner.invoke(cli.app, ["regime", "--as-of", AS_OF])
    assert result.exit_code == 0, result.output
    assert "blocked" in result.output and "not in the playbook table" in result.output


def test_regime_without_the_playbook_is_a_missing_module_error(
    store_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "swing_engine.strategies.playbook", None)  # import -> ImportError
    result = runner.invoke(cli.app, ["regime", "--as-of", AS_OF])
    assert result.exit_code == cli.EXIT_MISSING_MODULE
    assert "strategies.playbook" in result.output


def test_scan_saves_the_playbook_routing_with_its_signals(store_file: Path, workdir: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    install_playbook(monkeypatch, {"fake_strat": 0.5})
    result = runner.invoke(cli.app, ["scan", "--as-of", AS_OF])
    assert result.exit_code == 0, result.output
    saved = json.loads(cli_tests.run_file(workdir, "regime").read_text())
    assert saved["regime"] == "narrow_uptrend" and saved["allowed"] == {"fake_strat": 0.5}


def test_scan_without_routing_warns_and_saves_no_regime_file(store_file: Path, workdir: Path,
                                                             monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "swing_engine.strategies.playbook", None)  # import -> ImportError
    result = runner.invoke(cli.app, ["scan", "--as-of", AS_OF])
    assert result.exit_code == 0, result.output
    assert cli_tests.run_file(workdir, "signals").exists() and not cli_tests.run_file(workdir, "regime").exists()
    assert "routing not saved" in result.output


# ----------------------------------------------------------------------------------------------------------
# swing replay
# ----------------------------------------------------------------------------------------------------------
def fake_replay_result() -> SimpleNamespace:
    days = pd.date_range(START, periods=3, freq="B")
    return SimpleNamespace(
        summary={"trades": 4, "win_rate": 0.5, "expectancy_r": 0.4, "max_dd": -0.03},
        by_strategy=pd.DataFrame({"strategy": ["fake_strat"], "n": [4], "avg_r": [0.4]}),
        by_regime=pd.DataFrame({"regime": ["healthy_uptrend", "choppy"], "n": [3, 1], "avg_r": [0.7, -0.5]}),
        trades=pd.DataFrame({"symbol": ["AAA"], "entry_date": [days[0]], "result_r": [1.5]}),
        equity_curve=pd.Series([100_000.0, 100_500.0, 101_000.0], index=days, name="equity"),
        daily=pd.DataFrame({"regime": ["healthy_uptrend"] * 3}, index=days),
    )


def test_replay_runs_prints_tables_and_saves_json(
    store_file: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}

    def run_replay(settings, store, start, end, *, strategies=None, use_router=True, equity=100_000.0, costs=None,
                   shadow_table="shadow_signals"):
        seen.update(store=store, start=start, end=end, strategies=strategies, use_router=use_router, equity=equity,
                    costs=costs, shadow_table=shadow_table)
        return fake_replay_result()

    class CostModel:
        def __init__(self, bps_per_side: float = 10.0) -> None:
            self.bps_per_side = bps_per_side

    fake_module(monkeypatch, "research.replay", run_replay=run_replay)
    fake_module(monkeypatch, "research.backtest", CostModel=CostModel)
    args = ["replay", "--start", START, "--end", END, "-s", "fake_strat,other", "--no-router",
            "--equity", "50000", "--cost", "bps_per_side=5"]
    result = runner.invoke(cli.app, args)
    assert result.exit_code == 0, result.output
    assert isinstance(seen["store"], FakeStore) and seen["start"] == date.fromisoformat(START)
    assert seen["end"] == date.fromisoformat(END) and seen["strategies"] == ["fake_strat", "other"]
    assert seen["use_router"] is False and seen["equity"] == 50_000.0 and seen["costs"].bps_per_side == 5
    assert seen["shadow_table"] == cli.REPLAY_SHADOW_TABLE  # never the live nightly's shadow_signals
    assert "By strategy" in result.output and "By regime" in result.output and "choppy" in result.output
    path = workdir / "data" / "runs" / "replay" / f"{START}_{END}.json"
    saved = json.loads(path.read_text())
    assert saved["summary"]["trades"] == 4 and saved["use_router"] is False
    assert saved["by_regime"][1]["regime"] == "choppy" and len(saved["equity_curve"]) == 3
    assert saved["trades"][0]["symbol"] == "AAA" and saved["daily"][0]["regime"] == "healthy_uptrend"


def test_replay_defaults_use_the_router_and_no_cost_override(store_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def run_replay(settings, store, start, end, **kw):
        seen.update(kw)
        return SimpleNamespace(summary={"trades": 0}, by_strategy=pd.DataFrame(), by_regime=None, trades=pd.DataFrame(),
                               equity_curve=pd.Series(dtype=float), daily=pd.DataFrame())

    fake_module(monkeypatch, "research.replay", run_replay=run_replay)
    result = runner.invoke(cli.app, ["replay", "--start", START, "--end", END])
    assert result.exit_code == 0, result.output
    assert seen["use_router"] is True and seen["strategies"] is None and seen["costs"] is None
    assert seen["equity"] == cli.DEFAULT_REPLAY_EQUITY and "(no trades)" in result.output


def test_replay_rejects_start_after_end(store_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module(monkeypatch, "research.replay", run_replay=lambda *a, **k: pytest.fail("must not run"))
    result = runner.invoke(cli.app, ["replay", "--start", END, "--end", START])
    assert result.exit_code == cli.EXIT_USAGE


def test_replay_without_the_module_is_a_missing_module_error(store_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "swing_engine.research.replay", None)
    result = runner.invoke(cli.app, ["replay", "--start", START, "--end", END])
    assert result.exit_code == cli.EXIT_MISSING_MODULE and "research.replay" in result.output


# ----------------------------------------------------------------------------------------------------------
# swing shadow report
# ----------------------------------------------------------------------------------------------------------
def test_shadow_report_passes_filters_and_prints_groups(store_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def shadow_report(store, since=None, group_by=("strategy", "regime"), *, horizon=None, taken=None, table="x"):
        seen.update(store=store, since=since, group_by=group_by, horizon=horizon, taken=taken, table=table)
        return pd.DataFrame({"strategy": ["rsi2_meanrev"], "n": [12], "win_rate": [0.58], "expectancy": [0.21],
                             "n_target": [77]})

    fake_module(monkeypatch, "research.shadow", shadow_report=shadow_report)
    result = runner.invoke(cli.app, ["shadow", "report", "--since", "2026-06-01", "--by", "strategy",
                                     "--horizon", "10", "--untaken", "--replay"])
    assert result.exit_code == 0, result.output
    assert isinstance(seen["store"], FakeStore) and seen["since"] == date(2026, 6, 1)
    assert seen["group_by"] == ("strategy",) and seen["horizon"] == 10 and seen["taken"] is False
    assert seen["table"] == cli.REPLAY_SHADOW_TABLE
    assert "n_target" not in result.output  # compact columns by default
    every = runner.invoke(cli.app, ["shadow", "report", "--by", "strategy", "--all-columns"])
    assert every.exit_code == 0 and "n_target" in every.output and "77" in every.output
    assert "rsi2_meanrev" in result.output and "0.58" in result.output


def test_shadow_report_defaults_and_empty_ledger(store_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def shadow_report(store, since=None, group_by=("strategy", "regime")):
        seen.update(since=since, group_by=group_by)
        return pd.DataFrame()

    fake_module(monkeypatch, "research.shadow", shadow_report=shadow_report)
    result = runner.invoke(cli.app, ["shadow", "report"])
    assert result.exit_code == 0, result.output
    assert seen == {"since": None, "group_by": ("strategy", "regime")} and "no graded shadow signals" in result.output


# ----------------------------------------------------------------------------------------------------------
# nightly / autopilot print the regime block
# ----------------------------------------------------------------------------------------------------------
def test_nightly_prints_the_market_regime(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"regime": "choppy", "allowed": {"rsi2_meanrev": 0.75}, "blocked": {"breakout_52w": "not in table"}}

    def run_nightly(settings, secrets, as_of, provider, equity, dry_run, **_):
        return NightlyReport(
            as_of=AS_OF_DATE, provider="fake_provider", dry_run=True, started_at=datetime(2026, 10, 2, tzinfo=UTC),
            steps=[StepResult(name="scan", status=StepStatus.OK, detail="1 signals")], regime=payload,
        )

    fake_module(monkeypatch, "ops.nightly", run_nightly=run_nightly)
    result = runner.invoke(cli.app, ["nightly", "--as-of", AS_OF, "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "Market regime" in result.output and "choppy" in result.output and "rsi2_meanrev x0.75" in result.output
    assert "breakout_52w" in result.output
