"""CLI tests. Typer CliRunner, no network, and every other module is replaced by an in-process fake
installed in sys.modules, so these pass regardless of what the concurrently written modules look like.
"""

from __future__ import annotations

import json
import pickle
import sys
import types
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import pytest
import yaml
from typer.testing import CliRunner

from swing_engine import cli
from swing_engine.core import registry
from swing_engine.core.config import Secrets, load_settings
from swing_engine.core.interfaces import BarProvider, Broker, Strategy
from swing_engine.core.models import OrderIntent, Position, Review, ReviewDecision, Side, Signal

FIXTURES = Path(__file__).parent / "fixtures" / "cli"
AS_OF = "2026-10-02"
AS_OF_DATE = date.fromisoformat(AS_OF)
EQUITY = 50_000.0
STOP_FRACTION = 0.95
TARGET_FRACTION = 1.10
SYMBOLS = ("AAA", "BBB")
PANEL_DAYS = 5
WIDE_TERMINAL = {"COLUMNS": "200"}  # keep rich from wrapping table cells in assertions

runner = CliRunner(env=WIDE_TERMINAL)


# ----------------------------------------------------------------------------------------------------------
# fakes (module level so pickle can find them)
# ----------------------------------------------------------------------------------------------------------
def make_panel(symbols: tuple[str, ...] = SYMBOLS, days: int = PANEL_DAYS) -> pd.DataFrame:
    ts = pd.date_range(end=AS_OF, periods=days, freq="B", tz="America/New_York")
    rows: list[dict[str, Any]] = []
    for i, symbol in enumerate(symbols):
        for j, t in enumerate(ts):
            px = 10.0 + i + j * 0.1
            rows.append(
                {
                    "symbol": symbol,
                    "ts": t,
                    "open": px,
                    "high": px * 1.01,
                    "low": px * 0.99,
                    "close": px,
                    "volume": 1_000_000.0,
                    "market_trend_state": 1.0,
                    "market_vol_regime": 1.0,
                }
            )
    return pd.DataFrame(rows)


class FakeStore:
    """Minimal data.store.Store stand-in (contract: read_bars, read_table, write_table)."""

    instances: list[FakeStore] = []

    def __init__(self, path: str, with_panel: bool = True):
        self.path = path
        self.bars = make_panel()
        self.tables: dict[str, pd.DataFrame] = {"panel": make_panel()} if with_panel else {}
        self.calls: list[tuple[str, Any]] = []
        FakeStore.instances.append(self)

    def read_bars(self, symbols: list[str] | None, start: date, end: date) -> pd.DataFrame:
        self.calls.append(("read_bars", (symbols, start, end)))
        return self.bars

    def read_table(self, name: str, where: str | None = None) -> pd.DataFrame:
        self.calls.append(("read_table", name))
        if name not in self.tables:
            raise KeyError(f"no table {name}")
        return self.tables[name]

    def write_table(self, name: str, df: pd.DataFrame, keys: list[str]) -> None:
        self.calls.append(("write_table", (name, keys)))
        self.tables[name] = df


class FakeStoreNoPanel(FakeStore):
    def __init__(self, path: str):
        super().__init__(path, with_panel=False)


class FakeStrategy(Strategy):
    name = "fake_strat"
    default_params = {"lookback": 5}

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        assert (panel["ts"].dt.date <= as_of).all(), "scan must hand strategies a point-in-time panel"
        last = panel.groupby("symbol").tail(1)
        return [
            Signal(
                strategy=self.name,
                symbol=str(row.symbol),
                as_of=as_of,
                entry=float(row.close),
                stop=float(row.close) * STOP_FRACTION,
                target=float(row.close) * TARGET_FRACTION,
                reward_risk=2.0,
                score=float(row.close),
                features={"lookback": float(self.params["lookback"])},
                notes=f"regime={regime}",
            )
            for row in last.itertuples()
        ]


class FakeProvider(BarProvider):
    name = "fake_provider"

    def __init__(self, settings: Any = None, secrets: Any = None):
        self.settings = settings

    def list_symbols(self, include_delisted: bool = True) -> pd.DataFrame:
        return pd.DataFrame({"symbol": list(SYMBOLS)})

    def daily_bars(self, symbols: Any, start: date, end: date) -> pd.DataFrame:
        return make_panel()


class FakeBroker(Broker):
    name = "fake_broker"
    submitted: list[OrderIntent] = []

    def account(self) -> dict[str, Any]:
        return {"equity": EQUITY}

    def positions(self) -> list[Position]:
        return []

    def submit(self, intent: OrderIntent) -> dict[str, Any]:
        FakeBroker.submitted.append(intent)
        return {"status": "accepted", "id": f"ord-{intent.client_order_id}"}

    def open_orders(self) -> list[dict[str, Any]]:
        return []

    def cancel(self, order_id: str) -> None:
        return None


class FakeLimitState:
    def __init__(self, risk: Any = None, **_: Any):
        self.risk = risk


class FakeOrderManager:
    calls: list[tuple[OrderIntent, str]] = []

    def __init__(self, broker: Any, limits: Any, killswitch_path: str):
        self.broker = broker
        self.limits = limits
        self.killswitch_path = killswitch_path

    def submit(self, intent: OrderIntent, approved_by: str) -> dict[str, Any]:
        FakeOrderManager.calls.append((intent, approved_by))
        return self.broker.submit(intent)

    def reconcile(self) -> dict[str, Any]:
        return {"open_orders": 0}


class FakeRanker:
    def predict(self, panel_as_of: pd.DataFrame) -> pd.Series:
        return pd.Series(panel_as_of["close"].to_numpy(), index=panel_as_of.index)


class FakeBacktestResult:
    def __init__(self) -> None:
        self.equity_curve = pd.DataFrame({"equity": [100.0, 101.0, 100.5, 102.0, 103.0]})


def fake_size_signal(signal: Signal, equity: float, risk_cfg: Any, open_positions: Any, sector_map: Any = None):
    risk_dollars = equity * risk_cfg.risk_per_trade_pct / 100.0
    qty = int(risk_dollars / signal.risk_per_share())
    return OrderIntent(
        symbol=signal.symbol,
        side=signal.side,
        qty=qty,
        entry_limit=signal.entry,
        stop=signal.stop,
        target=signal.target,
        strategy=signal.strategy,
        client_order_id=f"{signal.strategy}-{signal.symbol}-{signal.as_of}",
        risk_dollars=risk_dollars,
    )


def make_signal(symbol: str, close: float, strategy: str = "fake_strat") -> Signal:
    return Signal(
        strategy=strategy,
        symbol=symbol,
        as_of=AS_OF_DATE,
        entry=close,
        stop=close * STOP_FRACTION,
        target=close * TARGET_FRACTION,
        reward_risk=2.0,
        score=close,
    )


def make_review(symbol: str, decision: ReviewDecision) -> Review:
    return Review(
        symbol=symbol,
        strategy="fake_strat",
        thesis="thesis",
        catalyst_within_hold_window=False,
        news_contradicts_setup=False,
        liquidity_concern=False,
        decision=decision,
    )


# ----------------------------------------------------------------------------------------------------------
# fixtures
# ----------------------------------------------------------------------------------------------------------
def fake_module(monkeypatch: pytest.MonkeyPatch, name: str, **attrs: Any) -> types.ModuleType:
    """Install a fake `swing_engine.<name>` module so cli's lazy imports resolve to it."""
    full = f"swing_engine.{name}"
    mod = types.ModuleType(full)
    for key, value in attrs.items():
        setattr(mod, key, value)
    monkeypatch.setitem(sys.modules, full, mod)
    return mod


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Settings pointing every path into tmp; no secrets; registry discovery disabled (hermetic)."""
    store = tmp_path / "data" / "swing.duckdb"
    settings = {
        "data": {"store_path": str(store), "bar_provider": "fake_provider", "history_years": 1},
        "risk": {"kill_switch_file": str(tmp_path / "state" / "KILL"), "risk_per_trade_pct": 1.0},
        "strategies": {"fake_strat": {"enabled": True, "params": {"lookback": 3}}},
    }
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(yaml.safe_dump(settings))
    monkeypatch.setenv("SWING_SETTINGS", str(settings_file))
    load_settings.cache_clear()
    for field in Secrets.model_fields:
        monkeypatch.delenv(field.upper(), raising=False)
    monkeypatch.setattr(cli, "load_secrets", lambda: Secrets(_env_file=None))
    monkeypatch.setattr(registry, "_DISCOVERED", True)
    for kind in registry._REGISTRY:
        monkeypatch.setattr(registry, "_REGISTRY", {**registry._REGISTRY, kind: dict(registry._REGISTRY[kind])})
    monkeypatch.setitem(registry._REGISTRY["strategy"], FakeStrategy.name, FakeStrategy)
    monkeypatch.setitem(registry._REGISTRY["bar_provider"], FakeProvider.name, FakeProvider)
    monkeypatch.setitem(registry._REGISTRY["broker"], FakeBroker.name, FakeBroker)
    FakeStore.instances.clear()
    FakeBroker.submitted.clear()
    FakeOrderManager.calls.clear()
    return tmp_path


@pytest.fixture
def store_file(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An existing store path backed by FakeStore (with a cached panel table)."""
    path = workdir / "data" / "swing.duckdb"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    fake_module(monkeypatch, "data.store", Store=FakeStore)
    return path


def run_file(workdir: Path, kind: str) -> Path:
    return workdir / "data" / cli.RUNS_DIRNAME / kind / f"{AS_OF}.json"


def write_models(path: Path, items: list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([m.model_dump(mode="json") for m in items]))


# ----------------------------------------------------------------------------------------------------------
# help / version / unit helpers
# ----------------------------------------------------------------------------------------------------------
TOP_LEVEL = [
    "status", "ingest", "universe", "features", "scan", "backtest", "rank", "review", "size", "paper",
    "monitor", "journal", "trials",
]  # fmt: skip


def test_help_lists_every_command() -> None:
    result = runner.invoke(cli.app, ["--help"])
    assert result.exit_code == 0, result.output
    for name in TOP_LEVEL:
        assert name in result.output


@pytest.mark.parametrize(
    "args",
    [[c] for c in TOP_LEVEL] + [["rank", "train"], ["rank", "predict"], ["monitor", "run"], ["monitor", "report"], ["monitor", "replay"]],
)
def test_every_command_has_help(args: list[str]) -> None:
    result = runner.invoke(cli.app, [*args, "--help"])
    assert result.exit_code == 0, result.output
    assert "Usage" in result.output


def test_version_and_no_args() -> None:
    assert "swing-engine" in runner.invoke(cli.app, ["--version"]).output
    result = runner.invoke(cli.app, [])
    assert result.exit_code == cli.EXIT_USAGE
    assert "Usage" in result.output


def test_parse_params_coerces_json_values() -> None:
    parsed = cli._parse_params(["lookback=20", "atr_mult=2.5", "flag=true", "name=abc", "grid=[1,2]"])
    assert parsed == {"lookback": 20, "atr_mult": 2.5, "flag": True, "name": "abc", "grid": [1, 2]}
    with pytest.raises(Exception, match="key=value"):
        cli._parse_params(["novalue"])


def test_split_list_accepts_repeats_and_commas() -> None:
    assert cli._split_list(["a", "b,c", " d "]) == ["a", "b", "c", "d"]
    assert cli._split_list(None) is None
    assert cli._split_list([""]) is None


def test_parse_date_rejects_garbage() -> None:
    assert cli._parse_date(AS_OF) == AS_OF_DATE
    assert cli._parse_date(None, AS_OF_DATE) == AS_OF_DATE
    with pytest.raises(Exception, match="ISO date"):
        cli._parse_date("yesterday")


# ----------------------------------------------------------------------------------------------------------
# status
# ----------------------------------------------------------------------------------------------------------
def test_status_without_store_or_keys(workdir: Path) -> None:
    result = runner.invoke(cli.app, ["status"])
    assert result.exit_code == 0, result.output
    assert "MASSIVE_API_KEY" in result.output and "missing" in result.output
    assert "store exists" in result.output and "False" in result.output
    assert "clear" in result.output  # kill switch
    assert "fake_strat" in result.output  # registered strategy
    assert "fake_provider" in result.output


def test_status_shows_set_keys_without_printing_them(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "load_secrets", lambda: Secrets(_env_file=None, massive_api_key="sk-very-secret"))
    result = runner.invoke(cli.app, ["status"])
    assert result.exit_code == 0, result.output
    assert "set" in result.output
    assert "sk-very-secret" not in result.output


def test_status_counts_rows_from_duckdb_and_flags_kill_switch(workdir: Path) -> None:
    store = workdir / "data" / "swing.duckdb"
    store.parent.mkdir(parents=True)
    con = duckdb.connect(str(store))
    con.execute("create table bars(symbol varchar, ts timestamp, close double)")
    con.execute("insert into bars values ('AAA', '2026-10-01', 1.0), ('AAA', '2026-10-02', 1.1), ('BBB', '2026-10-02', 2.0)")
    con.close()
    kill = workdir / "state" / "KILL"
    kill.parent.mkdir()
    kill.touch()
    result = runner.invoke(cli.app, ["status"])
    assert result.exit_code == 0, result.output
    assert "rows[bars]" in result.output and "3" in result.output
    assert "bars.symbols" in result.output and "2" in result.output
    assert "TRIPPED" in result.output


# ----------------------------------------------------------------------------------------------------------
# missing modules
# ----------------------------------------------------------------------------------------------------------
def test_missing_module_gives_clear_error(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "swing_engine.data.ingest", None)
    result = runner.invoke(cli.app, ["ingest", "--start", "2026-09-01", "--end", AS_OF])
    assert result.exit_code == cli.EXIT_MISSING_MODULE
    assert "swing_engine.data.ingest" in result.output


def test_missing_attribute_gives_clear_error(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module(monkeypatch, "monitor.report")  # module exists, `report` does not
    result = runner.invoke(cli.app, ["monitor", "report"])
    assert result.exit_code == cli.EXIT_MISSING_MODULE
    assert "report" in result.output and "api-contract" in result.output


# ----------------------------------------------------------------------------------------------------------
# ingest / universe / features
# ----------------------------------------------------------------------------------------------------------
def test_ingest_calls_run_ingest_with_dates_and_store(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def run_ingest(settings, secrets, provider_name, symbols, start, end, store):
        seen.update(provider=provider_name, symbols=symbols, start=start, end=end, store=store)
        return {"rows": 10, "symbols": 2, "elapsed_s": 0.1}

    fake_module(monkeypatch, "data.ingest", run_ingest=run_ingest)
    fake_module(monkeypatch, "data.store", Store=FakeStore)
    args = ["ingest", "--provider", "sample", "--start", "2026-09-01", "--end", AS_OF, "-s", "AAA,BBB"]
    result = runner.invoke(cli.app, args)
    assert result.exit_code == 0, result.output
    assert seen["provider"] == "sample"
    assert seen["symbols"] == ["AAA", "BBB"]
    assert (seen["start"], seen["end"]) == (date(2026, 9, 1), AS_OF_DATE)
    assert isinstance(seen["store"], FakeStore)
    assert "rows" in result.output and "10" in result.output


@pytest.mark.parametrize(("flag", "expected"), [("auto", "auto"), ("grouped", "grouped"), ("per-symbol", "symbols")])
def test_ingest_passes_mode_and_progress(
    workdir: Path, monkeypatch: pytest.MonkeyPatch, flag: str, expected: str
) -> None:
    seen: dict[str, Any] = {}

    def run_ingest(settings, secrets, provider_name, symbols, start, end, store, *, full=False, mode="auto",
                   progress=None):
        seen.update(mode=mode, full=full)
        progress("estimate: 3 sessions")
        return {"rows": 1}

    fake_module(monkeypatch, "data.ingest", run_ingest=run_ingest)
    fake_module(monkeypatch, "data.store", Store=FakeStore)
    result = runner.invoke(cli.app, ["ingest", "--provider", "sample", "--end", AS_OF, "--mode", flag])
    assert result.exit_code == 0, result.output
    assert seen == {"mode": expected, "full": False}
    assert "estimate: 3 sessions" in result.output


def test_ingest_rejects_unknown_mode_and_reports_mode_errors(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def run_ingest(settings, secrets, provider_name, symbols, start, end, store, *, mode="auto"):
        raise ValueError("mode='grouped' ingests every US ticker per session; drop the symbol list")

    fake_module(monkeypatch, "data.ingest", run_ingest=run_ingest)
    fake_module(monkeypatch, "data.store", Store=FakeStore)
    bad = runner.invoke(cli.app, ["ingest", "--provider", "sample", "--mode", "bogus"])
    assert bad.exit_code == cli.EXIT_USAGE
    assert "per-symbol" in bad.output
    clash = runner.invoke(cli.app, ["ingest", "--provider", "sample", "--mode", "grouped", "-s", "AAA"])
    assert clash.exit_code == cli.EXIT_USAGE
    assert "drop the symbol list" in clash.output


class _FakeRating:
    def __init__(self, ok: bool, event_id: str, rating: str, reason: str | None = None) -> None:
        self.ok, self.event_id, self.rating, self.reason = ok, event_id, rating, reason

    def summary(self) -> str:
        return f"rated {self.event_id} {self.rating}" if self.ok else f"not rated: {self.event_id} ({self.reason})"


def test_monitor_rate_calls_rate_cli(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, str]] = []

    def rate_cli(settings, event_id, rating):
        if rating not in ("useful", "noise", "traded"):
            raise ValueError(f"rating must be useful|noise|traded, got {rating!r}")
        seen.append((event_id, rating))
        if event_id == "missing":
            return _FakeRating(False, event_id, rating, "unknown_event")
        return _FakeRating(True, event_id, rating)

    fake_module(monkeypatch, "monitor.rate", rate_cli=rate_cli)
    ok = runner.invoke(cli.app, ["monitor", "rate", "ev-1", "traded"])
    assert ok.exit_code == 0, ok.output
    assert "rated ev-1 traded" in ok.output
    missing = runner.invoke(cli.app, ["monitor", "rate", "missing", "useful"])
    assert missing.exit_code == cli.EXIT_NO_DATA
    assert "unknown_event" in missing.output
    bad = runner.invoke(cli.app, ["monitor", "rate", "ev-1", "great"])
    assert bad.exit_code == cli.EXIT_USAGE
    assert seen == [("ev-1", "traded"), ("missing", "useful")]


def test_universe_prints_count(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def build_universe(provider, settings, as_of):
        assert isinstance(provider, FakeProvider) and as_of == AS_OF_DATE
        return ["AAA", "BBB", "CCC"]

    fake_module(monkeypatch, "data.universe", build_universe=build_universe)
    result = runner.invoke(cli.app, ["universe", "--as-of", AS_OF])
    assert result.exit_code == 0, result.output
    assert "symbols" in result.output and "3" in result.output and "CCC" in result.output


def test_features_builds_panel_and_caches_table(store_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def build_panel(bars, market=None):
        out = bars.copy()
        out["sma_10"] = out["close"]
        return out

    fake_module(monkeypatch, "features.panel", build_panel=build_panel)
    result = runner.invoke(cli.app, ["features", "--end", AS_OF])
    assert result.exit_code == 0, result.output
    store = FakeStore.instances[-1]
    assert ("write_table", (cli.PANEL_TABLE, cli.PANEL_KEYS)) in store.calls
    assert "sma_10" in store.tables[cli.PANEL_TABLE].columns
    assert "Feature panel cached" in result.output


def test_features_without_store_exits_no_data(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module(monkeypatch, "data.store", Store=FakeStore)
    result = runner.invoke(cli.app, ["features"])
    assert result.exit_code == cli.EXIT_NO_DATA
    assert "swing ingest" in result.output


# ----------------------------------------------------------------------------------------------------------
# scan
# ----------------------------------------------------------------------------------------------------------
def test_scan_prints_signals_sorted_and_saves(store_file: Path, workdir: Path) -> None:
    result = runner.invoke(cli.app, ["scan", "--as-of", AS_OF])
    assert result.exit_code == 0, result.output
    assert "AAA" in result.output and "BBB" in result.output
    assert result.output.index("BBB") < result.output.index("AAA")  # higher score first
    saved = json.loads(run_file(workdir, "signals").read_text())
    assert [s["symbol"] for s in saved] == ["BBB", "AAA"]
    assert saved[0]["features"]["lookback"] == 3.0  # params from settings.yaml, not defaults


def test_scan_builds_panel_when_table_missing(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (workdir / "data").mkdir(parents=True)
    (workdir / "data" / "swing.duckdb").touch()
    fake_module(monkeypatch, "data.store", Store=FakeStoreNoPanel)
    built: list[int] = []

    def build_panel(bars, market=None):
        built.append(len(bars))
        return bars

    fake_module(monkeypatch, "features.panel", build_panel=build_panel)
    result = runner.invoke(cli.app, ["scan", "--as-of", AS_OF, "--no-save"])
    assert result.exit_code == 0, result.output
    assert built == [len(make_panel())]
    assert not run_file(workdir, "signals").exists()


def test_scan_unknown_strategy_is_usage_error(store_file: Path) -> None:
    result = runner.invoke(cli.app, ["scan", "--as-of", AS_OF, "-s", "nope"])
    assert result.exit_code == cli.EXIT_USAGE
    assert "nope" in result.output and "fake_strat" in result.output


# ----------------------------------------------------------------------------------------------------------
# backtest / trials / rank
# ----------------------------------------------------------------------------------------------------------
def test_backtest_logs_trial_and_prints_deflated_sharpe(store_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    class CostModel:
        def __init__(self, bps_per_side: float = 10.0):
            self.bps_per_side = bps_per_side

    def run_backtest(strategy, panel, start, end, risk_cfg, costs, market=None):
        seen.update(params=dict(strategy.params), start=start, end=end, costs=costs.bps_per_side, rows=len(panel))
        return FakeBacktestResult()

    def summarize(result):
        return {"trades": 12, "win_rate": 0.5, "sharpe": 1.2, "max_dd": -0.1}

    def deflated_sharpe(sharpe, n_trials, n_obs, skew, kurt):
        seen.update(dsr_args=(sharpe, n_trials, n_obs))
        return 0.4321

    def log_trial(name, params, metrics, path=cli.TRIALS_PATH):
        seen.update(logged=(name, params, metrics["sharpe"]))

    fake_module(monkeypatch, "research.backtest", CostModel=CostModel, run_backtest=run_backtest)
    fake_module(monkeypatch, "research.metrics", summarize=summarize, deflated_sharpe=deflated_sharpe)
    fake_module(monkeypatch, "research.trials", log_trial=log_trial, trial_count=lambda name=None: 7 if name else 9)
    args = ["backtest", "fake_strat", "--start", "2026-09-29", "--end", AS_OF, "-P", "lookback=7", "--cost", "bps_per_side=20"]
    result = runner.invoke(cli.app, args)
    assert result.exit_code == 0, result.output
    assert seen["params"] == {"lookback": 7}
    assert seen["costs"] == 20
    assert seen["logged"] == ("fake_strat", {"lookback": 7}, 1.2)
    assert seen["dsr_args"][:2] == (1.2, 9) and seen["dsr_args"][2] > 0  # deflated by all trials
    assert "deflated sharpe" in result.output and "0.4321" in result.output
    assert "trials logged for this strategy" in result.output and "7" in result.output
    assert "9" in result.output  # total trials


def test_backtest_passes_the_production_sizer_and_universe_gate(store_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def run_backtest(strategy, panel, start, end, risk_cfg, costs, market=None, sizer=None, universe_at=None):
        seen.update(sizer=sizer, universe_at=universe_at)
        return FakeBacktestResult()

    fake_module(monkeypatch, "research.backtest", CostModel=lambda **kw: object(), run_backtest=run_backtest)
    fake_module(monkeypatch, "research.metrics", summarize=lambda r: {"sharpe": 0.5}, deflated_sharpe=lambda *a: 0.1)
    fake_module(monkeypatch, "research.trials", log_trial=lambda n, p, m, **k: None, trial_count=lambda n=None: 0)
    result = runner.invoke(cli.app, ["backtest", "fake_strat", "--start", "2026-09-29", "--end", AS_OF, "--no-log"])
    assert result.exit_code == 0, result.output
    assert cli.PRODUCTION_SIZER in result.output
    sizer = seen["sizer"]
    risk = load_settings(None).risk
    assert sizer(make_signal("AAA", 10.0), EQUITY, risk, []).qty > 0  # a 2R signal is sized like `swing size`
    thin = Signal(strategy="s", symbol="AAA", as_of=AS_OF_DATE, entry=10.0, stop=9.0, target=10.5, reward_risk=0.5)
    assert sizer(thin, EQUITY, risk, []) is None  # below risk.min_reward_risk: paper would reject it, so does research
    assert seen["universe_at"] is None  # FakeStore has no symbols table, so no point-in-time screen applies


def test_month_anchors_and_membership_lookup() -> None:
    days = pd.bdate_range("2026-01-05", "2026-03-31").date
    anchors = cli._month_anchors(days, date(2026, 1, 15), date(2026, 3, 31))
    assert anchors == [date(2026, 1, 15), date(2026, 2, 2), date(2026, 3, 2)]
    assert cli._month_anchors([], date(2026, 1, 15), date(2026, 3, 31)) == [date(2026, 1, 15)]
    at = cli._membership_lookup(
        {anchors[0]: frozenset({"AAA"}), anchors[1]: frozenset({"AAA", "BBB"}), anchors[2]: frozenset({"BBB"})}
    )
    assert at(date(2026, 1, 1)) == {"AAA"}  # before the first anchor: the first screen applies
    assert at(date(2026, 1, 31)) == {"AAA"}
    assert at(date(2026, 2, 15)) == {"AAA", "BBB"}
    assert at(date(2026, 3, 2)) == {"BBB"} and at(date(2026, 12, 31)) == {"BBB"}  # AAA delisted: stays out after


def test_backtest_no_log_skips_trial(store_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    logged: list[str] = []
    fake_module(monkeypatch, "research.backtest", CostModel=lambda **kw: object(), run_backtest=lambda *a, **k: FakeBacktestResult())
    fake_module(monkeypatch, "research.metrics", summarize=lambda r: {"sharpe": 0.5}, deflated_sharpe=lambda *a: 0.1)
    fake_module(monkeypatch, "research.trials", log_trial=lambda n, p, m, **k: logged.append(n), trial_count=lambda n=None: 0)
    result = runner.invoke(cli.app, ["backtest", "fake_strat", "--start", "2026-09-29", "--end", AS_OF, "--no-log"])
    assert result.exit_code == 0, result.output
    assert logged == []


def test_trials_empty_log(workdir: Path) -> None:
    result = runner.invoke(cli.app, ["trials", "--path", str(workdir / "none.jsonl")])
    assert result.exit_code == 0, result.output
    assert "no trials logged" in result.output


def test_trials_lists_fixture_and_filters_by_name(workdir: Path) -> None:
    result = runner.invoke(cli.app, ["trials", "--path", str(FIXTURES / "trials.jsonl")])
    assert result.exit_code == 0, result.output
    assert "total 3" in result.output
    assert "pullback_trend" in result.output and "rsi2_meanrev" in result.output
    filtered = runner.invoke(cli.app, ["trials", "--path", str(FIXTURES / "trials.jsonl"), "--name", "rsi2_meanrev"])
    assert filtered.exit_code == 0
    assert "total 1" in filtered.output and "pullback_trend" not in filtered.output


def test_rank_train_then_predict(store_file: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def train_ranker(panel, horizon=10, start=None, end=None):
        seen.update(horizon=horizon, start=start, end=end, rows=len(panel))
        return FakeRanker()

    fake_module(monkeypatch, "research.ranker", train_ranker=train_ranker)
    trained = runner.invoke(cli.app, ["rank", "train", "--start", "2026-09-29", "--end", AS_OF, "--horizon", "5"])
    assert trained.exit_code == 0, trained.output
    assert seen["horizon"] == 5 and seen["rows"] > 0
    model_path = workdir / "data" / cli.RANKER_FILENAME
    assert isinstance(pickle.loads(model_path.read_bytes()), FakeRanker)
    predicted = runner.invoke(cli.app, ["rank", "predict", "--as-of", AS_OF, "--top", "1"])
    assert predicted.exit_code == 0, predicted.output
    assert "BBB" in predicted.output and "AAA" not in predicted.output


# ----------------------------------------------------------------------------------------------------------
# review
# ----------------------------------------------------------------------------------------------------------
def test_review_dry_run_uses_module_prompt_builder(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_models(run_file(workdir, "signals"), [make_signal("AAA", 10.0)])
    called: list[str] = []
    fake_module(
        monkeypatch,
        "agent.review",
        build_prompt=lambda signals, context, settings=None: f"PROMPT FOR {signals[0].symbol}",
        review_candidates=lambda *a, **k: called.append("api") or [],
    )
    result = runner.invoke(cli.app, ["review", "--as-of", AS_OF, "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "PROMPT FOR AAA" in result.output
    assert called == []


def test_review_dry_run_falls_back_to_rendering_payload(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_models(run_file(workdir, "signals"), [make_signal("AAA", 10.0)])
    fake_module(monkeypatch, "agent.review")  # no build_prompt helper
    result = runner.invoke(cli.app, ["review", "--as-of", AS_OF, "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "# SYSTEM" in result.output and "# USER" in result.output and '"AAA"' in result.output


def test_review_requires_api_key_when_not_dry_run(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_models(run_file(workdir, "signals"), [make_signal("AAA", 10.0)])
    fake_module(monkeypatch, "agent.review", review_candidates=lambda *a, **k: [])
    result = runner.invoke(cli.app, ["review", "--as-of", AS_OF])
    assert result.exit_code == cli.EXIT_USAGE
    assert "ANTHROPIC_API_KEY" in result.output


def test_review_saves_reviews(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_models(run_file(workdir, "signals"), [make_signal("AAA", 10.0), make_signal("BBB", 11.0)])
    monkeypatch.setattr(cli, "load_secrets", lambda: Secrets(_env_file=None, anthropic_api_key="k"))

    def review_candidates(signals, context_by_symbol, settings):
        return [make_review(s.symbol, ReviewDecision.APPROVE_FOR_RISK_CHECK) for s in signals]

    fake_module(monkeypatch, "agent.review", review_candidates=review_candidates)
    result = runner.invoke(cli.app, ["review", "--as-of", AS_OF, "--limit", "1"])
    assert result.exit_code == 0, result.output
    saved = json.loads(run_file(workdir, "reviews").read_text())
    assert [r["symbol"] for r in saved] == ["BBB"]  # highest score first, capped by --limit


# ----------------------------------------------------------------------------------------------------------
# size
# ----------------------------------------------------------------------------------------------------------
def test_size_filters_by_review_decision_and_writes_intents(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_models(run_file(workdir, "signals"), [make_signal("AAA", 10.0), make_signal("BBB", 20.0)])
    write_models(
        run_file(workdir, "reviews"),
        [make_review("AAA", ReviewDecision.APPROVE_FOR_RISK_CHECK), make_review("BBB", ReviewDecision.REJECT)],
    )
    fake_module(monkeypatch, "risk.sizing", size_signal=fake_size_signal)
    result = runner.invoke(cli.app, ["size", "--as-of", AS_OF, "--equity", str(EQUITY)])
    assert result.exit_code == 0, result.output
    intents = json.loads(run_file(workdir, "intents").read_text())
    assert [i["symbol"] for i in intents] == ["AAA"]
    assert intents[0]["qty"] == int(EQUITY * 0.01 / (10.0 - 10.0 * STOP_FRACTION))
    everything = runner.invoke(cli.app, ["size", "--as-of", AS_OF, "--equity", str(EQUITY), "--ignore-reviews"])
    assert everything.exit_code == 0, everything.output
    assert len(json.loads(run_file(workdir, "intents").read_text())) == 2


def test_size_reports_reasons_from_size_signal_detail(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_models(run_file(workdir, "signals"), [make_signal("AAA", 10.0), make_signal("BBB", 20.0)])

    def size_signal_detail(signal, equity, risk_cfg, open_positions, sector_map=None):
        if signal.symbol == "BBB":
            return None, "reward_risk 1.0 below min 2.0"
        return fake_size_signal(signal, equity, risk_cfg, open_positions), None

    fake_module(monkeypatch, "risk.sizing", size_signal_detail=size_signal_detail)
    result = runner.invoke(cli.app, ["size", "--as-of", AS_OF, "--equity", str(EQUITY)])
    assert result.exit_code == 0, result.output
    assert "Skipped by risk.sizing (1)" in result.output and "below min 2.0" in result.output
    assert [i["symbol"] for i in json.loads(run_file(workdir, "intents").read_text())] == ["AAA"]


def test_size_takes_equity_from_broker(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_models(run_file(workdir, "signals"), [make_signal("AAA", 10.0)])
    fake_module(monkeypatch, "risk.sizing", size_signal=fake_size_signal)
    result = runner.invoke(cli.app, ["size", "--as-of", AS_OF, "--broker", "fake_broker"])
    assert result.exit_code == 0, result.output
    assert "50,000" in result.output


def test_size_requires_equity(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_models(run_file(workdir, "signals"), [make_signal("AAA", 10.0)])
    fake_module(monkeypatch, "risk.sizing", size_signal=fake_size_signal)
    result = runner.invoke(cli.app, ["size", "--as-of", AS_OF])
    assert result.exit_code == cli.EXIT_USAGE
    assert "--equity" in result.output


# ----------------------------------------------------------------------------------------------------------
# paper
# ----------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("args", [[], ["--approve", ""], ["--approve", "  "], ["--approve", "x"]])
def test_paper_refuses_without_a_named_approver(workdir: Path, monkeypatch: pytest.MonkeyPatch, args: list[str]) -> None:
    def must_not_load(dotted: str) -> Any:
        raise AssertionError(f"paper loaded {dotted} before checking approval")

    monkeypatch.setattr(cli, "_load", must_not_load)
    result = runner.invoke(cli.app, ["paper", "--as-of", AS_OF, *args])
    assert result.exit_code == cli.EXIT_REFUSED
    assert "approve" in result.output.lower()
    assert FakeOrderManager.calls == []


def _install_execution_fakes(monkeypatch: pytest.MonkeyPatch, tripped: bool = False) -> None:
    fake_module(monkeypatch, "risk.killswitch", is_tripped=lambda path: tripped)
    fake_module(monkeypatch, "risk.limits", LimitState=FakeLimitState)
    fake_module(monkeypatch, "execution.order_manager", OrderManager=FakeOrderManager)


def test_paper_submits_with_approval_and_records_results(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    intent = fake_size_signal(make_signal("AAA", 10.0), EQUITY, load_settings(None).risk, [])
    write_models(run_file(workdir, "intents"), [intent])
    _install_execution_fakes(monkeypatch)
    result = runner.invoke(cli.app, ["paper", "--as-of", AS_OF, "--approve", "jane", "--broker", "fake_broker", "--reconcile"])
    assert result.exit_code == 0, result.output
    assert [(i.symbol, who) for i, who in FakeOrderManager.calls] == [("AAA", "jane")]
    assert FakeBroker.submitted[0].qty == intent.qty
    assert "accepted" in result.output and "open_orders" in result.output
    fills = json.loads(run_file(workdir, "fills").read_text())
    assert fills[0]["status"] == "accepted"


def test_paper_refuses_when_kill_switch_tripped(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    intent = fake_size_signal(make_signal("AAA", 10.0), EQUITY, load_settings(None).risk, [])
    write_models(run_file(workdir, "intents"), [intent])
    _install_execution_fakes(monkeypatch, tripped=True)
    result = runner.invoke(cli.app, ["paper", "--as-of", AS_OF, "--approve", "jane", "--broker", "fake_broker"])
    assert result.exit_code == cli.EXIT_REFUSED
    assert "kill switch" in result.output
    assert FakeOrderManager.calls == []


def test_paper_refuses_live_alpaca_without_override(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "load_secrets", lambda: Secrets(_env_file=None, alpaca_paper=False))
    monkeypatch.delenv(cli.LIVE_OVERRIDE_ENV, raising=False)
    result = runner.invoke(cli.app, ["paper", "--as-of", AS_OF, "--approve", "jane"])
    assert result.exit_code == cli.EXIT_REFUSED
    assert "ALPACA_PAPER" in result.output


def test_paper_executes_the_staged_plan_instead_of_the_unfiltered_intents(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A live account's staged plan (vetoes + cap applied, exits included) is what `--approve` must send."""
    from types import SimpleNamespace

    every = [fake_size_signal(make_signal(s, 10.0), EQUITY, load_settings(None).risk, []) for s in ("AAA", "REJ")]
    write_models(run_file(workdir, "intents"), every)  # the unfiltered sized set
    run_file(workdir, "pending").parent.mkdir(parents=True, exist_ok=True)
    run_file(workdir, "pending").write_text("{}")
    seen: dict[str, Any] = {}

    def load_pending(settings: Any, day: Any) -> Any:
        return [every[0]], []

    def run_pending(settings: Any, secrets: Any, day: Any, broker: Any, approver: str) -> Any:
        seen.update(day=day, approver=approver, broker=broker.name)
        entry = SimpleNamespace(model_dump=lambda mode: {"kind": "entry", "symbol": "AAA", "status": "submitted"})
        return SimpleNamespace(mode=SimpleNamespace(value="approved"), exits=[], entries=[entry], errors=[])

    _install_execution_fakes(monkeypatch)
    fake_module(monkeypatch, "execution.autopilot", load_pending=load_pending, run_pending=run_pending)
    result = runner.invoke(cli.app, ["paper", "--as-of", AS_OF, "--approve", "jane", "--broker", "fake_broker"])
    assert result.exit_code == 0, result.output
    assert seen == {"day": AS_OF_DATE, "approver": "jane", "broker": "fake_broker"}
    assert FakeOrderManager.calls == []  # the intents file was not submitted
    assert json.loads(run_file(workdir, "fills").read_text()) == [{"kind": "entry", "symbol": "AAA", "status": "submitted"}]
    forced = runner.invoke(cli.app, ["paper", "--as-of", AS_OF, "--approve", "jane", "--broker", "fake_broker",
                                     "--from-intents"])
    assert forced.exit_code == 0, forced.output
    assert [i.symbol for i, _ in FakeOrderManager.calls] == ["AAA", "REJ"]


def test_paper_without_intents_exits_no_data(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = runner.invoke(cli.app, ["paper", "--as-of", AS_OF, "--approve", "jane", "--broker", "fake_broker"])
    assert result.exit_code == cli.EXIT_NO_DATA
    assert "swing size" in result.output


# ----------------------------------------------------------------------------------------------------------
# monitor / journal
# ----------------------------------------------------------------------------------------------------------
def test_monitor_run_passes_dry_run_and_feeds(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[dict[str, Any]] = []

    async def run_monitor(settings, secrets, dry_run=False, feeds=None):
        seen.append({"dry_run": dry_run, "feeds": feeds})

    fake_module(monkeypatch, "monitor.service", run_monitor=run_monitor)
    assert runner.invoke(cli.app, ["monitor", "run", "--dry-run", "-f", "edgar,nasdaq_halts"]).exit_code == 0
    assert runner.invoke(cli.app, ["monitor", "--dry-run"]).exit_code == 0  # README shorthand
    assert seen == [{"dry_run": True, "feeds": ["edgar", "nasdaq_halts"]}, {"dry_run": True, "feeds": None}]


def test_monitor_report_and_replay_print_results(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module(monkeypatch, "monitor.report", report=lambda days: {"days": days, "alerts": 4, "duplicate_rate": 0.1})
    fake_module(monkeypatch, "monitor.replay", replay=lambda days, rules: pd.DataFrame({"rule": ["halts_luld"], "hits": [days]}))
    report = runner.invoke(cli.app, ["monitor", "report", "--days", "3"])
    assert report.exit_code == 0, report.output
    assert "duplicate_rate" in report.output and "3" in report.output
    replay = runner.invoke(cli.app, ["monitor", "replay", "--days", "5", "-r", "halts_luld"])
    assert replay.exit_code == 0, replay.output
    assert "halts_luld" in replay.output and "5" in replay.output


def test_journal_passes_saved_artifacts(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_models(run_file(workdir, "signals"), [make_signal("AAA", 10.0)])
    seen: dict[str, Any] = {}

    def write_entry(day, signals, reviews, intents, fills):
        seen.update(day=day, n_signals=len(signals), reviews=reviews, intents=intents, fills=fills)
        return f"journal/{day}.md"

    fake_module(monkeypatch, "agent.journal", write_entry=write_entry)
    result = runner.invoke(cli.app, ["journal", "--as-of", AS_OF])
    assert result.exit_code == 0, result.output
    assert seen == {"day": AS_OF_DATE, "n_signals": 1, "reviews": [], "intents": [], "fills": []}
    assert f"journal/{AS_OF}.md" in result.output


def test_journal_disables_narrative_without_api_key(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def write_entry(day, signals, reviews, intents, fills, *, settings=None, narrative=True):
        seen.update(narrative=narrative, has_settings=settings is not None)
        return "ok"

    fake_module(monkeypatch, "agent.journal", write_entry=write_entry)
    assert runner.invoke(cli.app, ["journal", "--as-of", AS_OF]).exit_code == 0
    assert seen == {"narrative": False, "has_settings": True}
    monkeypatch.setattr(cli, "load_secrets", lambda: Secrets(_env_file=None, anthropic_api_key="k"))
    assert runner.invoke(cli.app, ["journal", "--as-of", AS_OF]).exit_code == 0
    assert seen["narrative"] is True


def test_size_never_reads_numbers_from_reviews(workdir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Hard rule: a Review may only gate a Signal; the intent's numbers must come from the Signal + risk code."""
    signal = make_signal("AAA", 10.0)
    write_models(run_file(workdir, "signals"), [signal])
    review = make_review("AAA", ReviewDecision.APPROVE_FOR_RISK_CHECK)
    review.rubric_scores = {"target": 999, "stop": 1, "qty": 12345}
    write_models(run_file(workdir, "reviews"), [review])
    fake_module(monkeypatch, "risk.sizing", size_signal=fake_size_signal)
    result = runner.invoke(cli.app, ["size", "--as-of", AS_OF, "--equity", str(EQUITY)])
    assert result.exit_code == 0, result.output
    intent = json.loads(run_file(workdir, "intents").read_text())[0]
    assert intent["stop"] == signal.stop and intent["target"] == signal.target
    assert intent["qty"] == int(EQUITY * 0.01 / signal.risk_per_share())
    assert intent["side"] == Side.LONG.value


def test_dashboard_passes_settings_and_flags(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import swing_engine.dashboard as dash

    seen: dict[str, Any] = {}
    monkeypatch.setattr(dash, "serve", lambda **kw: seen.update(kw))
    settings = tmp_path / "s.yaml"
    settings.write_text("{}\n")
    result = runner.invoke(cli.app, ["--settings", str(settings), "dashboard", "--port", "8801", "--demo"])
    assert result.exit_code == 0, result.output
    assert seen == {"settings_path": str(settings), "port": 8801, "demo": True, "open_browser": False}
