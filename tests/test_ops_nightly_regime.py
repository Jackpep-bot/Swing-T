"""ops.nightly wiring of the regime contract: the liquidity-screened panel and breadth table (features), market
state -> playbook routing (scan), per-strategy risk multipliers (size, run_cycle) and the shadow ledger step.
The breadth / playbook / shadow modules are stubbed through `nightly.contract_fn` (tests/test_ops_nightly.py);
one test at the end runs the real modules when they import. No network; every file lives under tmp_path."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from swing_engine.core.config import Settings
from swing_engine.core.models import Position, Side, Signal
from swing_engine.data._common import normalize_symbols
from swing_engine.data.store import Store
from swing_engine.ops import nightly
from swing_engine.ops.nightly import StepStatus, run_cycle, run_nightly
from tests import test_ops_nightly as nightly_tests
from tests.test_ops_nightly import (
    AS_OF,
    EQUITY,
    ORIGINAL_CONTRACT_FN,
    ContractStubs,
    install_contract,
    make_settings,
    no_secrets,
    run_file,
)

contract = nightly_tests.contract  # the autouse contract-stub fixture, re-exported so it applies here too

SESSIONS = 320  # > 200 sessions so sma_200 warms up; covers the 20-session liquidity window
LIQUID_VOLUME = 2_000_000.0
ILLIQUID_VOLUME = 1_000.0


# ----------------------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------------------
def synthetic_bars(spec: dict[str, tuple[float, float]], end: date = AS_OF, sessions: int = SESSIONS) -> pd.DataFrame:
    """Deterministic random-walk daily bars: symbol -> (start price, daily volume)."""
    ts = pd.bdate_range(end=pd.Timestamp(end), periods=sessions).tz_localize("America/New_York")
    rng = np.random.default_rng(7)
    frames = []
    for symbol, (price, volume) in spec.items():
        close = price * np.exp(np.cumsum(rng.normal(0.0005, 0.01, len(ts))))
        frames.append(pd.DataFrame({
            "symbol": symbol, "ts": ts, "open": close * 0.998, "high": close * 1.01, "low": close * 0.99,
            "close": close, "volume": volume, "vwap": close, "adj_close": close,
        }))  # fmt: skip
    return pd.concat(frames, ignore_index=True)


def reference(rows: dict[str, str]) -> pd.DataFrame:
    return normalize_symbols(pd.DataFrame([
        {"symbol": s, "name": s, "exchange": "XNAS", "type": kind, "active": True} for s, kind in rows.items()
    ]))  # fmt: skip


def make_ctx(settings: Settings, store: Any, *, broker: Any = None, equity: float | None = None,
             dry_run: bool = True) -> nightly._Context:
    report = nightly.NightlyReport(as_of=AS_OF, provider="sample", dry_run=dry_run, started_at=datetime.now(UTC))
    return nightly._Context(
        settings=settings, secrets=no_secrets(), as_of=AS_OF, provider="sample", equity=equity, dry_run=dry_run,
        store=store, broker=broker, review_client=None, journal_client=None, journal_root=None, report=report,
    )  # fmt: skip


class HoldingBroker:
    def __init__(self, held: str, ordered: str) -> None:
        self.held, self.ordered = held, ordered

    def account(self) -> dict[str, Any]:
        return {"equity": EQUITY}

    def positions(self) -> list[Position]:
        return [Position(symbol=self.held, qty=10, avg_entry=10.0, side=Side.LONG)]

    def open_orders(self) -> list[dict[str, Any]]:
        return [{"symbol": self.ordered, "status": "new"}]


SPEC = {
    "LIQA": (50.0, LIQUID_VOLUME), "LIQB": (80.0, LIQUID_VOLUME), "ILLQ": (20.0, ILLIQUID_VOLUME),
    "HELD": (20.0, ILLIQUID_VOLUME), "ORDR": (20.0, ILLIQUID_VOLUME),
    "SPY": (500.0, LIQUID_VOLUME), "QQQ": (400.0, LIQUID_VOLUME),
}  # fmt: skip
TYPES = {"LIQA": "CS", "LIQB": "CS", "ILLQ": "CS", "HELD": "CS", "ORDR": "CS", "SPY": "ETF", "QQQ": "ETF"}


def screened_settings(tmp_path: Path) -> Settings:
    settings = make_settings(tmp_path)
    settings.universe.static_symbols = []  # screen the store instead of the test's static list
    return settings


# ----------------------------------------------------------------------------------------------------------
# features: screened panel + breadth
# ----------------------------------------------------------------------------------------------------------
def test_features_builds_the_panel_only_for_screened_index_and_held_symbols(
    tmp_path: Path, contract: ContractStubs
) -> None:
    settings = screened_settings(tmp_path)
    with Store(":memory:") as store:
        store.write_bars(synthetic_bars(SPEC))
        store.write_table("symbols", reference(TYPES), ["symbol"])
        ctx = make_ctx(settings, store, broker=HoldingBroker(held="HELD", ordered="ORDR"))
        detail, data = nightly._step_features(ctx)

        assert ctx.universe == ["LIQA", "LIQB"]  # ETFs fail the type filter, ILLQ/HELD/ORDR the liquidity screen
        assert set(ctx.panel["symbol"].unique()) == {"LIQA", "LIQB", "SPY", "QQQ", "HELD", "ORDR"}
        assert data["universe_how"] == "build_universe" and data["screened"] == 2 and data["store_symbols"] == len(SPEC)
        assert data["held"] == ["HELD", "ORDR"] and "2 screened via build_universe of 7" in detail
        per_symbol = ctx.panel.groupby("symbol").size()
        assert (per_symbol == SESSIONS).all()  # full history for every kept symbol
        # breadth runs on the screened names only and lands in the 'breadth' table, one row per session
        assert contract.calls["market_breadth"][0]["symbols"] == ["LIQA", "LIQB"]
        breadth = store.read_table(nightly.BREADTH_TABLE)
        assert len(breadth) == 1 and set(breadth["n_symbols"]) == {2}  # first run: no survivor-only backfill
        assert pd.to_datetime(breadth[nightly.BREADTH_KEY]).max().date() == AS_OF


class FlakyPositionsBroker(HoldingBroker):
    def positions(self) -> list[Position]:
        raise ConnectionError("alpaca timed out")


def test_features_keeps_every_symbol_when_the_broker_holdings_are_unknown(tmp_path: Path) -> None:
    """A held name outside today's screen must keep its panel rows (time stop, rule exit, trail) even when the
    broker call fails during features: the ledger cannot say it is held (FILLED is terminal)."""
    settings = screened_settings(tmp_path)
    with Store(":memory:") as store:
        store.write_bars(synthetic_bars(SPEC))
        store.write_table("symbols", reference(TYPES), ["symbol"])
        ctx = make_ctx(settings, store, broker=FlakyPositionsBroker(held="HELD", ordered="ORDR"))
        detail, data = nightly._step_features(ctx)
    assert ctx.universe == ["LIQA", "LIQB"] and data["held_fetch_failed"] == ["positions"]
    assert set(ctx.panel["symbol"].unique()) == set(SPEC)  # HELD (illiquid, unreported) is still in the panel
    assert "not restricted" in detail


def test_features_falls_back_to_a_liquidity_screen_without_a_symbols_table(tmp_path: Path) -> None:
    settings = screened_settings(tmp_path)
    with Store(":memory:") as store:
        store.write_bars(synthetic_bars(SPEC))
        ctx = make_ctx(settings, store)
        _detail, data = nightly._step_features(ctx)
    assert data["universe_how"].startswith("liquidity screen")
    assert ctx.universe == ["LIQA", "LIQB", "QQQ", "SPY"]  # no reference types: liquidity alone decides
    assert set(ctx.panel["symbol"].unique()) == {"LIQA", "LIQB", "QQQ", "SPY"} and data["held"] == []


def test_breadth_keeps_earlier_sessions_and_rewrites_only_from_the_last_stored_one(tmp_path: Path) -> None:
    settings = screened_settings(tmp_path)
    days = [d.date() for d in pd.bdate_range(end=pd.Timestamp(AS_OF), periods=3)]
    with Store(":memory:") as store:
        store.write_bars(synthetic_bars(SPEC))
        store.write_table("symbols", reference(TYPES), ["symbol"])
        for day in days[:2]:  # two nightly runs: the first writes only its own session
            ctx = make_ctx(settings, store)
            ctx.as_of = day
            nightly._step_features(ctx)
        stored = store.read_table(nightly.BREADTH_TABLE)
        assert sorted(pd.to_datetime(stored[nightly.BREADTH_KEY]).dt.date) == days[:2]
        store.sql(f"UPDATE {nightly.BREADTH_TABLE} SET pct_above_50 = -1")  # mark every stored row
        nightly._step_features(make_ctx(settings, store))  # AS_OF = days[2]
        again = store.read_table(nightly.BREADTH_TABLE).set_index(nightly.BREADTH_KEY)
    again.index = pd.to_datetime(again.index).date
    assert again.loc[days[0], "pct_above_50"] == -1  # an earlier night's value is kept
    assert again.loc[days[1], "pct_above_50"] == 60.0  # the latest stored session is recomputed
    assert again.loc[AS_OF, "pct_above_50"] == 60.0 and len(again) == 3


def test_breadth_failure_or_absence_keeps_the_features_step_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = screened_settings(tmp_path)
    for kw in ({"boom": ("market_breadth",)}, {"missing": ("market_breadth",)}):
        install_contract(monkeypatch, **kw)
        with Store(":memory:") as store:
            store.write_bars(synthetic_bars(SPEC))
            ctx = make_ctx(settings, store)
            detail, data = nightly._step_features(ctx)
            assert ctx.panel is not None and ctx.breadth is None and not store.has_table(nightly.BREADTH_TABLE)
        assert ("exploded" in data["breadth"]) if "boom" in kw else ("unavailable" in data["breadth"]), detail


# ----------------------------------------------------------------------------------------------------------
# scan: routing
# ----------------------------------------------------------------------------------------------------------
def test_correction_allows_nothing_and_saves_an_empty_signal_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_contract(monkeypatch, regime="correction", table={})
    settings = make_settings(tmp_path)
    report = run_nightly(settings, no_secrets(), AS_OF, "sample", EQUITY, True, journal_root=tmp_path)
    scan = report.step("scan")
    assert scan.status is StepStatus.OK and scan.data["signals"] == 0 and scan.data["per_strategy"] == {}
    assert scan.data["allowed"] == {} and set(scan.data["blocked"]) == set(settings.strategies)
    assert "regime correction: allowed none" in scan.detail
    assert json.loads(run_file(tmp_path, "signals").read_text()) == []  # autopilot must not size an older list
    assert report.step("size").status is StepStatus.SKIP and report.step("shadow").data["recorded"] == 0
    journal = (tmp_path / "data" / "journal" / f"{AS_OF.isoformat()}.md").read_text()
    assert "regime: **correction**" in journal and "none (no new entries)" in journal


def test_only_allowed_strategies_run_and_zero_multipliers_are_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stubs = install_contract(monkeypatch, regime="narrow_uptrend",
                             table={"pullback_trend": 0.5, "sr_bounce": 0.0, "breakout_52w": 1.0})
    settings = make_settings(tmp_path)
    report = run_nightly(settings, no_secrets(), AS_OF, "sample", EQUITY, True, journal_root=tmp_path)
    scan = report.step("scan")
    assert set(scan.data["per_strategy"]) == {"pullback_trend"}  # breakout_52w is not enabled in settings
    assert scan.data["allowed"] == {"pullback_trend": 0.5}
    assert scan.data["blocked"] == {"sr_bounce": "multiplier 0 in this regime",
                                    "rsi2_meanrev": "not in the playbook table for this regime"}
    assert stubs.calls["select_strategies"] == [{"regime": "narrow_uptrend"}]
    signals = json.loads(run_file(tmp_path, "signals").read_text())
    assert {s["strategy"] for s in signals} <= {"pullback_trend"}


def test_missing_or_broken_playbook_fails_the_scan_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_contract(monkeypatch, missing=("market_state",))
    settings = make_settings(tmp_path)
    report = run_nightly(settings, no_secrets(), AS_OF, "sample", EQUITY, True, journal_root=tmp_path)
    scan = report.step("scan")
    assert scan.status is StepStatus.FAIL and "routing unavailable" in scan.detail and "stubbed out" in scan.detail
    assert report.regime is None and not run_file(tmp_path, "regime").exists()
    assert report.step("size").status is StepStatus.SKIP  # nothing sized at full risk on an unrouted scan
    assert json.loads(run_file(tmp_path, "signals").read_text()) == []  # autopilot must not size an older list

    install_contract(monkeypatch, boom=("market_state",))
    broken = run_nightly(settings, no_secrets(), AS_OF, "sample", EQUITY, True, journal_root=tmp_path)
    assert broken.step("scan").status is StepStatus.FAIL and "market_state exploded" in broken.step("scan").detail
    assert broken.step("size").status is StepStatus.SKIP  # no signals: no new risk on a broken router


def test_state_without_select_strategies_is_saved_but_the_scan_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_contract(monkeypatch, missing=("select_strategies",))
    settings = make_settings(tmp_path)
    report = run_nightly(settings, no_secrets(), AS_OF, "sample", EQUITY, True, journal_root=tmp_path)
    saved = json.loads(run_file(tmp_path, "regime").read_text())
    assert saved["regime"] == "healthy_uptrend" and "allowed" not in saved
    assert report.step("scan").status is StepStatus.FAIL and "routing unavailable" in report.step("scan").detail
    assert report.step("size").status is StepStatus.SKIP


def test_contract_fn_reports_only_an_absent_module_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nightly, "contract_fn", ORIGINAL_CONTRACT_FN)
    fn, why = nightly.contract_fn("market_state")
    assert callable(fn) and why == ""
    monkeypatch.setitem(nightly.CONTRACT, "market_state", "strategies.no_such_playbook.market_state")
    fn, why = nightly.contract_fn("market_state")
    assert fn is None and "unavailable" in why

    real_import = nightly.importlib.import_module

    def drifted(name: str, *a: Any, **kw: Any) -> Any:
        if name == "swing_engine.strategies.playbook":  # e.g. the module's own regime-drift guard at import time
            raise RuntimeError("PLAYBOOK_REGIMES drifted")
        if name == "swing_engine.features.breadth":
            raise ModuleNotFoundError("No module named 'scipy'", name="scipy")  # a missing dependency
        return real_import(name, *a, **kw)

    monkeypatch.setattr(nightly.importlib, "import_module", drifted)
    monkeypatch.setitem(nightly.CONTRACT, "market_state", "strategies.playbook.market_state")
    with pytest.raises(RuntimeError, match="drifted"):
        nightly.contract_fn("market_state")
    with pytest.raises(ModuleNotFoundError):
        nightly.contract_fn("market_breadth")
    with pytest.raises(RuntimeError, match="drifted"):  # and compute_regime propagates it: the scan fails closed
        nightly.compute_regime(Settings(), pd.DataFrame(), AS_OF)


# ----------------------------------------------------------------------------------------------------------
# size: multipliers scale risk_per_trade_pct
# ----------------------------------------------------------------------------------------------------------
def signal(strategy: str, symbol: str, entry: float = 50.0) -> Signal:
    return Signal(strategy=strategy, symbol=symbol, as_of=AS_OF, entry=entry, stop=entry * 0.95,
                  target=entry * 1.15, reward_risk=3.0, score=1.0)


def test_size_scales_risk_by_the_strategy_multiplier_and_skips_unrouted_strategies(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, risk={"max_position_pct": 100.0})
    ctx = make_ctx(settings, store=None, equity=EQUITY)
    ctx.signals = [signal("pullback_trend", "AAA"), signal("rsi2_meanrev", "BBB"), signal("sr_bounce", "CCC")]
    ctx.risk_multipliers = {"pullback_trend": 1.0, "rsi2_meanrev": 0.25}
    _detail, data = nightly._step_size(ctx)
    by_symbol = {i.symbol: i for i in ctx.intents}
    assert set(by_symbol) == {"AAA", "BBB"}
    assert data["skipped"] == {"sr_bounce:CCC": "strategy not allowed by the playbook in this regime"}
    budget = EQUITY * settings.risk.risk_per_trade_pct / 100
    assert by_symbol["AAA"].risk_dollars <= budget and by_symbol["AAA"].risk_dollars > budget * 0.9
    assert by_symbol["BBB"].risk_dollars <= budget * 0.25 and by_symbol["BBB"].risk_dollars > budget * 0.2
    assert by_symbol["BBB"].qty == pytest.approx(by_symbol["AAA"].qty / 4, abs=1)
    assert settings.risk.risk_per_trade_pct == 1.0  # the settings object is never mutated

    ctx.risk_multipliers = None  # unrouted: full risk for everyone
    nightly._step_size(ctx)
    assert {i.symbol for i in ctx.intents} == {"AAA", "BBB", "CCC"}


def test_route_strategies_clips_multipliers_into_zero_one() -> None:
    settings = Settings.model_validate({"strategies": {"a": {"enabled": True}, "b": {"enabled": True},
                                                       "c": {"enabled": False}}})
    allowed, blocked = nightly.route_strategies(settings, {"a": 3.0, "b": -1.0, "c": 1.0})
    assert allowed == {"a": 1.0} and set(blocked) == {"b"}  # disabled 'c' is never considered


def test_run_cycle_reapplies_the_saved_multipliers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = make_settings(tmp_path)
    run_nightly(settings, no_secrets(), AS_OF, "sample", EQUITY, True, journal_root=tmp_path)
    signals = [Signal.model_validate(r) for r in json.loads(run_file(tmp_path, "signals").read_text())]
    assert signals
    keep = signals[0].strategy
    saved = json.loads(run_file(tmp_path, "regime").read_text())
    saved["allowed"] = {keep: 0.5}
    run_file(tmp_path, "regime").write_text(json.dumps(saved))

    report = run_cycle(settings, no_secrets(), AS_OF, None, True, equity=EQUITY)
    size = report.step("size")
    assert size.status is StepStatus.OK and size.data["risk_multipliers"] == {keep: 0.5}
    assert report.regime["allowed"] == {keep: 0.5} and report.files["regime_used"] == str(run_file(tmp_path, "regime"))
    others = [s for s in signals if s.strategy != keep]
    assert all(size.data["skipped"][f"{s.strategy}:{s.symbol}"].startswith("strategy not allowed") for s in others)
    budget = EQUITY * settings.risk.risk_per_trade_pct / 100 * 0.5
    intents = json.loads(run_file(tmp_path, "intents").read_text())
    assert all(i["strategy"] == keep and i["risk_dollars"] <= budget + 1e-9 for i in intents)


def test_run_cycle_refuses_to_size_signals_without_saved_routing(tmp_path: Path) -> None:
    """`swing scan` (or a nightly whose routing never saved) leaves signals with no runs/regime file: the
    autopilot must not size them at full risk; positions/exits still run."""
    settings = make_settings(tmp_path)
    run_nightly(settings, no_secrets(), AS_OF, "sample", EQUITY, True, journal_root=tmp_path)
    assert json.loads(run_file(tmp_path, "signals").read_text())
    run_file(tmp_path, "regime").unlink()
    report = run_cycle(settings, no_secrets(), AS_OF, None, True, equity=EQUITY)
    size = report.step("size")
    assert size.status is StepStatus.SKIP and "no saved playbook routing" in size.detail
    assert "regime_used" not in report.files and report.regime is None

    run_file(tmp_path, "regime").write_text(json.dumps({"regime": "choppy", "market_state": {}}))  # no 'allowed'
    again = run_cycle(settings, no_secrets(), AS_OF, None, True, equity=EQUITY)
    assert again.step("size").status is StepStatus.SKIP and "no saved playbook routing" in again.step("size").detail


# ----------------------------------------------------------------------------------------------------------
# shadow step
# ----------------------------------------------------------------------------------------------------------
def test_shadow_skips_without_the_module_and_keeps_the_pipeline_going(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_contract(monkeypatch, missing=("record_signals",))
    settings = make_settings(tmp_path)
    report = run_nightly(settings, no_secrets(), AS_OF, "sample", EQUITY, True, journal_root=tmp_path)
    shadow = report.step("shadow")
    assert shadow.status is StepStatus.SKIP and "research.shadow.record_signals unavailable" in shadow.detail
    assert report.ok and report.step("journal").status is StepStatus.OK


def test_shadow_marks_only_sized_intents_as_taken(tmp_path: Path, contract: ContractStubs) -> None:
    settings = make_settings(tmp_path)
    ctx = make_ctx(settings, store=object())
    ctx.signals = [signal("pullback_trend", "AAA"), signal("rsi2_meanrev", "AAA"), signal("sr_bounce", "BBB")]
    ctx.market_state = {"regime": "choppy"}
    ctx.intents = []
    _detail, data = nightly._step_shadow(ctx)
    assert data == {"recorded": 3, "taken": [], "graded": 0, "regime": "choppy", "signal_day": AS_OF.isoformat()}
    ctx.equity, ctx.risk_multipliers = EQUITY, {"rsi2_meanrev": 1.0}
    nightly._step_size(ctx)
    _detail, data = nightly._step_shadow(ctx)
    assert data["taken"] == ["rsi2_meanrev:AAA"]  # the pullback signal on the same name stays untaken
    assert contract.calls["record_signals"][-1]["taken"] == {"rsi2_meanrev:AAA"}


def test_pre_open_run_records_shadow_rows_under_the_bar_session(tmp_path: Path, contract: ContractStubs) -> None:
    """The 06:30 ET run has as_of = today but bars only through the previous close: rows are keyed by the bar's
    session so grading starts at the session the autopilot actually enters on."""
    run_day = date.fromordinal(AS_OF.toordinal() + 1)  # Thursday morning; the store ends Wednesday's close
    settings = screened_settings(tmp_path)
    with Store(":memory:") as store:
        store.write_bars(synthetic_bars(SPEC))
        store.write_table("symbols", reference(TYPES), ["symbol"])
        ctx = make_ctx(settings, store)
        ctx.as_of = ctx.report.as_of = run_day
        nightly._step_features(ctx)
        nightly._step_scan(ctx)
        assert ctx.signal_day == AS_OF
        ctx.signals = [Signal(strategy="pullback_trend", symbol="LIQA", as_of=run_day, entry=50.0, stop=47.5,
                              target=57.5, reward_risk=3.0, score=1.0)]
        _detail, data = nightly._step_shadow(ctx)
    recorded = contract.calls["record_signals"][-1]
    assert recorded["as_of"] == AS_OF and data["signal_day"] == AS_OF.isoformat()
    assert all(s.as_of == AS_OF for s in recorded["signals"])
    assert contract.calls["grade_signals"][-1]["as_of"] == run_day  # grading still runs through the run date


class _OneSignalStrategy:
    name = "fake_shadow"

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        self.params = params or {}

    def signals(self, panel: pd.DataFrame, as_of: date, regime: Any = None) -> list[Signal]:
        sym = sorted(panel["symbol"].unique())[0]
        return [Signal(strategy=self.name, symbol=sym, as_of=as_of, entry=50.0, stop=47.5, target=57.5,
                       reward_risk=3.0, score=9.0)]


def test_shadow_only_strategies_are_recorded_but_never_sized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, contract: ContractStubs
) -> None:
    from swing_engine.core import registry

    monkeypatch.setitem(registry._REGISTRY["strategy"], "fake_shadow", _OneSignalStrategy)
    settings = make_settings(tmp_path, strategies={"fake_shadow": {"enabled": False, "shadow_only": True}})
    assert "fake_shadow" not in nightly._enabled_strategies(settings)
    assert nightly._strategy_params(settings, "fake_shadow") == {}
    report = run_nightly(settings, no_secrets(), AS_OF, "sample", EQUITY, True, journal_root=tmp_path)
    scan = report.step("scan")
    assert scan.status is StepStatus.OK and scan.data["shadow_only"] == {"fake_shadow": 1}
    assert "fake_shadow" not in scan.data["per_strategy"] and "fake_shadow" not in (scan.data["allowed"] or {})
    saved = json.loads(run_file(tmp_path, "signals").read_text())
    intents = json.loads(run_file(tmp_path, "intents").read_text())
    assert all(s["strategy"] != "fake_shadow" for s in saved) and all(i["strategy"] != "fake_shadow" for i in intents)
    recorded = contract.calls["record_signals"][0]
    assert any(s.strategy == "fake_shadow" for s in recorded["signals"])
    assert not any(k.startswith("fake_shadow:") for k in recorded["taken"])


def test_shipped_settings_keep_the_p1_modules_out_of_execution() -> None:
    import yaml

    from swing_engine.core.config import ROOT

    settings = Settings.model_validate(yaml.safe_load((ROOT / "config" / "settings.yaml").read_text()))
    p1 = ("pullback_holy_grail", "base_breakout", "power_gap", "qullamaggie_flag", "episodic_pivot")
    enabled = set(nightly._enabled_strategies(settings))
    assert not enabled & set(p1)  # methods.md 7 / gates.md step 4: disabled until the gate is met
    assert set(p1) <= set(nightly._shadow_only_strategies(settings))


# ----------------------------------------------------------------------------------------------------------
# the real contract modules, when they import
# ----------------------------------------------------------------------------------------------------------
def test_nightly_with_the_real_breadth_playbook_and_shadow_modules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for module in ("features.breadth", "strategies.playbook", "research.shadow"):
        pytest.importorskip(f"swing_engine.{module}")
    monkeypatch.setattr(nightly, "contract_fn", ORIGINAL_CONTRACT_FN)
    settings = make_settings(tmp_path)
    if not hasattr(settings, "playbook"):
        pytest.skip("settings.playbook not wired yet")
    report = run_nightly(settings, no_secrets(), AS_OF, "sample", EQUITY, True, journal_root=tmp_path)
    assert report.ok, report.summary()
    regime = json.loads(run_file(tmp_path, "regime").read_text())
    assert regime["regime"] in {"healthy_uptrend", "narrow_uptrend", "choppy", "correction", "high_vol_selloff"}
    assert set(regime["allowed"]) | set(regime["blocked"]) == set(settings.strategies)
    shadow = report.step("shadow")
    assert shadow.status is StepStatus.OK and shadow.data["recorded"] == report.step("scan").data["signals"]
    with Store(str(tmp_path / "data" / "swing.duckdb")) as store:
        assert store.count(nightly.BREADTH_TABLE) > 0
