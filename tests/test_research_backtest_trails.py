"""Backtester trail hooks and extra exits (dd99dbe): chandelier, close-ATR, channel, give-back, profitable closes,
strategy ``trail_stop`` hook, engine-trail opt-out, ATR on the fly, rolling chandelier, size-floor universe."""
from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing_engine.core.models import Side
from swing_engine.features.indicators import atr
from swing_engine.research.backtest import (
    BacktestConfig,
    CostModel,
    ExitReason,
    OpenPosition,
    TrailingStop,
    _apply_trail_level,
    _ratchet_stop,
    chandelier_stop,
    run_backtest,
    size_floor_universe,
    strategy_engine_trail,
    strategy_trail_rule,
    with_atr_column,
)
from swing_engine.strategies.rsi2_meanrev import RSI2MeanRev
from tests.fixtures.research.strategies import ScriptedStrategy, long_signal
from tests.fixtures.research.synthetic_panel import make_bars, trading_dates

FREE = CostModel(slippage_bps=0.0, sec_fee_per_million_sold=0.0, finra_taf_per_share=0.0)
DAYS = trading_dates(8, "2024-01-02")
FLAT = (100.0, 101.0, 99.0, 100.0)
WIDE_STOP, FAR_TARGET = 80.0, 200.0
SHORT_STOP, SHORT_TARGET = 120.0, 50.0


def pos(side: Side = Side.LONG, *, entry=100.0, stop=90.0, best=None, last_close=None) -> OpenPosition:
    long = side == Side.LONG
    return OpenPosition(
        symbol="AAA", side=side, qty=10, entry_price=entry, entry_ts=DAYS[1], entry_idx=1, stop=stop,
        initial_stop=stop, target=None, strategy="t", score=1.0, risk_per_share=abs(entry - stop),
        last_close=entry if last_close is None else last_close,
        best_price=(entry if best is None else best), worst_price=entry if long else entry,
    )


def run(ohlc, *, side=Side.LONG, strategy=None, config=None, **cols):
    panel = make_bars("AAA", ohlc).assign(**cols)
    stop, target = (WIDE_STOP, FAR_TARGET) if side == Side.LONG else (SHORT_STOP, SHORT_TARGET)
    sig = long_signal("AAA", DAYS[0].date(), FLAT[3], stop, target, side=side)
    strat = strategy or ScriptedStrategy({})
    strat.by_date = {sig.as_of: [sig]}
    return run_backtest(strat, panel, costs=FREE, config=config or BacktestConfig(max_hold_bars=100))


# ----------------------------------------------------------------------------------------------- TrailingStop


def test_chandelier_preset():
    t = TrailingStop.chandelier()
    assert (t.atr_mult, t.atr_column) == (3.0, "atr_22")
    t = TrailingStop.chandelier(atr_mult=2.5, period=10)
    assert (t.atr_mult, t.atr_column) == (2.5, "atr_10")


@pytest.mark.parametrize(
    ("side", "trailing", "kw", "expected"),
    [
        # close-ATR: last close -/+ mult * atr
        (Side.LONG, TrailingStop(close_atr_mult=1.5), {"last_close": 110.0}, 107.0),
        (Side.SHORT, TrailingStop(close_atr_mult=1.5), {"stop": 110.0, "last_close": 90.0}, 93.0),
        # give-back: keep 75 % of the best open profit
        (Side.LONG, TrailingStop(giveback_pct=25.0), {"best": 120.0}, 115.0),
        (Side.SHORT, TrailingStop(giveback_pct=25.0), {"stop": 110.0, "best": 80.0}, 85.0),
    ],
)
def test_ratchet_extra_rules(side, trailing, kw, expected):
    p = pos(side, **kw)
    _ratchet_stop(p, trailing, atr=2.0)
    assert p.stop == pytest.approx(expected)


def test_ratchet_channel_long_and_short():
    p = pos(Side.LONG)
    _ratchet_stop(p, TrailingStop(channel_bars=3), atr=math.nan, channel=97.0)
    assert p.stop == 97.0
    s = pos(Side.SHORT, stop=110.0)
    _ratchet_stop(s, TrailingStop(channel_bars=3), atr=math.nan, channel=104.0)
    assert s.stop == 104.0
    _ratchet_stop(s, TrailingStop(channel_bars=3), atr=math.nan)  # NaN channel: no candidate
    assert s.stop == 104.0


def test_giveback_needs_open_profit_and_close_atr_needs_atr():
    p = pos(Side.LONG, best=100.0)  # best == entry: no profit to give back
    _ratchet_stop(p, TrailingStop(giveback_pct=25.0, close_atr_mult=1.0), atr=math.nan)
    assert p.stop == 90.0


@pytest.mark.parametrize("side", [Side.LONG, Side.SHORT])
def test_ratchet_never_loosens(side):
    long = side == Side.LONG
    tight = 118.0 if long else 82.0
    p = pos(side, stop=tight, best=120.0 if long else 80.0)
    _ratchet_stop(p, TrailingStop(giveback_pct=25.0), atr=2.0)  # candidate 115 / 85 is looser
    assert p.stop == tight


def test_chandelier_in_run_backtest_computes_missing_atr_column():
    bars = [FLAT, FLAT, (100.0, 110.0, 99.0, 109.0), (109.0, 109.5, 104.0, 105.0), FLAT, FLAT]
    panel = make_bars("AAA", bars)
    a3 = atr(panel["high"], panel["low"], panel["close"], 3)
    cfg = BacktestConfig(max_hold_bars=100, trailing=TrailingStop.chandelier(atr_mult=1.0, period=3))
    res = run(bars, config=cfg)
    t = res.trades.iloc[0]
    expected = 110.0 - a3.iloc[2]  # highest high since entry (bar 2) - ATR(3) at that close
    assert t["exit_reason"] == ExitReason.TRAIL_STOP and t["exit_ts"] == DAYS[3]
    assert t["exit_price"] == pytest.approx(expected) == pytest.approx(105.0)  # ATR(3) = 5.0 at bar 2


def test_channel_bars_in_run_backtest_long_and_short():
    up = [FLAT, FLAT, (101.0, 104.0, 100.5, 103.0), (103.0, 106.0, 102.0, 105.0), (104.0, 104.5, 101.0, 102.0)]
    t = run(up, config=BacktestConfig(max_hold_bars=100, trailing=TrailingStop(channel_bars=2))).trades.iloc[0]
    # close of bar 3: lowest low of bars 2-3 = 100.5; bar 4 low 101 does not reach it
    assert t["exit_reason"] == ExitReason.END and t["stop"] == pytest.approx(101.0)  # bar 4 itself ratchets to 101
    down = [FLAT, FLAT, (99.0, 99.5, 96.0, 97.0), (97.0, 98.0, 94.0, 95.0), (96.0, 99.6, 95.5, 98.0)]
    t = run(down, side=Side.SHORT, config=BacktestConfig(max_hold_bars=100, trailing=TrailingStop(channel_bars=2)))
    t = t.trades.iloc[0]
    assert t["exit_reason"] == ExitReason.TRAIL_STOP and t["exit_ts"] == DAYS[4]
    assert t["exit_price"] == pytest.approx(99.5)  # highest high of bars 2-3


# ----------------------------------------------------------------------------------------------- profitable closes


def test_profitable_closes_exit_long_and_short():
    cfg = BacktestConfig(max_hold_bars=100, profitable_closes=2)
    up = [FLAT, (100.0, 102.0, 99.0, 101.0), (101.0, 101.5, 99.0, 99.5), (100.0, 103.0, 99.0, 102.0), FLAT]
    t = run(up, config=cfg).trades.iloc[0]
    assert t["exit_reason"] == ExitReason.PROFITABLE_CLOSES and t["exit_ts"] == DAYS[3]
    assert t["exit_price"] == pytest.approx(102.0)
    down = [FLAT, (100.0, 101.0, 98.0, 99.0), (99.0, 101.0, 98.5, 100.5), (100.0, 101.0, 97.0, 98.0), FLAT]
    t = run(down, side=Side.SHORT, config=cfg).trades.iloc[0]
    assert t["exit_reason"] == ExitReason.PROFITABLE_CLOSES and t["exit_ts"] == DAYS[3]
    assert t["exit_price"] == pytest.approx(98.0)


def test_profitable_closes_off_by_default():
    up = [FLAT] + [(100.0, 102.0, 99.0, 101.0)] * 5
    assert run(up).trades.iloc[0]["exit_reason"] == ExitReason.END


# ----------------------------------------------------------------------------------------------- strategy trail


@pytest.mark.parametrize(
    ("side", "stop", "close", "level", "expected"),
    [
        (Side.LONG, 90.0, 105.0, 95.0, 95.0),  # tightens
        (Side.LONG, 96.0, 105.0, 95.0, 96.0),  # never loosens
        (Side.LONG, 90.0, 105.0, 105.0, 90.0),  # never at the close
        (Side.LONG, 90.0, 105.0, 106.0, 90.0),  # never through the close
        (Side.SHORT, 110.0, 95.0, 105.0, 105.0),
        (Side.SHORT, 104.0, 95.0, 105.0, 104.0),
        (Side.SHORT, 110.0, 95.0, 95.0, 110.0),
        (Side.SHORT, 110.0, 95.0, 94.0, 110.0),
    ],
)
def test_apply_trail_level(side, stop, close, level, expected):
    p = pos(side, stop=stop)
    _apply_trail_level(p, level, close)
    assert p.stop == expected


@pytest.mark.parametrize("bad", [None, "x", math.nan, math.inf, 0.0, -5.0])
def test_apply_trail_level_ignores_bad_levels(bad):
    p = pos(Side.LONG)
    _apply_trail_level(p, bad, 105.0)
    assert p.stop == 90.0


TRAIL_BARS = [FLAT, FLAT, (101.0, 106.0, 100.0, 105.0), (105.0, 107.0, 101.5, 106.0), (105.0, 106.0, 102.0, 104.0)]
TRAIL_LEVELS = [np.nan, 95.0, 101.0, 103.0, 103.0]


def test_config_trail_rule_ratchets_and_exits():
    cfg = BacktestConfig(max_hold_bars=100, trail_rule=lambda row: row["st"])
    t = run(TRAIL_BARS, config=cfg, st=TRAIL_LEVELS).trades.iloc[0]
    # 101 after bar 2, 103 after bar 3's close; bar 4 (low 102) hits it
    assert t["exit_reason"] == ExitReason.TRAIL_STOP and t["exit_ts"] == DAYS[4]
    assert t["exit_price"] == pytest.approx(103.0)


def test_strategy_trail_stop_hook_is_picked_up():
    strat = ScriptedStrategy({})
    strat.trail_stop = lambda row: row["st"]
    assert strategy_trail_rule(strat) is strat.trail_stop
    t = run(TRAIL_BARS, strategy=strat, st=TRAIL_LEVELS).trades.iloc[0]
    assert t["exit_reason"] == ExitReason.TRAIL_STOP and t["exit_price"] == pytest.approx(103.0)


def test_short_strategy_trail():
    bars = [FLAT, FLAT, (99.0, 100.0, 94.0, 95.0), (95.0, 98.5, 93.0, 94.0), (95.0, 98.0, 94.0, 96.0)]
    cfg = BacktestConfig(max_hold_bars=100, trail_rule=lambda row: row["st"])
    t = run(bars, side=Side.SHORT, config=cfg, st=[np.nan, 105.0, 99.0, 97.0, 97.0]).trades.iloc[0]
    assert t["exit_reason"] == ExitReason.TRAIL_STOP and t["exit_ts"] == DAYS[4]
    assert t["exit_price"] == pytest.approx(97.0)


class _PanelTrail(RSI2MeanRev):
    def trail_stop(self, row):
        return 1.0


def test_strategy_trail_rule_skips_default_hook():
    assert strategy_trail_rule(RSI2MeanRev()) is None  # PanelStrategy default no-op
    assert strategy_trail_rule(ScriptedStrategy({})) is None  # no hook at all
    hook = strategy_trail_rule(_PanelTrail())
    assert hook is not None and hook(None) == 1.0


# ----------------------------------------------------------------------------------------------- engine trail opt-out


def test_strategy_engine_trail_params_over_attr():
    s = RSI2MeanRev()
    assert strategy_engine_trail(s) is True
    s.engine_trail = False
    assert strategy_engine_trail(s) is False
    s.params["engine_trail"] = True
    assert strategy_engine_trail(s) is True
    s.engine_trail = True
    s.params["engine_trail"] = False
    assert strategy_engine_trail(s) is False
    s.params["engine_trail"] = None  # None defers to the attribute
    assert strategy_engine_trail(s) is True
    assert strategy_engine_trail(object()) is True


def test_engine_trail_false_drops_config_trailing():
    bars = [FLAT, FLAT, (105.0, 110.0, 104.0, 109.0), (110.0, 120.0, 109.0, 118.0), (117.0, 118.0, 112.0, 113.0)]
    cfg = BacktestConfig(max_hold_bars=100, trailing=TrailingStop(pct=5.0))
    assert run(bars, config=cfg).trades.iloc[0]["exit_reason"] == ExitReason.TRAIL_STOP

    off = ScriptedStrategy({})
    off.engine_trail = False
    res = run(bars, strategy=off, config=cfg)
    assert res.config.trailing is None
    assert res.trades.iloc[0]["exit_reason"] == ExitReason.END and res.trades.iloc[0]["stop"] == WIDE_STOP

    back_on = ScriptedStrategy({}, {"engine_trail": True})
    back_on.engine_trail = False  # the param wins
    assert run(bars, strategy=back_on, config=cfg).trades.iloc[0]["exit_reason"] == ExitReason.TRAIL_STOP


def test_engine_trail_false_keeps_strategy_trail():
    strat = ScriptedStrategy({}, {"engine_trail": False})
    strat.trail_stop = lambda row: row["st"]
    cfg = BacktestConfig(max_hold_bars=100, trailing=TrailingStop(pct=1.0))
    t = run(TRAIL_BARS, strategy=strat, config=cfg, st=TRAIL_LEVELS).trades.iloc[0]
    assert t["exit_reason"] == ExitReason.TRAIL_STOP and t["exit_price"] == pytest.approx(103.0)


# ----------------------------------------------------------------------------------------------- ATR / chandelier helpers


def _two_symbols() -> pd.DataFrame:
    rng = np.random.default_rng(3)
    parts = []
    for sym in ("AAA", "BBB"):
        c = 100 + np.cumsum(rng.normal(0, 1, 30))
        parts.append(make_bars(sym, [(x, x + 1.5, x - 1.0, x + 0.2) for x in c]))
    return pd.concat(parts, ignore_index=True).sample(frac=1.0, random_state=0)  # shuffled rows


def test_with_atr_column_per_symbol_and_causal():
    panel = _two_symbols()
    out = with_atr_column(panel, "atr_5")
    for sym, g in out.groupby("symbol"):
        g = g.sort_values("ts")
        exp = atr(g["high"], g["low"], g["close"], 5)
        pd.testing.assert_series_equal(g["atr_5"], exp, check_names=False)
        head = with_atr_column(panel[(panel["symbol"] == sym) & (panel["ts"] <= g["ts"].iloc[14])], "atr_5")
        np.testing.assert_allclose(head.sort_values("ts")["atr_5"].to_numpy(), exp.iloc[:15].to_numpy())
    assert with_atr_column(panel, "atr_14") is panel  # already present
    assert with_atr_column(panel, "foo") is panel  # not an atr_<n> name


def test_chandelier_stop_matches_rolling_formula():
    panel = _two_symbols()
    out = chandelier_stop(panel, period=4, atr_mult=2.0)
    for _sym, g in panel.groupby("symbol"):
        g = g.sort_values("ts")
        exp = g["high"].rolling(4).max() - 2.0 * atr(g["high"], g["low"], g["close"], 4)
        pd.testing.assert_series_equal(out.loc[g.index], exp, check_names=False)
        assert out.loc[g.index].iloc[:3].isna().all()


# ----------------------------------------------------------------------------------------------- size floor


def _sized(days, rows) -> pd.DataFrame:
    return pd.DataFrame(
        [{"symbol": s, "ts": days[d], "cap": cap, **extra} for d, s, cap, extra in rows]
    )


def test_size_floor_universe_per_day_breakpoint():
    days = trading_dates(2, "2024-01-02")
    rows = [(0, s, cap, {}) for s, cap in zip("ABCDE", (1, 2, 3, 4, 5), strict=True)]
    rows += [(1, s, cap, {}) for s, cap in zip("ABCDE", (50, 40, 30, 20, 10), strict=True)]
    u = size_floor_universe(_sized(days, rows), "cap", pctile=40.0)
    # 40th pct of [1..5] = 2.6 -> C, D, E; day 2 reversed -> A, B, C
    assert u(days[0].date()) == frozenset("CDE")
    assert u(days[1].date()) == frozenset("ABC")
    assert u(date(2030, 1, 1)) == frozenset()


def test_size_floor_universe_is_point_in_time():
    days = trading_dates(3, "2024-01-02")
    rows = [(d, s, cap * (d + 1) ** 3 if s == "A" else cap, {}) for d in range(3)
            for s, cap in zip("ABCD", (1, 2, 3, 4), strict=True)]
    full = _sized(days, rows)
    u_full = size_floor_universe(full, "cap", pctile=50.0)
    for d in range(3):
        upto = full[full["ts"] <= days[d]]
        assert size_floor_universe(upto, "cap", pctile=50.0)(days[d].date()) == u_full(days[d].date())
    assert "A" not in u_full(days[0].date()) and "A" in u_full(days[2].date())  # A only qualifies after growing


def test_size_floor_universe_uses_nyse_breakpoint():
    days = trading_dates(1, "2024-01-02")
    rows = [(0, "N1", 100, {"exchange": "NYSE"}), (0, "N2", 200, {"exchange": "NYSE"}),
            (0, "Q1", 1, {"exchange": "NASDAQ"}), (0, "Q2", 150, {"exchange": "NASDAQ"})]
    u = size_floor_universe(_sized(days, rows), "cap", pctile=50.0)  # NYSE median 150
    assert u(days[0].date()) == frozenset({"N2", "Q2"})


def test_size_floor_universe_missing_column():
    with pytest.raises(KeyError):
        size_floor_universe(pd.DataFrame({"symbol": ["A"], "ts": [DAYS[0]]}), "cap")


def test_size_floor_universe_gates_run_backtest():
    bars = [FLAT] * 4
    panel = pd.concat([make_bars("AAA", bars).assign(cap=1.0), make_bars("BBB", bars).assign(cap=9.0)])
    sigs = [long_signal(s, DAYS[0].date(), 100.0, WIDE_STOP, FAR_TARGET) for s in ("AAA", "BBB")]
    res = run_backtest(ScriptedStrategy({DAYS[0].date(): sigs}), panel, costs=FREE,
                       universe_at=size_floor_universe(panel, "cap", pctile=50.0))
    assert res.trades["symbol"].tolist() == ["BBB"] and res.skip_reasons["not_in_universe"] == 1


def test_size_floor_nyse_choice_is_per_day():
    """A session without NYSE rows falls back to its own rows; later NYSE rows must not change it."""
    days = trading_dates(2, "2024-01-02")
    rows = [(0, s, cap, {"exchange": "NASDAQ"}) for s, cap in zip("ABCD", (1, 2, 3, 4), strict=True)]
    rows += [(1, "N1", 100, {"exchange": "NYSE"}), (1, "Q1", 1, {"exchange": "NASDAQ"})]
    full = _sized(days, rows)
    day0 = days[0].date()
    assert size_floor_universe(full, "cap", 50.0)(day0) == size_floor_universe(full.iloc[:4], "cap", 50.0)(day0)
    assert size_floor_universe(full, "cap", 50.0)(day0) == frozenset("CD")
    assert size_floor_universe(full, "cap", 50.0)(days[1].date()) == frozenset({"N1"})
