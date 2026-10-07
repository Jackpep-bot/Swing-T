"""Backtester mechanics: fills, exits, sizing, costs, point-in-time slicing, planted edge."""
from __future__ import annotations

import pandas as pd
import pytest

from swing_engine.core.config import RiskConfig
from swing_engine.core.models import OrderIntent, Side, Signal
from swing_engine.research.backtest import (
    BPS,
    EQUITY_COLUMNS,
    TRADE_COLUMNS,
    BacktestConfig,
    CostModel,
    ExitReason,
    TrailingStop,
    _RegimeLookup,
    fixed_fractional_sizer,
    run_backtest,
)
from swing_engine.research.metrics import summarize
from swing_engine.strategies.rsi2_meanrev import RSI2MeanRev
from tests.fixtures.research.strategies import FlagStrategy, RecordingStrategy, ScriptedStrategy, long_signal
from tests.fixtures.research.synthetic_panel import make_bars, make_panel, trading_dates

SLIP = 10.0
SLIP_F = SLIP / BPS
COSTS = CostModel(slippage_bps=SLIP)
NO_FEES = CostModel(slippage_bps=SLIP, sec_fee_per_million_sold=0.0, finra_taf_per_share=0.0)
DAYS = trading_dates(8, "2024-01-02")
FLAT = (100.0, 101.0, 99.0, 100.0)
WIDE_STOP, FAR_TARGET = 90.0, 200.0


def _run_one(ohlc, *, stop=95.0, target=110.0, costs=COSTS, config=None, risk=None, sizer=None, params=None):
    panel = make_bars("AAA", ohlc)
    sig = long_signal("AAA", DAYS[0].date(), FLAT[3], stop, target)
    strat = ScriptedStrategy({sig.as_of: [sig]}, params)
    return run_backtest(strat, panel, risk_cfg=risk, costs=costs, config=config, sizer=sizer)


# ----------------------------------------------------------------------------------------------- planted edge


def test_planted_edge_beats_zero_edge():
    edge = run_backtest(FlagStrategy(), make_panel(seed=1, edge=0.08), costs=CostModel.small_cap())
    noise = run_backtest(FlagStrategy(), make_panel(seed=1, edge=0.0), costs=CostModel.small_cap())
    s_edge, s_noise = summarize(edge), summarize(noise)
    assert s_edge["trades"] >= 40 and s_noise["trades"] >= 40
    assert s_edge["avg_r"] > 0.25
    assert s_edge["total_return"] > 0
    assert s_edge["win_rate"] > 0.5
    assert s_noise["avg_r"] < 0.1
    assert s_edge["avg_r"] - s_noise["avg_r"] > 0.3
    assert s_noise["cost_drag"] > 0  # the zero-edge run still pays slippage and fees


# ----------------------------------------------------------------------------------------------- fills & exits


def test_entry_fills_at_next_open_with_slippage():
    res = _run_one([FLAT, (102.0, 105.0, 101.0, 104.0), (104.0, 106.0, 103.0, 105.0), FLAT])
    t = res.trades.iloc[0]
    assert t["entry_ts"] == DAYS[1]
    assert t["entry_price"] == pytest.approx(102.0 * (1 + SLIP_F))
    assert t["side"] == "long"


def test_stop_gap_through_fills_at_open_not_stop():
    res = _run_one([FLAT, FLAT, (90.0, 92.0, 88.0, 89.0), (89.0, 90.0, 88.0, 89.0)])
    t = res.trades.iloc[0]
    assert t["exit_reason"] == ExitReason.STOP_GAP
    assert t["exit_ts"] == DAYS[2]
    assert t["exit_price"] == pytest.approx(90.0 * (1 - SLIP_F))
    assert t["r_multiple"] < -1.5  # lost twice the planned risk because of the gap


def test_intrabar_stop_fills_at_stop_price():
    res = _run_one([FLAT, FLAT, (99.0, 100.0, 94.0, 96.0), FLAT])
    t = res.trades.iloc[0]
    assert t["exit_reason"] == ExitReason.STOP
    assert t["exit_price"] == pytest.approx(95.0 * (1 - SLIP_F))
    assert -1.2 < t["r_multiple"] < -0.9


def test_target_fills_at_target_or_at_gap_open():
    hit = _run_one([FLAT, FLAT, (105.0, 111.0, 104.0, 110.0), FLAT])
    assert hit.trades.iloc[0]["exit_reason"] == ExitReason.TARGET
    assert hit.trades.iloc[0]["exit_price"] == pytest.approx(110.0 * (1 - SLIP_F))
    gapped = _run_one([FLAT, FLAT, (112.0, 115.0, 111.0, 113.0), FLAT])
    assert gapped.trades.iloc[0]["exit_reason"] == ExitReason.TARGET
    assert gapped.trades.iloc[0]["exit_price"] == pytest.approx(112.0 * (1 - SLIP_F))


def test_gap_through_target_fills_at_open_before_an_intrabar_stop_touch():
    # open 112 > target 110: the resting sell limit fills at the open; the later low of 94 never reaches us
    res = _run_one([FLAT, FLAT, (112.0, 115.0, 94.0, 100.0), FLAT])
    t = res.trades.iloc[0]
    assert t["exit_reason"] == ExitReason.TARGET
    assert t["exit_price"] == pytest.approx(112.0 * (1 - SLIP_F))
    assert t["r_multiple"] > 2.0


def test_stop_wins_when_both_touch_unless_configured():
    bars = [FLAT, FLAT, (100.0, 111.0, 94.0, 100.0), FLAT]
    assert _run_one(bars).trades.iloc[0]["exit_reason"] == ExitReason.STOP
    cfg = BacktestConfig(stop_first_when_both_hit=False)
    assert _run_one(bars, config=cfg).trades.iloc[0]["exit_reason"] == ExitReason.TARGET


def test_time_stop_uses_strategy_max_hold_days():
    res = _run_one([FLAT] * 8, stop=WIDE_STOP, target=FAR_TARGET, params={"max_hold_days": 3})
    t = res.trades.iloc[0]
    assert t["exit_reason"] == ExitReason.TIME
    assert t["bars_held"] == 3
    assert t["exit_ts"] == DAYS[3]
    assert t["exit_price"] == pytest.approx(100.0 * (1 - SLIP_F))


def test_open_position_is_closed_at_window_end():
    res = _run_one([FLAT] * 8, stop=WIDE_STOP, target=FAR_TARGET, config=BacktestConfig(max_hold_bars=100))
    t = res.trades.iloc[0]
    assert t["exit_reason"] == ExitReason.END
    assert t["exit_ts"] == DAYS[7]
    assert res.equity["n_positions"].iloc[-1] == 0
    assert res.final_equity == pytest.approx(res.equity["cash"].iloc[-1])


def test_entry_cancelled_when_open_gaps_through_stop():
    res = _run_one([FLAT, (94.0, 96.0, 93.0, 95.0), FLAT, FLAT])
    assert res.trades.empty
    assert res.skip_reasons.get("open_through_stop") == 1
    assert res.n_entries_skipped == 1


def test_entry_cancelled_when_open_is_through_entry_limit():
    def limit_sizer(signal: Signal, equity, risk_cfg, open_positions) -> OrderIntent:
        return OrderIntent(symbol=signal.symbol, side=signal.side, qty=10, entry_limit=101.0, stop=signal.stop,
                           target=signal.target, strategy=signal.strategy, client_order_id="x", risk_dollars=50)

    res = _run_one([FLAT, (103.0, 104.0, 102.0, 103.0), FLAT, FLAT], sizer=limit_sizer)
    assert res.trades.empty
    assert res.skip_reasons.get("open_through_limit") == 1


def test_delisted_symbol_closes_at_its_last_close():
    aaa = make_bars("AAA", [FLAT, FLAT, (101.0, 103.0, 100.0, 102.0), (102.0, 104.0, 101.0, 103.0)])
    bbb = make_bars("BBB", [FLAT] * 8)
    panel = pd.concat([aaa, bbb], ignore_index=True)
    sig = long_signal("AAA", DAYS[0].date(), FLAT[3], WIDE_STOP, FAR_TARGET)
    res = run_backtest(ScriptedStrategy({sig.as_of: [sig]}), panel, costs=COSTS)
    t = res.trades.iloc[0]
    assert t["exit_reason"] == ExitReason.DELISTED
    assert t["exit_ts"] == DAYS[3]
    assert t["exit_price"] == pytest.approx(103.0 * (1 - SLIP_F))


def test_short_side_mirrors_long():
    panel = make_bars("AAA", [FLAT, FLAT, (99.0, 100.0, 89.0, 90.0), FLAT])
    sig = long_signal("AAA", DAYS[0].date(), FLAT[3], 105.0, 90.0, side=Side.SHORT)
    res = run_backtest(ScriptedStrategy({sig.as_of: [sig]}), panel, costs=COSTS)
    t = res.trades.iloc[0]
    assert t["side"] == "short"
    assert t["entry_price"] == pytest.approx(100.0 * (1 - SLIP_F))  # short entry is a sale
    assert t["exit_reason"] == ExitReason.TARGET
    assert t["exit_price"] == pytest.approx(90.0 * (1 + SLIP_F))
    assert t["pnl"] > 0


def test_exit_rule_hook_fires_at_close():
    cfg = BacktestConfig(exit_rule=lambda row, pos: float(row["close"]) > 103.0)
    res = _run_one([FLAT, FLAT, (101.0, 105.0, 100.0, 104.0), FLAT], stop=WIDE_STOP, target=FAR_TARGET, config=cfg)
    t = res.trades.iloc[0]
    assert t["exit_reason"] == ExitReason.RULE
    assert t["exit_ts"] == DAYS[2]
    assert t["exit_price"] == pytest.approx(104.0 * (1 - SLIP_F))


def test_strategy_exit_rule_attribute_is_picked_up():
    sig = long_signal("AAA", DAYS[0].date(), FLAT[3], WIDE_STOP, FAR_TARGET)
    strat = ScriptedStrategy({sig.as_of: [sig]})
    strat.exit_rule = lambda row, pos: pos.bars_held >= 2  # duck-typed hook on the strategy
    res = _run_one_from(strat, [FLAT] * 6)
    t = res.trades.iloc[0]
    assert t["exit_reason"] == ExitReason.RULE and t["bars_held"] == 2


def test_strategy_should_exit_hook_books_a_rule_exit():
    """rsi2_meanrev's documented exit (rsi_2 > 70) runs through `should_exit`, which the backtester must honour."""
    rsi = [5.0, 50.0, 80.0, 50.0, 50.0, 50.0, 50.0, 50.0]  # oversold at the first close, recovered two bars later
    panel = make_bars("AAA", [FLAT] * 8).assign(rsi_2=rsi, sma_200=90.0, sma_10=105.0)
    strat = RSI2MeanRev()
    assert not callable(getattr(strat, "exit_rule", None)) and callable(strat.should_exit)
    res = run_backtest(strat, panel, costs=COSTS)
    assert len(res.trades) == 1
    t = res.trades.iloc[0]
    assert t["entry_ts"] == DAYS[1] and t["target"] == pytest.approx(105.0)  # sma_10 is the reference target
    assert t["exit_reason"] == ExitReason.RULE and t["exit_ts"] == DAYS[2] and t["bars_held"] == 2
    assert t["exit_price"] == pytest.approx(100.0 * (1 - SLIP_F))  # at the close, not at the static target


def test_should_exit_time_rule_is_reported_as_a_time_stop():
    panel = make_bars("AAA", [FLAT] * 8).assign(rsi_2=[5.0] + [50.0] * 7, sma_200=90.0, sma_10=105.0)
    res = run_backtest(RSI2MeanRev({"max_hold_days": 3}), panel, costs=COSTS)
    t = res.trades.iloc[0]
    assert t["exit_reason"] == ExitReason.TIME and t["bars_held"] == 3


# ----------------------------------------------------------------------------------------------- trailing


def test_trailing_pct_stop_locks_in_profit():
    bars = [FLAT, FLAT, (105.0, 110.0, 104.0, 109.0), (110.0, 120.0, 109.0, 118.0), (117.0, 118.0, 112.0, 113.0), FLAT]
    cfg = BacktestConfig(trailing=TrailingStop(pct=5.0))
    res = _run_one(bars, stop=WIDE_STOP, target=FAR_TARGET, config=cfg)
    t = res.trades.iloc[0]
    assert t["exit_reason"] == ExitReason.TRAIL_STOP
    assert t["exit_ts"] == DAYS[4]
    assert t["exit_price"] == pytest.approx(120.0 * 0.95 * (1 - SLIP_F))
    assert t["pnl"] > 0
    assert t["stop"] > t["initial_stop"]


def test_breakeven_ratchet_moves_stop_to_entry():
    bars = [FLAT, FLAT, (103.0, 107.0, 102.0, 106.0), (104.0, 105.0, 99.0, 100.0), FLAT]
    cfg = BacktestConfig(trailing=TrailingStop(breakeven_after_r=1.0))
    res = _run_one(bars, stop=95.0, target=FAR_TARGET, config=cfg, costs=NO_FEES)
    t = res.trades.iloc[0]
    assert t["exit_reason"] == ExitReason.TRAIL_STOP
    assert t["stop"] == pytest.approx(t["entry_price"])
    assert abs(t["r_multiple"]) < 0.05


# ----------------------------------------------------------------------------------------------- portfolio rules


def test_one_position_per_symbol_never_overlaps():
    sig = {d.date(): [long_signal("AAA", d.date(), FLAT[3], WIDE_STOP, FAR_TARGET)] for d in DAYS}
    res = _run_one_from(ScriptedStrategy(sig, {"max_hold_days": 2}), [FLAT] * 8)
    t = res.trades
    assert len(t) >= 3
    assert (t["entry_ts"].iloc[1:].to_numpy() > t["exit_ts"].iloc[:-1].to_numpy()).all()
    assert res.equity["n_positions"].max() == 1


def _run_one_from(strategy, ohlc, **kw):
    return run_backtest(strategy, make_bars("AAA", ohlc), costs=COSTS, **kw)


def test_max_open_positions_caps_entries():
    symbols = [f"S{k}" for k in range(6)]
    panel = pd.concat([make_bars(s, [FLAT] * 8) for s in symbols], ignore_index=True)
    sigs = [long_signal(s, DAYS[0].date(), FLAT[3], WIDE_STOP, FAR_TARGET, score=k) for k, s in enumerate(symbols)]
    strat = ScriptedStrategy({DAYS[0].date(): sigs}, {"max_hold_days": 50})
    res = run_backtest(strat, panel, risk_cfg=RiskConfig(max_open_positions=3), costs=COSTS)
    assert res.equity["n_positions"].max() == 3
    assert len(res.trades) == 3
    assert set(res.trades["symbol"]) == {"S5", "S4", "S3"}  # highest scores first
    assert res.skip_reasons.get("no_free_slot") == 3


def test_universe_at_gates_signals_point_in_time():
    panel = pd.concat([make_bars("AAA", [FLAT] * 8), make_bars("BBB", [FLAT] * 8)], ignore_index=True)
    sigs = {
        d.date(): [long_signal(s, d.date(), FLAT[3], WIDE_STOP, FAR_TARGET) for s in ("AAA", "BBB")]
        for d in DAYS[:2]
    }
    admitted_from = DAYS[1].date()  # BBB only passes the universe screen from the second anchor on
    res = run_backtest(
        ScriptedStrategy(sigs, {"max_hold_days": 50}), panel, costs=COSTS,
        universe_at=lambda d: {"AAA"} if d < admitted_from else {"AAA", "BBB"},
    )
    assert res.n_signals == 4 and res.skip_reasons["not_in_universe"] == 1
    entries = res.trades.set_index("symbol")["entry_ts"]
    assert entries["AAA"] == DAYS[1] and entries["BBB"] == DAYS[2]  # BBB traded only once it qualified


def test_regime_lookup_falls_back_to_panel_market_columns():
    panel = make_bars("AAA", [FLAT] * 4).assign(market_trend_state=1.0, market_vol_regime=2.0)
    spy_raw = make_bars("SPY", [FLAT] * 4)  # raw bars from a provider: no regime columns
    assert _RegimeLookup(spy_raw, panel)(DAYS[0]) == {"market_trend_state": 1.0, "market_vol_regime": 2.0}
    spy = spy_raw.assign(trend_state=-1.0)  # a market frame with its own regime still wins
    assert _RegimeLookup(spy, panel)(DAYS[0])["market_trend_state"] == -1.0
    assert _RegimeLookup(None, make_bars("AAA", [FLAT] * 4))(DAYS[0]) is None


def test_custom_sizer_plugs_in():
    def seven(signal: Signal, equity, risk_cfg, open_positions) -> OrderIntent:
        return OrderIntent(symbol=signal.symbol, side=signal.side, qty=7, entry_limit=None, stop=signal.stop,
                           target=signal.target, strategy=signal.strategy, client_order_id="seven", risk_dollars=35)

    res = _run_one([FLAT, FLAT, (99.0, 100.0, 94.0, 96.0), FLAT], sizer=seven)
    assert (res.trades["qty"] == 7).all()


def test_fixed_fractional_sizer_schwab_example():
    sig = long_signal("AAA", DAYS[0].date(), 10.0, 8.0, 14.0)
    intent = fixed_fractional_sizer(sig, 50_000.0, RiskConfig(risk_per_trade_pct=1.0), [])
    assert intent is not None and intent.qty == 250
    assert intent.risk_dollars == pytest.approx(500.0)
    capped = fixed_fractional_sizer(sig, 50_000.0, RiskConfig(risk_per_trade_pct=1.0, max_position_pct=2.0), [])
    assert capped is not None and capped.qty == 100
    assert fixed_fractional_sizer(sig, 50_000.0, RiskConfig(max_open_positions=0), []) is None


def test_invalid_signal_geometry_is_skipped():
    panel = make_bars("AAA", [FLAT] * 4)
    bad = Signal(strategy="s", symbol="AAA", as_of=DAYS[0].date(), entry=100.0, stop=105.0)
    res = run_backtest(ScriptedStrategy({bad.as_of: [bad]}), panel, costs=COSTS)
    assert res.trades.empty
    assert res.skip_reasons.get("stop_not_below_entry") == 1


# ----------------------------------------------------------------------------------------------- point in time


def test_strategy_only_sees_bars_up_to_as_of():
    strat = RecordingStrategy()
    run_backtest(strat, make_panel(n_symbols=3, n_days=12, seed=3), costs=COSTS)
    assert strat.calls  # one call per day except the last
    for as_of, last_ts, _ in strat.calls:
        assert last_ts is not None and last_ts.date() == as_of


def test_regime_comes_from_market_frame():
    panel = make_bars("AAA", [FLAT] * 4)
    market = pd.DataFrame({"ts": DAYS[:4], "market_trend_state": 1, "market_vol_regime": 0})
    strat = RecordingStrategy()
    run_backtest(strat, panel, market=market, costs=COSTS)
    assert all(r == {"market_trend_state": 1.0, "market_vol_regime": 0.0} for _, _, r in strat.calls)
    aliased = RecordingStrategy()
    run_backtest(aliased, panel, market=pd.DataFrame({"ts": DAYS[:4], "trend_state": -1}), costs=COSTS)
    assert all(r == {"market_trend_state": -1.0} for _, _, r in aliased.calls)
    none = RecordingStrategy()
    run_backtest(none, panel, costs=COSTS)
    assert all(r is None for _, _, r in none.calls)


def test_window_start_end_and_warmup():
    panel = make_bars("AAA", [FLAT] * 8)
    strat = RecordingStrategy()
    res = run_backtest(strat, panel, start=DAYS[3].date(), end=DAYS[6].date(), costs=COSTS)
    assert res.start == DAYS[3].date() and res.end == DAYS[6].date()
    assert len(res.equity) == 4
    assert [c[0] for c in strat.calls] == [d.date() for d in DAYS[3:6]]
    assert len(strat.calls[0][1:]) and strat.calls[0][1] == DAYS[3]  # history before start is still visible


# ----------------------------------------------------------------------------------------------- schemas & costs


def test_result_schemas():
    res = _run_one([FLAT, FLAT, (99.0, 100.0, 94.0, 96.0), FLAT])
    assert list(res.trades.columns) == TRADE_COLUMNS
    assert list(res.equity.columns) == EQUITY_COLUMNS
    assert res.equity.index.is_monotonic_increasing
    assert res.equity["equity"].iloc[0] == pytest.approx(res.initial_equity)
    assert res.equity["ret"].iloc[0] == 0.0
    assert res.n_signals == 1


def test_cost_model_math():
    cm = CostModel(slippage_bps=10.0)
    assert cm.fill_price(100.0, is_buy=True) == pytest.approx(100.10)
    assert cm.fill_price(100.0, is_buy=False) == pytest.approx(99.90)
    assert cm.regulatory_fees(10_000, 1_000_000.0) == pytest.approx(20.60 + 1.95)
    assert cm.regulatory_fees(100_000, 1_000_000.0) == pytest.approx(20.60 + 9.79)  # TAF capped
    assert cm.leg_fees(100, 10_000.0, is_sell=False) == 0.0
    sell_fill = 110.0 * (1 - 0.001)
    expected = (0.10 + 0.11) * 100 + sell_fill * 100 / 1e6 * 20.60 + 100 * 0.000195
    assert cm.round_trip_cost(100.0, 110.0, 100) == pytest.approx(expected)
    assert CostModel.large_cap().slippage_bps == 10.0 and CostModel.small_cap().slippage_bps == 20.0
    with_commission = CostModel(slippage_bps=0.0, commission_per_share=0.005)
    assert with_commission.leg_fees(200, 1.0, is_sell=False) == pytest.approx(1.0)


def test_trade_costs_reconcile_with_equity():
    res = _run_one([FLAT, FLAT, (99.0, 100.0, 94.0, 96.0), FLAT], costs=COSTS)
    t = res.trades.iloc[0]
    assert t["costs"] == pytest.approx(t["slippage_cost"] + t["fees"])
    assert res.final_equity == pytest.approx(res.initial_equity + t["pnl"])
