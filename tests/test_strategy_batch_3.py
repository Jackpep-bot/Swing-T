"""Catalog batch 3 strategies: generic contract checks plus a hand-built fire / no-fire case and geometry for each."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.core.models import EntryType
from swing_engine.strategies._catalog3 import is_week_end, month_offsets
from swing_engine.strategies.derrico_price_swing import upswing
from swing_engine.strategies.gandalf_project_research_system import gandalf_buy
from tests import test_strategies_common as common
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, last_date, make_bars, make_panel

BATCH = [
    "turn_of_month", "high_turnover_short_term_momentum", "xs_momentum_rank", "bollinger_w_bottom_ii_reversal",
    "calhoun_mean_reversion_swing", "connors_pctb", "derrico_price_swing", "gandalf_project_research_system",
    "inside_outside_bar_breakout", "kaufman_three_period_divergence", "momentum_pinball", "pivot_extension_reversal",
    "rsi_trend_zigzag_luo", "trendline_break", "williams_smash_day", "ehlers_dsp_family", "katsanos_stiffness",
    "parabolic_sar_reversal", "slope_performance_trend", "weinstein_stage2_breakout",
]
FLAT = [100.0, 100.5, 99.5, 100.0, 1e6]


def strat(name: str, **params):
    return registry.get("strategy", name)(params or None)


def panel_of(rows, symbol: str = "AAA", start: str = "2024-01-02", **cols) -> pd.DataFrame:
    """Fixture features for hand-built (open, high, low, close, volume) rows; `cols` overwrite or add columns
    (a scalar for every row, or a {position: value} dict on top of a base value given as `(base, {pos: v})`)."""
    p = add_features(bars_from_ohlc(symbol, rows, start=start))
    for name, val in cols.items():
        base, at = val if isinstance(val, tuple) else (val, {})
        arr = np.full(len(p), float(base))
        for i, v in at.items():
            arr[i] = v
        p[name] = arr
    return p


def check_geometry(sigs) -> None:
    for s in sigs:
        assert s.stop < s.entry
        if s.target is not None:
            assert s.target > s.entry


# ----------------------------------------------------------------------------------------------- generic contract
@pytest.fixture(scope="module")
def spy_panel() -> pd.DataFrame:
    return make_panel(("AAA", "BBB", "CCC", "SPY"), n_days=320, seed=11)  # SPY = market proxy for RS features


def test_batch_registered():
    assert set(BATCH) <= set(registry.names("strategy"))


@pytest.mark.parametrize("name", BATCH)
def test_generic_contract(name, spy_panel):
    common.test_defaults_params_and_required_features(name)
    common.test_generator_panel_has_required_columns(name, spy_panel)
    common.test_signals_are_well_formed_and_point_in_time(name, spy_panel)


def test_calendar_helpers():
    assert month_offsets(date(2024, 1, 31)) == (21, -1)
    assert month_offsets(date(2024, 3, 28)) == (20, -1)  # Good Friday 2024-03-29 is a holiday
    assert month_offsets(date(2024, 3, 29)) == (0, 0)
    assert is_week_end(date(2024, 10, 11)) and not is_week_end(date(2024, 10, 10)) and is_week_end(date(2024, 3, 28))


# ----------------------------------------------------------------------------------------------- calendar / factor
def test_turn_of_month():
    p = add_features(make_bars(("SPY", "AAA"), n_days=40, seed=3))
    sigs = strat("turn_of_month").signals(p, date(2024, 1, 30))  # day -2 of January 2024
    assert [s.symbol for s in sigs] == ["SPY"]
    check_geometry(sigs)
    assert sigs[0].target is None and strat("turn_of_month").params["max_hold_days"] == 4
    assert {s.symbol for s in strat("turn_of_month", symbols=None).signals(p, date(2024, 1, 30))} == {"SPY", "AAA"}
    assert strat("turn_of_month").signals(p, date(2024, 1, 31)) == []


def _month_panel(n_sym: int = 10) -> pd.DataFrame:
    syms = ["AAA", *(f"S{i:02d}" for i in range(n_sym - 1))]
    return add_features(make_bars(syms, n_days=40, seed=5))


def test_xs_momentum_rank():
    p = _month_panel()
    p["mom_12_1_rank"] = np.where(p["symbol"] == "AAA", 0.95, 0.5)
    s = strat("xs_momentum_rank")
    sigs = s.signals(p, date(2024, 1, 31))  # last session of January
    assert [x.symbol for x in sigs] == ["AAA"]
    check_geometry(sigs)
    assert s.signals(p, date(2024, 1, 30)) == []
    assert s.should_exit(pd.Series({"mom_12_1_rank": 0.6}), 3)
    assert not s.should_exit(pd.Series({"mom_12_1_rank": 0.8}), 3)


def test_high_turnover_short_term_momentum():
    p = _month_panel()
    aaa = p["symbol"] == "AAA"
    p["ret_21d"] = np.where(aaa, 0.3, p["symbol"].str[-1].map(lambda c: int(c) / 100 if c.isdigit() else 0.0))
    p["sma_252_of_volume"] = 1e6
    p["sma_21_of_volume"] = np.where(aaa, 3e6, 1e6)
    s = strat("high_turnover_short_term_momentum")
    sigs = s.signals(p, date(2024, 1, 31))
    assert [x.symbol for x in sigs] == ["AAA"] and sigs[0].features["turnover_source"] == 0.0
    check_geometry(sigs)
    assert s.signals(p, date(2024, 1, 30)) == []
    p["sma_21_of_volume"] = 1e6  # relative proxy no longer separates AAA ...
    assert s.signals(p, date(2024, 1, 31)) == []
    p["turnover"] = np.where(aaa, 0.05, 0.01)  # ... but the EDGAR turnover column does when present
    sigs = s.signals(p, date(2024, 1, 31))
    assert [x.symbol for x in sigs] == ["AAA"] and sigs[0].features["turnover_source"] == 1.0


# ----------------------------------------------------------------------------------------------- mean reversion
def test_bollinger_method3():
    rows = [FLAT] * 28 + [[100, 100.2, 97.5, 98.5, 1e6], [98.6, 101.0, 98.4, 100.9, 1e6]]
    p = panel_of(rows, bb_lower_20=98.0, bb_upper_20=110.0, ii_pct_21=5.0, bb_pctb_20=0.5, trend_state=0)
    sigs = strat("bollinger_w_bottom_ii_reversal").signals(p, last_date(p))
    assert len(sigs) == 1 and sigs[0].target == 110.0 and sigs[0].stop < 97.5
    check_geometry(sigs)
    p["ii_pct_21"] = -5.0  # tag without accumulation is not an alert
    assert strat("bollinger_w_bottom_ii_reversal").signals(p, last_date(p)) == []


def test_bollinger_w_bottom():
    rows = [FLAT] * 10 + [
        [97, 97.5, 95.0, 96, 1e6],  # 10: first low, outside the band
        [96, 99, 96.5, 98.5, 1e6], [98.5, 101, 98, 100, 1e6], [100, 100.5, 98.5, 99, 1e6], [99, 99.5, 97.5, 98, 1e6],
        [98, 98.5, 96.5, 97, 1e6], [97, 97.5, 96.2, 96.5, 1e6], [96.5, 97.5, 96.3, 97, 1e6],
        [97, 97.5, 96.4, 96.8, 1e6], [96.8, 97.2, 96.1, 96.5, 1e6],
        [96.5, 97, 95.5, 96.8, 1e6],  # 20: retest, inside the band
        [96.8, 98, 96.0, 97.5, 1e6], [97.5, 99, 96.5, 98.5, 1e6], [98.5, 100, 97, 99.5, 1e6],
        [99.5, 100.5, 97.5, 100, 1e6], [100, 100.8, 98, 100.5, 1e6],
        [100.5, 102.5, 99.8, 102.2, 1e6],  # 26: first close above the 101 peak between the lows
    ]
    p = panel_of(rows, bb_lower_20=96.0, bb_upper_20=115.0, ii_pct_21=1.0, bb_pctb_20=(0.5, {10: -0.1, 20: 0.2}),
                 trend_state=0)
    s = strat("bollinger_w_bottom_ii_reversal", variant="w_bottom")
    sigs = s.signals(p, last_date(p))
    assert len(sigs) == 1 and sigs[0].features["setup_low"] == 95.5
    check_geometry(sigs)
    p["bb_pctb_20"] = 0.5  # first low not outside the band -> no W
    assert s.signals(p, last_date(p)) == []


def test_calhoun_mean_reversion_swing():
    rows = []
    for i in range(26):  # leg: low 100 at bar 0 to high 120 at bar 25
        c = 100.5 + i * 0.76
        rows.append([c - 0.3, c + 0.5, c - 0.5, c, 1e6])
    for c in (118, 116, 114, 112):
        rows.append([c + 1, c + 1.2, c - 0.4, c, 1e6])
    rows += [[111, 111.2, 110.0, 110.4, 1e6], [110.4, 110.9, 110.2, 110.7, 1e6]]  # pullback low 110 = 50%; bounce
    p = panel_of(rows, trend_state=0)
    sigs = strat("calhoun_mean_reversion_swing").signals(p, last_date(p))
    assert len(sigs) == 1 and sigs[0].target == pytest.approx(120.0) and sigs[0].stop < 110.0
    check_geometry(sigs)
    assert strat("calhoun_mean_reversion_swing", retrace=0.382).signals(p, last_date(p)) == []


def test_connors_pctb():
    p = panel_of([FLAT] * 30, sma_200=90.0, bb_pctb_20=(0.5, {27: 0.1, 28: 0.15, 29: 0.05}))
    s = strat("connors_pctb")
    sigs = s.signals(p, last_date(p))
    assert len(sigs) == 1 and sigs[0].target is None
    check_geometry(sigs)
    p.loc[p.index[28], "bb_pctb_20"] = 0.3
    assert s.signals(p, last_date(p)) == []
    assert s.should_exit(pd.Series({"bb_pctb_20": 0.85}), 2) and not s.should_exit(pd.Series({"bb_pctb_20": 0.5}), 2)


def test_derrico_price_swing():
    w = {"low": np.array([10, 9, 9.5]), "close": np.array([10, 9.5, 10.5]), "bb_lower_20": np.array([9.8, 9.8, 9.8]),
         "rsi_14": np.array([45, 38, 39])}
    assert upswing(w, 2, 1, 40) and upswing(w, 2, 2, 40) and not upswing(w, 2, 3, 40) and upswing(w, 2, 4, 40)
    p = panel_of([FLAT] * 30, trend_state=0, rsi_14=(50.0, {28: 38.0, 29: 42.0}))
    sigs = strat("derrico_price_swing").signals(p, last_date(p))
    assert len(sigs) == 1
    check_geometry(sigs)
    assert strat("derrico_price_swing").signals(p, p["ts"].iloc[-2].date()) == []  # rsi 38 is not a cross


def test_gandalf_project_research_system():
    set_a = [[10, 10, 10, 10, 1e6], [10, 10.5, 9.5, 10, 1e6], [10, 12, 9, 9.5, 1e6], [9.5, 10, 9.4, 9.8, 1e6]]
    assert gandalf_buy({k: np.array([r[i] for r in set_a]) for i, k in enumerate(("open", "high", "low", "close"))})
    flat = [[10, 10, 10, 10, 1e6]] * 4
    assert not gandalf_buy({k: np.array([r[i] for r in flat]) for i, k in enumerate(("open", "high", "low", "close"))})
    p = panel_of([FLAT] * 20 + set_a, trend_state=1)
    sigs = strat("gandalf_project_research_system").signals(p, last_date(p))
    assert len(sigs) == 1 and sigs[0].target is None
    check_geometry(sigs)


# ----------------------------------------------------------------------------------------------- bar patterns
def test_inside_outside_bar_breakout():
    mother = [100, 105, 95, 102, 1e6]
    p = panel_of([FLAT] * 20 + [mother, [101, 104, 97, 103, 1e6]], trend_state=1)
    sigs = strat("inside_outside_bar_breakout").signals(p, last_date(p))
    assert len(sigs) == 1 and sigs[0].entry_type == EntryType.STOP
    assert (sigs[0].entry, sigs[0].stop, sigs[0].target) == (104.0, 97.0, 118.0)
    built = strat("inside_outside_bar_breakout", variant="inside_builtin").signals(p, last_date(p))
    assert built[0].entry_type == EntryType.OPEN and built[0].entry == 103.0
    assert strat("inside_outside_bar_breakout", variant="outside").signals(p, last_date(p)) == []
    out = panel_of([FLAT] * 20 + [mother, [100, 106, 94, 105.5, 1e6]], trend_state=1)
    o = strat("inside_outside_bar_breakout", variant="outside").signals(out, last_date(out))
    assert len(o) == 1 and o[0].entry == 106.0 and o[0].stop == 94.0
    assert strat("inside_outside_bar_breakout").signals(out, last_date(out)) == []
    check_geometry([*sigs, *built, *o])


def _slopes(p: pd.DataFrame, price: tuple, mom: tuple) -> pd.DataFrame:
    """Set the six Kaufman slope columns: (value before, value on the last two bars)."""
    for n in (5, 10, 15):
        p[f"linreg_slope_{n}"] = price[0]
        p[f"linreg_slope_{n}_of_stoch_k_14"] = mom[0]
        p.loc[p.index[-1], f"linreg_slope_{n}"] = price[1]
        p.loc[p.index[-1], f"linreg_slope_{n}_of_stoch_k_14"] = mom[1]
    return p


def test_kaufman_three_period_divergence():
    p = _slopes(panel_of([FLAT] * 30, trend_state=0), price=(1.0, 1.0), mom=(1.0, -1.0))
    s = strat("kaufman_three_period_divergence")
    sigs = s.signals(p, last_date(p))
    assert len(sigs) == 1
    check_geometry(sigs)
    assert strat("kaufman_three_period_divergence", variant="textbook").signals(p, last_date(p)) == []
    p = _slopes(p, price=(1.0, 1.0), mom=(-1.0, -1.0))  # divergence already present the bar before
    assert s.signals(p, last_date(p)) == []
    agree = pd.Series({c: 1.0 for c in s.required_features()})
    split = agree.copy()
    split["linreg_slope_15_of_stoch_k_14"] = -1.0
    assert s.should_exit(agree, 3) and not s.should_exit(split, 3)


def test_momentum_pinball():
    p = panel_of([FLAT] * 30, lbr_rsi_3=(50.0, {29: 20.0}), atr_pct_14=0.03)
    sigs = strat("momentum_pinball").signals(p, last_date(p))
    assert len(sigs) == 1 and sigs[0].entry_type == EntryType.STOP
    assert (sigs[0].entry, sigs[0].stop) == (100.5, 99.5) and sigs[0].features["approx_daily"] == 1.0
    p["atr_pct_14"] = 0.01  # not enough daily range
    assert strat("momentum_pinball").signals(p, last_date(p)) == []


def test_pivot_extension_reversal():
    lows = [99.5] * 20 + [99, 98.5, 98, 97.5, 95, 96, 96.5]
    p = panel_of([[lo + 1, lo + 2, lo, lo + 1, 1e6] for lo in lows], trend_state=0)
    s = strat("pivot_extension_reversal")
    sigs = s.signals(p, last_date(p))
    assert len(sigs) == 1 and sigs[0].features["pivot_low"] == 95.0
    check_geometry(sigs)
    assert s.signals(p, p["ts"].iloc[-2].date()) == []  # one right-side bar only: not confirmed yet


def test_williams_smash_day():
    base = [FLAT] * 20
    smash = [99.8, 100.0, 98.0, 98.2, 1e6]  # close 98.2 < prior low 99.5: naked smash
    p = panel_of(base + [smash], trend_state=1, sma_50=90.0)
    s = strat("williams_smash_day")
    sigs = s.signals(p, last_date(p))
    assert len(sigs) == 1 and sigs[0].entry_type == EntryType.STOP
    assert (sigs[0].entry, sigs[0].stop) == (100.01, 97.99)
    quiet = panel_of(base + [smash, [98.2, 99.5, 98.1, 99.0, 1e6]], trend_state=1, sma_50=90.0)
    assert s.signals(quiet, last_date(quiet))[0].entry == 100.01  # order re-issued while untriggered
    hit = panel_of(base + [smash, [98.2, 100.5, 98.1, 100.2, 1e6]], trend_state=1, sma_50=90.0)
    assert s.signals(hit, last_date(hit)) == []  # already triggered
    assert s.signals(panel_of(base + [smash], trend_state=0, sma_50=90.0), last_date(p)) == []  # trend gate


def test_trendline_break():
    rows = [[97, 99, 96.5, 98, 1e6]] * 10 + [[100, 110, 99, 101, 1e6]] + [[97, 99, 96.5, 98, 1e6]] * 11
    rows += [[100, 105, 98, 99, 1e6]] + [[97, 99, 96.5, 98, 1e6]] * 12 + [[98, 101.5, 97.5, 101, 1e6]]
    p = panel_of(rows, trend_state=0)
    s = strat("trendline_break", min_reward_risk=0.5)
    sigs = s.signals(p, last_date(p))
    assert len(sigs) == 1 and sigs[0].target == 105.0  # nearest confirmed pivot high above the entry
    assert sigs[0].features["tl_value"] == pytest.approx(105 - 5 / 12 * 13)
    check_geometry(sigs)
    assert strat("trendline_break").signals(p, last_date(p)) == []  # 105 target is < 2R at the card default
    rows[-1] = [98, 99.4, 97.5, 99.2, 1e6]  # close stays under the line
    assert s.signals(panel_of(rows, trend_state=0), last_date(p)) == []


def test_rsi_trend_zigzag_luo():
    p = panel_of([FLAT] * 30, zz_trend_5=1.0, zz_high_5=120.0, zz_low_5=95.0, rsi_14=31.0, prev_rsi_14=29.0)
    s = strat("rsi_trend_zigzag_luo")
    sigs = s.signals(p, last_date(p))
    assert len(sigs) == 1 and sigs[0].target == 120.0 and sigs[0].stop <= 95.0
    check_geometry(sigs)
    p["zz_trend_5"] = 0.0
    assert s.signals(p, last_date(p)) == []
    assert s.should_exit(pd.Series({"zz_trend_5": 0.0, "rsi_14": 50.0, "prev_rsi_14": 50.0}), 1)
    assert s.should_exit(pd.Series({"zz_trend_5": 1.0, "rsi_14": 68.0, "prev_rsi_14": 72.0}), 1)
    assert not s.should_exit(pd.Series({"zz_trend_5": 1.0, "rsi_14": 60.0, "prev_rsi_14": 55.0}), 1)


# ----------------------------------------------------------------------------------------------- indicator systems
def test_ehlers_dsp_family():
    roof = {"roof_48_10": (0.5, {28: -0.1, 29: 0.2}), "max_20_of_roof_48_10": 1.0, "min_20_of_roof_48_10": -1.0}
    p = panel_of([FLAT] * 30, **roof)
    s = strat("ehlers_dsp_family")
    sigs = s.signals(p, last_date(p))
    assert len(sigs) == 1 and sigs[0].reward_risk == pytest.approx(3.0)
    assert strat("ehlers_dsp_family", mode="reversal").signals(p, last_date(p)) == []
    assert s.should_exit(pd.Series({"roof_48_10": -0.1}), 2)
    stoch = panel_of([FLAT] * 30, **{**roof, "roof_48_10": (0.5, {28: -0.7, 29: -0.5})})  # %K 0.15 -> 0.25
    st = strat("ehlers_dsp_family", variant="ehlers_stoch", mode="reversal").signals(stoch, last_date(stoch))
    assert st == []
    st = strat("ehlers_dsp_family", variant="ehlers_stoch").signals(stoch, last_date(stoch))
    assert len(st) == 1
    check_geometry([*sigs, *st])


def test_katsanos_stiffness():
    rising = {i: 100.0 + i for i in range(30)}
    p = panel_of([FLAT] * 30, stiffness_60_100=(80.0, {29: 92.0}), ema_100_of_market_close=(0.0, rising))
    s = strat("katsanos_stiffness")
    sigs = s.signals(p, last_date(p))
    assert len(sigs) == 1 and sigs[0].target is None
    check_geometry(sigs)
    p["ema_100_of_market_close"] = 100.0  # index EMA flat
    assert s.signals(p, last_date(p)) == []
    assert len(strat("katsanos_stiffness", market_ema_col=None).signals(p, last_date(p))) == 1
    assert s.should_exit(pd.Series({"stiffness_60_100": 45.0}), 10)


def test_parabolic_sar_reversal():
    lows = [99.5] * 25 + [98, 97, 96.5, 97.2, 97.5]
    rows = [[lo + 0.5, lo + 1, lo, lo + 0.5, 1e6] for lo in lows]
    p = panel_of(rows, trend_state=0, psar_dir=(1.0, {i: -1.0 for i in range(25, 30)}), psar=101.0, atr_3=1.0)
    s = strat("parabolic_sar_reversal")
    sigs = s.signals(p, last_date(p))
    assert len(sigs) == 1 and sigs[0].entry_type == EntryType.STOP
    assert (sigs[0].entry, sigs[0].stop) == (101.0, 96.5)  # stop = short leg's extreme point
    assert strat("parabolic_sar_reversal", first_stop_atr3_mult=1.5).signals(p, last_date(p))[0].stop == 96.0
    check_geometry(sigs)
    p["psar_dir"] = 1.0
    assert s.signals(p, last_date(p)) == []
    assert s.trail_stop(pd.Series({"psar": 99.0, "psar_dir": 1.0})) == 99.0
    assert s.trail_stop(pd.Series({"psar": 99.0, "psar_dir": -1.0})) is None


def test_slope_performance_trend():
    seq = {i: -1.0 for i in range(10, 20)} | {i: 1.0 for i in range(20, 25)} | {29: 1.0}
    p = panel_of([FLAT] * 30, linreg_slope_252=(1.0, seq), linreg_slope_252_of_rs_line=(-1.0, {**seq, 20: -1.0}))
    # state: both < 0 on bars 10-19, mixed 20-28 (rel slope negative on 20, price slope positive), both > 0 on 29
    p.loc[p.index[20:29], "linreg_slope_252_of_rs_line"] = -1.0
    s = strat("slope_performance_trend")
    sigs = s.signals(p, last_date(p))
    assert len(sigs) == 1
    check_geometry(sigs)
    p.loc[p.index[22], "linreg_slope_252_of_rs_line"] = 1.0  # an earlier both-positive state: already long
    assert s.signals(p, last_date(p)) == []
    assert s.should_exit(pd.Series({"linreg_slope_252": -1.0, "linreg_slope_252_of_rs_line": -2.0}), 5)
    assert not s.should_exit(pd.Series({"linreg_slope_252": 1.0, "linreg_slope_252_of_rs_line": -2.0}), 5)


def test_weinstein_stage2_breakout():
    rows = [[100 + 0.01 * i, 100.5 + 0.01 * i, 99.5 + 0.01 * i, 100 + 0.01 * i, 1e6] for i in range(195)]
    rows += [[102 + i, 103.5 + i, 101.5 + i, 103 + i, 3e6] for i in range(5)]  # breakout week on 3x volume
    p = panel_of(rows, start="2024-01-08", mansfield_rs=5.0, sma_150=90.0)  # 40 weeks Mon..Fri, ends 2024-10-11
    assert last_date(p) == date(2024, 10, 11)
    s = strat("weinstein_stage2_breakout")
    sigs = s.signals(p, last_date(p))
    assert len(sigs) == 1 and sigs[0].target is None and sigs[0].features["wk_vol_ratio_4"] == pytest.approx(3.0)
    check_geometry(sigs)
    assert s.signals(p, date(2024, 10, 10)) == []  # Thursday: the week is not complete
    p["mansfield_rs"] = -1.0
    assert s.signals(p, last_date(p)) == []
    assert s.should_exit(pd.Series({"close": 89.0, "sma_150": 90.0}), 30)
