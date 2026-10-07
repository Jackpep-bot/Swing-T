"""Engine replay: planted edge vs zero edge, router gating and risk scaling, point-in-time truncation, determinism,
position-manager exits, the marketable-limit entry rule and the trial log."""
from __future__ import annotations

import json
import math
from datetime import date
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest

from swing_engine.core.config import ExecutionConfig, RiskConfig, Settings
from swing_engine.core.interfaces import Strategy
from swing_engine.core.models import Signal
from swing_engine.data.sample import SampleProvider
from swing_engine.data.store import Store
from swing_engine.research import replay as replay_mod
from swing_engine.research.backtest import CostModel, ExitReason
from swing_engine.research.replay import run_replay
from swing_engine.research.shadow import REPLAY_SHADOW_TABLE, SHADOW_TABLE, shadow_report
from tests.fixtures.research.strategies import RecordingStrategy, long_signal
from tests.fixtures.research.synthetic_panel import FLAG_COLUMN, make_bars, make_panel

PCT = 100.0
STOP_PCT, TARGET_PCT = 3.0, 6.0
NO_FEES = CostModel(slippage_bps=0.0, sec_fee_per_million_sold=0.0, finra_taf_per_share=0.0)


_REAL_LOAD_ROUTER = replay_mod._load_router
_REAL_LOAD_BREADTH = replay_mod._load_breadth


@pytest.fixture(autouse=True)
def _no_real_router(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate from the concurrently developed strategies.playbook / features.breadth modules."""
    monkeypatch.setattr(replay_mod, "_load_router", lambda: None)
    monkeypatch.setattr(replay_mod, "_load_breadth", lambda: None)


class ScheduleStrategy(Strategy):
    """Long at the close of every scheduled (symbol, day): fixed-percentage stop and target, 10-session hold."""

    name = "planted"
    default_params: dict[str, Any] = {"max_hold_days": 10}

    def __init__(self, schedule: set[tuple[str, date]], name: str = "planted"):
        super().__init__()
        self.name = name
        self.schedule = schedule

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        last = panel.loc[panel["ts"] == panel["ts"].max()]
        out = []
        for r in last.itertuples(index=False):
            if (r.symbol, as_of) in self.schedule and r.ts.date() == as_of:
                c = float(r.close)
                out.append(long_signal(r.symbol, as_of, c, c * (1 - STOP_PCT / PCT), c * (1 + TARGET_PCT / PCT),
                                       score=1.0, strategy=self.name))
        return out


def _settings(**risk: Any) -> Settings:
    return Settings(
        risk=RiskConfig(**{"max_open_positions": 8, **risk}),
        execution=ExecutionConfig(max_new_orders_per_day=5),
        strategies={"planted": {"enabled": True, "min_reward_risk": 0.0}},
    )


def _planted_store(edge: float, seed: int = 3) -> tuple[Store, set[tuple[str, date]], pd.DataFrame]:
    panel = make_panel(n_symbols=20, n_days=420, seed=seed, edge=edge)
    store = Store()
    store.write_bars(panel)
    flagged = panel.loc[panel[FLAG_COLUMN] == 1]
    schedule = {(str(s), t.date()) for s, t in zip(flagged["symbol"], flagged["ts"], strict=True)}
    return store, schedule, panel


def _replay(store: Store, schedule: set[tuple[str, date]], tmp_path, **kw: Any):
    return run_replay(
        kw.pop("settings", _settings()), store, "2022-06-01", "2023-08-31", strategies=[ScheduleStrategy(schedule)],
        use_router=kw.pop("use_router", False), costs=kw.pop("costs", CostModel.small_cap()),
        trials_path=tmp_path / "trials.jsonl", **kw,
    )


# ----------------------------------------------------------------------------------------------- planted edge


def test_planted_edge_is_positive_in_replay_and_shadow_and_zero_edge_is_not(tmp_path):
    store_e, sched_e, _ = _planted_store(0.08)
    store_n, sched_n, _ = _planted_store(0.0)
    edge = _replay(store_e, sched_e, tmp_path)
    noise = _replay(store_n, sched_n, tmp_path)
    se, sn = edge.summary, noise.summary
    assert se["trades"] >= 60 and sn["trades"] >= 60
    assert se["avg_r"] > 0.25 and se["total_return"] > 0
    assert sn["avg_r"] < 0.1
    assert se["avg_r"] - sn["avg_r"] > 0.3
    assert edge.by_strategy.loc["planted", "expectancy_r"] > 0.25

    rep_e = shadow_report(store_e, group_by=("strategy",), table=REPLAY_SHADOW_TABLE).iloc[0]
    rep_n = shadow_report(store_n, group_by=("strategy",), table=REPLAY_SHADOW_TABLE).iloc[0]
    assert rep_e["n"] > se["trades"]  # every signal is graded, taken or not
    assert rep_e["n_taken"] == se["n_orders"]
    assert rep_e["expectancy"] > 0.25
    assert rep_n["expectancy"] < 0.1
    shadow = store_e.read_table(REPLAY_SHADOW_TABLE)
    assert set(shadow["source"]) == {"replay"}
    assert not store_e.has_table(SHADOW_TABLE)  # a replay never writes the live nightly's ledger by default


def test_replay_frames_shapes_and_trial_log(tmp_path):
    store, sched, _ = _planted_store(0.08)
    res = _replay(store, sched, tmp_path)
    assert list(res.equity_curve.columns) == ["equity", "cash", "market_value", "exposure", "n_positions", "ret"]
    assert {"signal_date", "regime", "risk_mult", "r_multiple", "exit_reason"} <= set(res.trades.columns)
    assert len(res.daily) == len(res.equity_curve) == res.summary["sessions"]
    assert res.daily["n_orders"].max() <= 5  # execution.max_new_orders_per_day
    assert res.equity_curve["n_positions"].max() <= 8  # risk.max_open_positions
    assert (res.trades["entry_ts"].dt.date > res.trades["signal_date"]).all()  # next-open entries only
    assert res.equity_curve["equity"].iloc[-1] == pytest.approx(100_000.0 + res.trades["pnl"].sum())
    lines = (tmp_path / "trials.jsonl").read_text().strip().splitlines()
    rec = json.loads(lines[-1])
    assert rec["name"] == "replay" and rec["metrics"]["trades"] == res.summary["trades"]
    assert rec["params"]["use_router"] is False


def test_replay_is_deterministic(tmp_path):
    store, sched, _ = _planted_store(0.08)
    a = _replay(store, sched, tmp_path, record_shadow=False)
    b = _replay(store, sched, tmp_path, record_shadow=False)
    pd.testing.assert_frame_equal(a.trades, b.trades)
    pd.testing.assert_frame_equal(a.daily, b.daily)
    pd.testing.assert_frame_equal(a.equity_curve, b.equity_curve)


# ----------------------------------------------------------------------------------------------- router


def _fake_router(calls: list[tuple[date, pd.Timestamp]], mult: float):
    def market_state(panel, as_of, breadth=None, settings=None):
        calls.append((as_of, panel["ts"].max()))
        regime = "healthy_uptrend" if as_of.toordinal() % 2 == 0 else "correction"
        return SimpleNamespace(regime=regime)

    def select_strategies(state, settings):
        return {"planted": mult, "not_running": 1.0} if state.regime == "healthy_uptrend" else {}

    return lambda: (market_state, select_strategies)


def test_router_gates_by_regime_scales_risk_and_records_untaken_signals(tmp_path, monkeypatch):
    calls: list[tuple[date, pd.Timestamp]] = []
    monkeypatch.setattr(replay_mod, "_load_router", _fake_router(calls, 0.5))
    store, sched, _ = _planted_store(0.08)
    res = _replay(store, sched, tmp_path, use_router=True, settings=_settings(risk_per_trade_pct=0.2))
    assert len(res.trades) > 10
    assert set(res.trades["regime"]) == {"healthy_uptrend"}
    assert set(res.trades["risk_mult"]) == {0.5}
    assert list(res.by_regime.index) == ["healthy_uptrend"]
    assert all(ts.date() <= d for d, ts in calls)  # the router never sees a row after its as_of
    assert set(res.daily["allowed"]) <= {"planted=0.5", ""}  # strategies absent from the replay are ignored
    shadow = store.read_table(REPLAY_SHADOW_TABLE)
    corr = shadow.loc[shadow["regime"] == "correction"]
    assert len(corr) > 0 and not corr["taken"].astype(bool).any()
    assert res.summary["regime_days"].keys() == {"healthy_uptrend", "correction"}


def test_router_multiplier_halves_fixed_fractional_size(tmp_path, monkeypatch):
    bars = make_bars("AAA", [(100.0, 101.0, 99.0, 100.0)] * 6 + [(100.0, 100.5, 99.5, 100.0)] * 4, start="2024-01-02")
    store = Store()
    store.write_bars(bars)
    day = date(2024, 1, 4)
    sig = long_signal("AAA", day, 100.0, 98.0, 110.0, strategy="planted")

    class One(Strategy):
        name = "planted"

        def signals(self, panel, as_of, regime=None):
            return [sig] if as_of == day else []

    def go(use_router: bool) -> int:
        res = run_replay(_settings(risk_per_trade_pct=0.2), store, "2024-01-02", "2024-01-15", strategies=[One()],
                         use_router=use_router, costs=NO_FEES, trials_path=None, record_shadow=False)
        return int(res.trades.iloc[0]["qty"])

    full = go(False)
    monkeypatch.setattr(replay_mod, "_load_router", lambda: (
        lambda panel, as_of, breadth=None, settings=None: SimpleNamespace(regime="narrow_uptrend"),
        lambda state, settings: {"planted": 0.5},
    ))
    half = go(True)
    # 100k x 0.2% = $200 at (101.00 limit - 98 stop) -> 66 sh; at half risk -> 33 sh
    assert full == math.floor(200 / 3.0)
    assert half == math.floor(100 / 3.0)


# ----------------------------------------------------------------------------------------------- fills & exits


def _scripted_run(ohlc, sig_day: date, stop: float, target: float | None, params=None, **settings_kw):
    store = Store()
    store.write_bars(make_bars("AAA", ohlc, start="2024-01-02"))
    sig = long_signal("AAA", sig_day, ohlc[0][3], stop, target, strategy="planted")

    class One(Strategy):
        name = "planted"
        default_params = dict(params or {})

        def signals(self, panel, as_of, regime=None):
            return [sig] if as_of == sig_day else []

    settings = _settings(min_reward_risk=0.0)
    if settings_kw:
        settings = settings.model_copy(update={"execution": ExecutionConfig(**settings_kw)})
    last = pd.bdate_range("2024-01-02", periods=len(ohlc))[-1].date()
    return run_replay(settings, store, "2024-01-02", last, strategies=[One()], use_router=False, costs=NO_FEES,
                      trials_path=None)


FLAT = (100.0, 101.0, 99.0, 100.0)


def test_entry_skipped_when_open_above_marketable_limit():
    res = _scripted_run([FLAT, FLAT, (101.5, 103.0, 100.5, 102.0), FLAT, FLAT], date(2024, 1, 3), 95.0, 110.0)
    assert res.trades.empty
    assert res.summary["skip_reasons"] == {"open_through_limit": 1}


def test_stop_first_and_time_stop_fill_next_open():
    both = _scripted_run([FLAT, FLAT, FLAT, (100.0, 111.0, 94.0, 100.0), FLAT], date(2024, 1, 3), 95.0, 110.0)
    t = both.trades.iloc[0]
    assert t["exit_reason"] == ExitReason.STOP and t["exit_price"] == pytest.approx(95.0)

    flat = [FLAT] * 8
    timed = _scripted_run(flat, date(2024, 1, 2), 95.0, 110.0, params={"max_hold_days": 3},
                          breakeven_after_r=None, trail_after_r=None)
    t = timed.trades.iloc[0]
    assert t["exit_reason"] == ExitReason.TIME
    # entered 01-03, held 3 sessions (01-03..01-05) -> decided at the 01-05 close, filled at the 01-08 open
    assert t["exit_ts"].date() == date(2024, 1, 8)
    assert t["exit_price"] == pytest.approx(100.0)


def test_breakeven_stop_from_position_manager_takes_effect_next_session():
    ohlc = [FLAT, FLAT, (100.0, 106.0, 99.5, 105.5), (105.0, 105.5, 99.0, 100.0), FLAT]
    res = _scripted_run(ohlc, date(2024, 1, 2), 95.0, 120.0, breakeven_after_r=1.0, trail_after_r=None)
    t = res.trades.iloc[0]
    assert t["exit_reason"] == ExitReason.TRAIL_STOP  # ratcheted to the 100.00 entry at the +1.1R close
    assert t["exit_price"] == pytest.approx(100.0)
    assert t["r_multiple"] == pytest.approx(0.0)


# ----------------------------------------------------------------------------------------------- point in time

CUTOFF = date(2025, 3, 7)
PIT_SYMBOLS = ["SPY", *SampleProvider().stocks[:12]]


def _sample_store(poison_after: date | None) -> Store:
    bars = SampleProvider().daily_bars(PIT_SYMBOLS, date(2023, 9, 1), date(2025, 4, 30))
    if poison_after is not None:
        late = pd.to_datetime(bars["ts"]).dt.date > poison_after
        rng = np.random.default_rng(0)
        for c in ("open", "high", "low", "close"):
            bars.loc[late, c] = bars.loc[late, c] * 1000.0 * rng.uniform(0.5, 2.0, int(late.sum()))
        bars.loc[late, "volume"] = 1e12
        bars.loc[late & (rng.random(len(bars)) < 0.2), "close"] = np.nan
    store = Store()
    store.write_bars(bars)
    return store


def test_day_d_never_reads_rows_after_d(monkeypatch):
    calls: list[tuple[date, pd.Timestamp]] = []

    def market_state(panel, as_of, breadth=None, settings=None):
        calls.append((as_of, panel["ts"].max()))
        spy = panel.loc[panel["symbol"] == "SPY"].iloc[-1]
        return SimpleNamespace(regime="healthy_uptrend" if spy["close"] > spy["sma_50"] else "choppy")

    def select_strategies(state, settings):
        if state.regime == "healthy_uptrend":
            return {"rsi2_meanrev": 1.0, "pullback_trend": 1.0, "sr_bounce": 0.5}
        return {"rsi2_meanrev": 0.5}

    monkeypatch.setattr(replay_mod, "_load_router", lambda: (market_state, select_strategies))
    settings = Settings(
        risk=RiskConfig(max_open_positions=6),
        strategies={"rsi2_meanrev": {"enabled": True, "min_reward_risk": 0.0}, "pullback_trend": {"enabled": True},
                    "sr_bounce": {"enabled": True}},
    )

    def go(store: Store) -> tuple[Any, RecordingStrategy]:
        spy = RecordingStrategy()
        res = run_replay(settings, store, "2025-02-03", "2025-04-15",
                         strategies=["rsi2_meanrev", "pullback_trend", "sr_bounce", spy], trials_path=None)
        return res, spy

    clean_store, poisoned_store = _sample_store(None), _sample_store(CUTOFF)
    clean, spy_clean = go(clean_store)
    poisoned, spy_poisoned = go(poisoned_store)

    for as_of, last_ts, _ in spy_clean.calls + spy_poisoned.calls:
        assert last_ts.date() <= as_of
    assert all(ts.date() <= d for d, ts in calls)

    def upto(df: pd.DataFrame, col: str) -> pd.DataFrame:
        return df.loc[pd.to_datetime(df[col]).dt.date <= CUTOFF].reset_index(drop=True)

    d_clean, d_pois = upto(clean.daily, "date"), upto(poisoned.daily, "date")
    assert len(d_clean) > 20 and d_clean["n_signals"].sum() > 0 and d_clean["n_orders"].sum() > 0
    pd.testing.assert_frame_equal(d_clean, d_pois)
    pd.testing.assert_frame_equal(upto(clean.trades, "exit_ts"), upto(poisoned.trades, "exit_ts"))
    shadow_cols = ["strategy", "symbol", "as_of", "entry", "stop", "target", "score", "taken", "regime"]
    sc = _shadow_upto(clean_store.read_table(REPLAY_SHADOW_TABLE), shadow_cols)
    sp = _shadow_upto(poisoned_store.read_table(REPLAY_SHADOW_TABLE), shadow_cols)
    assert len(sc) > 0
    pd.testing.assert_frame_equal(sc, sp)
    # and the poison really did change what happened after the cutoff
    assert not clean.daily.equals(poisoned.daily)


def _shadow_upto(frame: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    frame = frame.assign(as_of=pd.to_datetime(frame["as_of"]).dt.date)
    frame = frame.loc[frame["as_of"] <= CUTOFF, cols]
    return frame.sort_values(["as_of", "strategy", "symbol"]).reset_index(drop=True)


def test_real_playbook_router_gates_trades_by_its_table(monkeypatch):
    playbook = pytest.importorskip("swing_engine.strategies.playbook")
    monkeypatch.setattr(replay_mod, "_load_router", _REAL_LOAD_ROUTER)
    monkeypatch.setattr(replay_mod, "_load_breadth", _REAL_LOAD_BREADTH)
    names = ["rsi2_meanrev", "pullback_trend", "sr_bounce", "breakout_52w"]
    settings = Settings(
        risk=RiskConfig(max_open_positions=6),
        strategies={n: {"enabled": True, **({"min_reward_risk": 0.0} if n == "rsi2_meanrev" else {})} for n in names},
    )
    res = run_replay(settings, _sample_store(None), "2025-01-02", "2025-04-15", trials_path=None)
    assert res.summary["router_available"] and not res.summary["strategy_failures"]
    known = set(settings.playbook.regimes)
    assert set(res.summary["regime_days"]) <= known
    table = settings.playbook.regimes
    for t in res.trades.itertuples(index=False):
        assert t.risk_mult == pytest.approx(table[t.regime][t.strategy])
    assert callable(playbook.select_strategies)


def test_empty_strategy_list_falls_back_to_enabled_settings(tmp_path):
    store, _, _ = _planted_store(0.0)
    with pytest.raises(ValueError, match="no strategies"):  # "planted" is enabled in settings but not registered
        run_replay(_settings(), store, "2022-06-01", "2022-07-01", strategies=[], trials_path=None)


# ----------------------------------------------------------------------------------------------- universe


class _SeesSymbols(Strategy):
    name = "sees"

    def __init__(self) -> None:
        super().__init__()
        self.seen: set[str] = set()
        self.rs: dict[str, float] = {}

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        self.seen |= set(panel["symbol"].astype(str))
        last = panel.loc[panel["ts"] == panel["ts"].max()]
        if "rs_63d_rank" in last.columns:
            self.rs.update(zip(last["symbol"].astype(str), last["rs_63d_rank"].astype(float), strict=True))
        return []


def _universe_store() -> Store:
    liquid = {f"LQ{k}": (50.0 + k, 2_000_000.0) for k in range(4)}
    spec = {**liquid, "THIN": (3.0, 1_000.0), "SPY": (500.0, 5_000_000.0), "QQQ": (400.0, 5_000_000.0),
            "IWM": (200.0, 5_000_000.0)}
    ts = pd.bdate_range("2023-06-01", "2024-06-28", tz="America/New_York")
    rng = np.random.default_rng(11)
    frames = []
    for sym, (price, volume) in spec.items():
        close = price * np.exp(np.cumsum(rng.normal(0.0005, 0.01, len(ts))))
        frames.append(pd.DataFrame({"symbol": sym, "ts": ts, "open": close, "high": close * 1.01, "low": close * 0.99,
                                    "close": close, "volume": volume, "vwap": close, "adj_close": close}))
    store = Store()
    store.write_bars(pd.concat(frames, ignore_index=True))
    return store


def test_replay_scans_and_measures_breadth_on_the_point_in_time_universe(monkeypatch):
    breadth_pop: list[set[str]] = []
    excluded: list[tuple[str, ...]] = []

    def market_breadth(panel, *, exclude=()):
        breadth_pop.append(set(panel["symbol"].astype(str)) - set(exclude))
        excluded.append(tuple(exclude))
        return pd.DataFrame({"pct_above_50": 50.0}, index=pd.DatetimeIndex(sorted(panel["ts"].unique())))

    monkeypatch.setattr(replay_mod, "_load_router",
                        lambda: (lambda *a, **k: SimpleNamespace(regime="choppy"), lambda s, c: {"sees": 1.0}))
    monkeypatch.setattr(replay_mod, "_load_breadth", lambda: market_breadth)
    strat = _SeesSymbols()
    res = run_replay(Settings(), _universe_store(), "2024-03-01", "2024-04-30", strategies=[strat], trials_path=None,
                     record_shadow=False)
    liquid = {f"LQ{k}" for k in range(4)}
    # ETFs pass the liquidity-only screen (no symbols table) but never count in breadth; THIN never passes
    assert set(excluded[0]) >= {"SPY", "QQQ", "IWM"} and breadth_pop[0] == liquid
    assert "THIN" not in strat.seen and liquid <= strat.seen
    assert res.summary["universe_screened"] and res.summary["universe_mean_size"] >= len(liquid)
    # rs_63d_rank ranks among the screened names only (THIN no longer in the population)
    assert set(strat.rs) <= strat.seen and max(strat.rs.values()) == pytest.approx(1.0)

    unscreened = _SeesSymbols()
    run_replay(Settings(), _universe_store(), "2024-03-01", "2024-04-30", strategies=[unscreened], trials_path=None,
               record_shadow=False, screen_universe=False)
    assert "THIN" in unscreened.seen
