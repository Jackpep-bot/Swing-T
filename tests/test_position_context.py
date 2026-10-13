"""`should_exit(row, bars_held, position)`: the PositionContext reaches the hook in run_backtest, replay and the
position manager; two-argument hooks keep working; the catalog exits built on it fire per their cards."""
from __future__ import annotations

import math
from datetime import date
from typing import Any

import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.core.config import ExecutionConfig, RiskConfig, Settings
from swing_engine.core.interfaces import Strategy, exit_takes_position
from swing_engine.core.models import PositionContext, Signal
from swing_engine.data.store import Store
from swing_engine.execution.position_manager import review_positions
from swing_engine.features.extra import ensure_extra
from swing_engine.research import replay as replay_mod
from swing_engine.research.backtest import BPS, CostModel, ExitReason, run_backtest
from swing_engine.research.replay import run_replay
from tests.fixtures.research.strategies import ScriptedStrategy, long_signal
from tests.fixtures.research.synthetic_panel import make_bars, trading_dates
from tests.test_execution_position_manager import (
    AS_OF,
    ENTRY,
    SESSIONS,
    STOP,
    make_settings,
    panel_for,
    sim_with_position,
)

SLIP = 10.0
COSTS = CostModel(slippage_bps=SLIP)
NO_FEES = CostModel(slippage_bps=0.0, sec_fee_per_million_sold=0.0, finra_taf_per_share=0.0)
DAYS = trading_dates(6, "2024-01-02")
FLAT = (100.0, 101.0, 99.0, 100.0)
UP = (100.0, 104.0, 99.0, 103.0)
FEATURES = {"drop_low": 97.0, "pivot": 99.5}


def _signal(as_of: date, strategy: str = "scripted") -> Signal:
    sig = long_signal("AAA", as_of, FLAT[3], 90.0, 200.0, strategy=strategy)
    return sig.model_copy(update={"features": FEATURES})


class Probe(ScriptedStrategy):
    """Records every PositionContext; exits once `exit_at` bars are held."""

    def __init__(self, sigs: dict[date, list[Signal]], exit_at: int = 99, name: str = "scripted"):
        super().__init__(sigs)
        self.name, self.exit_at, self.seen = name, exit_at, []

    def should_exit(self, row: pd.Series, bars_held: int, position: PositionContext | None = None) -> bool:
        self.seen.append(position)
        return bars_held >= self.exit_at


class TwoArg(ScriptedStrategy):
    def should_exit(self, row: pd.Series, bars_held: int) -> bool:  # a third argument would raise TypeError
        return bars_held >= 2


# ----------------------------------------------------------------------------------------------- dispatcher


def test_exit_takes_position_counts_positional_parameters() -> None:
    def three(row, bars_held, position=None): ...
    def star(row, *args): ...

    assert not exit_takes_position(lambda row, bars_held: False)
    assert exit_takes_position(three) and exit_takes_position(star)
    assert exit_takes_position(Probe({}).should_exit) and not exit_takes_position(TwoArg({}).should_exit)
    assert not exit_takes_position(registry.get("strategy", "rsi2_meanrev")().should_exit)  # 2-arg override
    assert exit_takes_position(registry.get("strategy", "breakout_52w")().should_exit)  # PanelStrategy default


def test_context_is_read_only() -> None:
    ctx = PositionContext(entry_features={"a": 1.0})
    with pytest.raises(AttributeError):
        ctx.entry_price = 1.0  # type: ignore[misc]
    with pytest.raises(TypeError):
        ctx.entry_features["a"] = 2.0  # type: ignore[index]


# ----------------------------------------------------------------------------------------------- engines


def test_backtest_passes_entry_fill_stops_best_price_and_signal_features() -> None:
    probe = Probe({DAYS[0].date(): [_signal(DAYS[0].date())]}, exit_at=3)
    res = run_backtest(probe, make_bars("AAA", [FLAT, FLAT, UP, FLAT, FLAT]), costs=COSTS)
    fill = 100.0 * (1 + SLIP / BPS)
    first, second, third = probe.seen
    assert first.entry_price == pytest.approx(fill) and first.bars_held == 1
    assert first.stop == first.initial_stop == 90.0
    assert first.best_price == pytest.approx(101.0)  # today's high, folded in before the close is marked
    assert second.best_price == pytest.approx(104.0) and third.best_price == pytest.approx(104.0)
    assert dict(first.entry_features) == FEATURES and first.as_of == DAYS[0].date()
    t = res.trades.iloc[0]
    assert t["exit_reason"] == ExitReason.RULE and t["bars_held"] == 3


def test_backtest_two_argument_hook_still_books_a_rule_exit() -> None:
    res = run_backtest(TwoArg({DAYS[0].date(): [_signal(DAYS[0].date())]}), make_bars("AAA", [FLAT] * 5), costs=COSTS)
    t = res.trades.iloc[0]
    assert t["exit_reason"] == ExitReason.RULE and t["bars_held"] == 2


def _replay_settings(name: str) -> Settings:
    return Settings(
        risk=RiskConfig(max_open_positions=8, min_reward_risk=0.0),
        execution=ExecutionConfig(max_new_orders_per_day=5, breakeven_after_r=None, trail_after_r=None),
        strategies={name: {"enabled": True, "min_reward_risk": 0.0}},
    )


def _replay(strategy: Strategy, ohlc: list[tuple[float, float, float, float]], monkeypatch) -> Any:
    monkeypatch.setattr(replay_mod, "_load_router", lambda: None)
    monkeypatch.setattr(replay_mod, "_load_breadth", lambda: None)
    store = Store()
    store.write_bars(make_bars("AAA", ohlc, start="2024-01-02"))
    last = pd.bdate_range("2024-01-02", periods=len(ohlc))[-1].date()
    return run_replay(_replay_settings(strategy.name), store, "2024-01-02", last, strategies=[strategy],
                      use_router=False, costs=NO_FEES, trials_path=None, record_shadow=False)


def test_replay_passes_the_context_through_the_position_manager(monkeypatch) -> None:
    probe = Probe({date(2024, 1, 2): [_signal(date(2024, 1, 2), "probe")]}, exit_at=2, name="probe")
    res = _replay(probe, [FLAT, FLAT, UP, FLAT, FLAT], monkeypatch)
    first, second = probe.seen
    assert first.entry_price == pytest.approx(100.0) and first.initial_stop == 90.0 and first.bars_held == 1
    assert first.best_price == pytest.approx(101.0) and second.best_price == pytest.approx(104.0)
    assert dict(second.entry_features) == FEATURES and second.as_of == date(2024, 1, 2)
    t = res.trades.iloc[0]
    assert t["exit_reason"] == ExitReason.RULE and t["exit_ts"].date() == date(2024, 1, 5)  # next open


def test_replay_two_argument_hook_still_exits(monkeypatch) -> None:
    two = TwoArg({date(2024, 1, 2): [_signal(date(2024, 1, 2), "two")]})
    two.name = "two"
    res = _replay(two, [FLAT] * 5, monkeypatch)
    assert res.trades.iloc[0]["exit_reason"] == ExitReason.RULE


class LiveProbe:
    name = "probe"
    params: dict[str, Any] = {}

    def __init__(self) -> None:
        self.seen: list[tuple[int, PositionContext]] = []

    def should_exit(self, row: pd.Series, bars_held: int, position: PositionContext | None = None) -> bool:
        self.seen.append((bars_held, position))
        return position is not None and float(row["close"]) < position.entry_price


def test_position_manager_builds_the_context_from_broker_and_ledger_facts(tmp_path) -> None:
    probe = LiveProbe()
    broker = sim_with_position(SESSIONS[-3], strategy="probe")
    panel = panel_for("ACME", [98.0, 103.0, 101.0, 99.0])  # highs = close + 1; the first row predates the entry
    actions = review_positions(make_settings(tmp_path), broker, panel, AS_OF, {"probe": probe})
    ((bars, ctx),) = probe.seen
    assert bars == 3 and ctx.bars_held == 3
    assert ctx.entry_price == ENTRY and ctx.initial_stop == STOP and ctx.stop == STOP
    assert ctx.best_price == 104.0  # highest high since the entry day, not the pre-entry 99
    assert dict(ctx.entry_features) == {} and ctx.as_of is None  # the ledger keeps no signal features / date
    assert [(a.kind.value, a.reason.value) for a in actions] == [("close", "strategy_exit")]


# ----------------------------------------------------------------------------------------------- extra features


def test_bars_since_ge_level() -> None:
    bars = make_bars("AAA", [(c, c, c, c) for c in (30.0, 45.0, 41.0, 39.0, 20.0, 50.0)])
    got = ensure_extra(bars, ["bars_since_ge_40_of_close"])["bars_since_ge_40_of_close"].tolist()
    assert math.isnan(got[0]) and got[1:] == [0.0, 0.0, 1.0, 2.0, 0.0]


def test_gandalf_weak_set_d_hand_checked() -> None:
    # oldest first: bar[4] .. bar[0]; D: ohlc4[2]=9 < mid[0]=10, median[4]=10 < ohlc4[3]=11, mid[1]=10 < ohlc4[1]=10.5
    rows = [(10.0, 10.0, 10.0, 10.0), (11.0, 11.0, 11.0, 11.0), (9.0, 9.0, 9.0, 9.0), (10.0, 12.0, 10.0, 10.0)]
    weak = ensure_extra(make_bars("AAA", [*rows, (10.0, 10.0, 10.0, 10.0)]), ["gandalf_weak"])["gandalf_weak"]
    assert weak.iloc[:4].isna().all() and weak.iloc[4] == 1.0
    calm = ensure_extra(make_bars("AAA", [*rows, (8.0, 8.0, 8.0, 8.0)]), ["gandalf_weak"])["gandalf_weak"]
    assert calm.iloc[4] == 0.0  # mid[0] = 8 is not above ohlc4[2] = 9, and set C fails


# ----------------------------------------------------------------------------------------------- strategy exits


def _strat(name: str, params: dict[str, Any] | None = None):
    return registry.get("strategy", name)(params)


def _ctx(bars_held: int = 1, entry: float = 100.0, **features: float) -> PositionContext:
    return PositionContext(entry_price=entry, stop=90.0, initial_stop=90.0, bars_held=bars_held,
                           best_price=entry, entry_features=features)


def _row(**cols: float) -> pd.Series:
    return pd.Series(cols)


def test_hudgin_exits_on_a_close_below_the_entry_drop_low() -> None:
    s = _strat("hudgin_golden_triangle")
    assert s.should_exit(_row(close=96.0), 2, _ctx(2, drop_low=97.0))
    assert not s.should_exit(_row(close=98.0), 2, _ctx(2, drop_low=97.0))
    assert not s.should_exit(_row(close=96.0), 2, _ctx(2))  # live: no entry features
    assert not s.should_exit(_row(close=96.0), 2)
    assert not _strat("hudgin_golden_triangle", {"exit_below_drop_low": False}).should_exit(
        _row(close=96.0), 2, _ctx(2, drop_low=97.0))


@pytest.mark.parametrize(("name", "window"), [("ipo_first_base_breakout", 3), ("vcp_sepa_breakout", 2)])
def test_failed_breakout_exits_below_the_pivot_within_the_card_window(name: str, window: int) -> None:
    s = _strat(name)
    row = _row(close=99.0, volume=1e6, sma_50=90.0, avg_vol_50d=1e6)
    assert s.should_exit(row, window, _ctx(window, pivot=100.0))
    assert not s.should_exit(row, window + 1, _ctx(window + 1, pivot=100.0))  # past the window: hold
    assert not s.should_exit(_row(close=101.0, volume=1e6, sma_50=90.0, avg_vol_50d=1e6), 1, _ctx(1, pivot=100.0))
    assert not s.should_exit(row, 1, _ctx(1)) and not s.should_exit(row, 1)
    assert not _strat(name, {"fail_exit_bars": 0}).should_exit(row, 1, _ctx(1, pivot=100.0))


def test_nr7_exits_at_the_first_profitable_close() -> None:
    s = _strat("nr7_nr4_range_contraction")
    assert s.should_exit(_row(close=100.5), 1, _ctx(1))
    assert not s.should_exit(_row(close=100.0), 1, _ctx(1)) and not s.should_exit(_row(close=100.5), 1)
    assert not _strat("nr7_nr4_range_contraction", {"exit_first_profitable_close": False}).should_exit(
        _row(close=100.5), 1, _ctx(1))
    assert s.should_exit(_row(close=90.0), 3, _ctx(3))  # 3-bar time exit unchanged


def test_momentum_pinball_exits_at_the_close_if_losing() -> None:
    s = _strat("momentum_pinball")
    assert s.should_exit(_row(close=99.0), 1, _ctx(1))
    assert not s.should_exit(_row(close=100.0), 1, _ctx(1)) and not s.should_exit(_row(close=99.0), 1)
    assert not _strat("momentum_pinball", {"exit_if_losing": False}).should_exit(_row(close=99.0), 1, _ctx(1))


def test_gandalf_gain_exit_and_losing_trade_weakness() -> None:
    s = _strat("gandalf_project_research_system")
    assert s.should_exit(_row(close=101.0, gandalf_weak=0.0), 2, _ctx(2))  # exit gain length 2, in profit
    assert not s.should_exit(_row(close=101.0, gandalf_weak=1.0), 1, _ctx(1))  # too early, not losing
    assert s.should_exit(_row(close=99.0, gandalf_weak=1.0), 1, _ctx(1))  # losing on weakness
    assert not s.should_exit(_row(close=99.0, gandalf_weak=0.0), 1, _ctx(1))
    assert not s.should_exit(_row(close=99.0, gandalf_weak=float("nan")), 1, _ctx(1))
    assert not s.should_exit(_row(close=101.0, gandalf_weak=1.0), 3)  # no context: time exit only
    assert "gandalf_weak" in s.extra_features


def _pzo_row(pzo: float, prev: float, since_cross: float, since_reach: float, close: float = 9.0) -> pd.Series:
    return _row(close=close, pzo_14=pzo, prev_pzo_14=prev, ema_60=10.0, adx_14=10.0,  # ADX <= 18: non-trend LX
                bars_since_ge_15_of_pzo_14=since_cross, bars_since_ge_40_of_pzo_14=since_reach)


def test_pzo_non_trend_path_exits() -> None:
    s = _strat("price_zone_oscillator")
    nan = float("nan")
    # dropped through +40 while held (reached it 2 bars ago), now below 0 with close < EMA60
    reached = _pzo_row(-1.0, -0.5, since_cross=2.0, since_reach=2.0)
    assert s.should_exit(reached, 4, _ctx(4)) and not s.should_exit(reached, 4)  # row rule: no cross through 0
    assert not s.should_exit(_pzo_row(-1.0, -0.5, 2.0, 2.0, close=11.0), 4, _ctx(4))  # close above EMA60
    # a -40 recovery that never crossed +15 is not a failed +15 cross (the row rule exits it on the -5 cross)
    oversold = _pzo_row(-10.0, -3.0, since_cross=nan, since_reach=nan)
    assert not s.should_exit(oversold, 3, _ctx(3)) and s.should_exit(oversold, 3)
    # +15 cross on the signal bar (bars_held bars ago), never reached +40, now below -5
    failed = _pzo_row(-6.0, -5.5, since_cross=3.0, since_reach=nan, close=11.0)
    assert s.should_exit(failed, 3, _ctx(3)) and not s.should_exit(failed, 3)
    # +40 and +15 both last seen before the entry: no path rule applies to this position
    assert not s.should_exit(_pzo_row(-1.0, -0.5, since_cross=5.0, since_reach=5.0), 3, _ctx(3))
    assert {"bars_since_ge_15_of_pzo_14", "bars_since_ge_40_of_pzo_14"} <= set(s.extra_features)


def test_position_manager_reads_signal_features_and_date_from_the_ledger_intent(tmp_path) -> None:
    from swing_engine.execution.ledger import OrderLedger
    from tests.test_execution_position_manager import intent

    probe = LiveProbe()
    entry_day = SESSIONS[-3]
    broker = sim_with_position(entry_day, strategy="probe")
    settings = make_settings(tmp_path)
    ledger = OrderLedger(settings.execution.ledger_file)
    ledger.reserve(intent(strategy="probe", day=entry_day, features=FEATURES, signal_as_of=SESSIONS[-4]), "test")
    ledger.close()
    review_positions(settings, broker, panel_for("ACME", [98.0, 103.0, 101.0, 99.0]), AS_OF, {"probe": probe})
    ((_bars, ctx),) = probe.seen
    assert dict(ctx.entry_features) == FEATURES and ctx.as_of == SESSIONS[-4]


def test_sizing_carries_signal_features_and_date_into_the_intent() -> None:
    from swing_engine.risk.sizing import size_signal

    sig = _signal(DAYS[1])
    out = size_signal(sig, 100_000.0, RiskConfig(min_reward_risk=0.0))
    assert out is not None and out.features == dict(sig.features) and out.signal_as_of == sig.as_of
