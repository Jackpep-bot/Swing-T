"""Catalog batch 1 strategies (docs/strategies/<slug>.md): hand-built panels where each must and must not fire,
signal geometry and exit hooks, plus the cross-strategy contract checks of tests/test_strategies_common.py."""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

import tests.test_strategies_common as common
from swing_engine.core import registry
from swing_engine.core.models import EntryType
from swing_engine.features import build_panel
from swing_engine.features.extra import ensure_extra
from swing_engine.features.patterns2 import add_patterns2
from tests.fixtures.strategies.panel import bars_from_ohlc, last_date, make_panel
from tests.test_strategy_base_breakout import cup_rows

SLUGS = [
    "pre_holiday_effect", "earnings_announcement_return_abr", "revenue_surprise", "bollinger_pctb_mfi_trend",
    "calhoun_atr_high_sma_breakout", "cooper_123_pullback", "fibonacci_retracement_pullback", "ibs_mean_reversion",
    "kaufman_gap_momentum", "lizards_cooper", "pendergast_long_haul", "rsi_divergence", "three_bar_inside_bar_prathap",
    "volatility_expansion_close", "canslim", "heikin_ashi_trend_ride", "ma_crossover_family",
    "rich_simple_trend_channel", "turtle_breakout_systems",
]
WARM = 230  # trend_state needs sma_200
WICK = 0.004


# ----------------------------------------------------------------------------------------------- builders
def walk(n: int = WARM, start: float = 50.0, up: float = 0.004, down: float = -0.002) -> list[float]:
    """Alternating up/down closes: a mild uptrend with two-sided RSI and a non-zero ATR."""
    out, c = [], start
    for i in range(n):
        c *= 1 + (up if i % 2 == 0 else down)
        out.append(c)
    return out


def rows_from(closes: list[float], vol: float = 1e6, prev: float | None = None) -> list[list[float]]:
    out, p = [], closes[0] if prev is None else prev
    for c in closes:
        out.append([p, max(p, c) * (1 + WICK), min(p, c) * (1 - WICK), c, vol])
        p = c
    return out


def panel_of(rows: list[list[float]], symbol: str = "AAA", start: str = "2024-01-02") -> pd.DataFrame:
    return build_panel(bars_from_ohlc(symbol, rows, start=start))


def strat(name: str, params: dict | None = None):
    return registry.get("strategy", name)(params)


def run(name: str, panel: pd.DataFrame, params: dict | None = None, as_of=None, regime=None):
    return strat(name, params).signals(panel, as_of or last_date(panel), regime)


def ramp(start: float, n: int, step: float) -> list[float]:
    return [start * (1 + step) ** (k + 1) for k in range(n)]


def check_geometry(sig) -> None:
    assert sig.stop < sig.entry
    if sig.target is not None:
        assert sig.target > sig.entry


def row_of(panel: pd.DataFrame, name: str, idx: int = -1) -> pd.Series:
    full = ensure_extra(panel, strat(name).required_features())
    return full.iloc[idx]


# ----------------------------------------------------------------------------------------------- contract checks
@pytest.fixture(scope="module")
def generic_panel() -> pd.DataFrame:
    p = make_panel(("AAA", "BBB", "CCC", "DDD"), n_days=320, seed=11)
    k = p.groupby("symbol").cumcount()
    # optional EDGAR columns (data/fundamentals.py edgar_panel_features) so the fundamentals strategies scan
    return p.assign(days_since_earnings=(k % 63).astype(float), rev_surprise=(k % 7).astype(float), sue=1.0)


def test_registry_lists_batch():
    assert set(SLUGS) <= set(registry.names("strategy"))


@pytest.mark.parametrize("name", sorted(set(SLUGS) - {"canslim"}))  # canslim inherits base_breakout's patterns2 columns
def test_common_params_and_columns(name, generic_panel):
    common.test_defaults_params_and_required_features(name)
    common.test_generator_panel_has_required_columns(name, generic_panel)


def test_canslim_params_and_columns(generic_panel):
    s = strat("canslim")
    assert "min_reward_risk" in s.default_params and strat("canslim", {"min_reward_risk": 9.0}).params["min_reward_risk"] == 9.0
    panel = add_patterns2(generic_panel.sort_values(["symbol", "ts"]).reset_index(drop=True))
    assert not [c for c in s.required_features() if c not in panel.columns]


@pytest.mark.parametrize("name", SLUGS)
def test_common_signals_well_formed_and_point_in_time(name, generic_panel):
    common.test_signals_are_well_formed_and_point_in_time(name, generic_panel)


@pytest.mark.parametrize("name", SLUGS)
def test_empty_panel(name, generic_panel):
    assert run(name, generic_panel.iloc[0:0], as_of=last_date(generic_panel)) == []


# ----------------------------------------------------------------------------------------------- pre_holiday_effect
def _dated(last: str) -> pd.DataFrame:
    n = len(pd.bdate_range("2024-01-02", last))
    return panel_of(rows_from(walk(n)))


def test_pre_holiday_fires_two_sessions_before_thanksgiving():
    sigs = run("pre_holiday_effect", _dated("2024-11-26"))  # 11-27 is the pre-holiday session, 11-28 Thanksgiving
    assert len(sigs) == 1
    s = sigs[0]
    check_geometry(s)
    assert s.target is None and s.entry - s.stop == pytest.approx(3.0 * row_of(_dated("2024-11-26"), "pre_holiday_effect")["atr_14"])
    st = strat("pre_holiday_effect")
    assert st.should_exit(pd.Series(), 2) and not st.should_exit(pd.Series(), 1)


def test_pre_holiday_silent_on_ordinary_day():
    assert run("pre_holiday_effect", _dated("2024-11-25")) == []
    assert run("pre_holiday_effect", _dated("2024-11-27")) == []  # that is pre_holiday_1: entry was the day before


# ----------------------------------------------------------------------------------------------- earnings / revenue factors
def _three(last: str, bump_sym: str = "AAA", bump_back: int = 5) -> pd.DataFrame:
    n = len(pd.bdate_range("2024-01-02", last))
    frames = []
    for sym, seed_up in (("AAA", 0.004), ("BBB", 0.0045), ("CCC", 0.005)):
        closes = walk(n, up=seed_up)
        if sym == bump_sym:  # +10% jump on the announcement session
            closes = closes[: n - bump_back] + [c * 1.10 for c in closes[n - bump_back :]]
        frames.append(bars_from_ohlc(sym, rows_from(closes)))
    return build_panel(pd.concat(frames, ignore_index=True))


def test_abr_buys_top_decile_at_month_end():
    panel = _three("2024-11-29").assign(days_since_earnings=4.0)  # day 0 = 4 sessions before the month-end close
    sigs = run("earnings_announcement_return_abr", panel)
    assert [s.symbol for s in sigs] == ["AAA"]
    s = sigs[0]
    check_geometry(s)
    assert s.features["abr"] == pytest.approx(0.10 * 2 / 3, abs=0.01)  # minus the equal-weight mean incl. AAA and s.target is None
    assert strat("earnings_announcement_return_abr").should_exit(pd.Series(), 21)


def test_abr_silent_off_month_end_without_dates_or_stale():
    panel = _three("2024-11-27").assign(days_since_earnings=4.0)
    assert run("earnings_announcement_return_abr", panel) == []  # not the last session of the month
    month_end = _three("2024-11-29")
    assert run("earnings_announcement_return_abr", month_end) == []  # no earnings-date column
    assert run("earnings_announcement_return_abr", month_end.assign(days_since_earnings=200.0)) == []  # too old
    assert run("earnings_announcement_return_abr", month_end.assign(days_since_earnings=0.0)) == []  # day +1 not closed


def _with_rs(panel: pd.DataFrame, sue_aaa: float) -> pd.DataFrame:
    rs = panel["symbol"].map({"AAA": 3.0, "BBB": 1.0, "CCC": 0.5})
    return panel.assign(rev_surprise=rs, sue=np.where(panel["symbol"] == "AAA", sue_aaa, 1.0))


def test_revenue_surprise_top_decile_with_positive_sue():
    sigs = run("revenue_surprise", _with_rs(_three("2024-11-29"), 1.0))
    assert [s.symbol for s in sigs] == ["AAA"]
    check_geometry(sigs[0])
    assert sigs[0].target is None


def test_revenue_surprise_silent():
    assert run("revenue_surprise", _with_rs(_three("2024-11-29"), -1.0)) == []  # sue <= 0
    assert run("revenue_surprise", _with_rs(_three("2024-11-27"), 1.0)) == []  # not month end
    assert run("revenue_surprise", _three("2024-11-29")) == []  # no rev_surprise column


# ----------------------------------------------------------------------------------------------- bollinger %b + MFI
def test_bollinger_pctb_mfi_fires_on_strong_rise():
    closes = walk() + ramp(walk()[-1], 12, 0.015)
    panel = panel_of(rows_from(closes))
    sigs = run("bollinger_pctb_mfi_trend", panel)
    assert len(sigs) == 1
    s = sigs[0]
    check_geometry(s)
    row = row_of(panel, "bollinger_pctb_mfi_trend")
    assert row["bb_pctb_20"] > 0.8 and row["mfi_10"] > 80 and row["psar_dir"] == 1
    assert s.stop == pytest.approx(max(row["psar"], s.entry - 2 * row["atr_14"]))
    st = strat("bollinger_pctb_mfi_trend")
    assert st.trail_stop(row) == pytest.approx(row["psar"])
    assert st.should_exit(pd.Series({"bb_pctb_20": 0.1, "mfi_10": 10.0}), 1)
    assert not st.should_exit(pd.Series({"bb_pctb_20": 0.1, "mfi_10": 50.0}), 1)


def test_bollinger_pctb_mfi_silent_on_decline():
    closes = walk() + ramp(walk()[-1], 12, -0.01)
    assert run("bollinger_pctb_mfi_trend", panel_of(rows_from(closes))) == []


# ----------------------------------------------------------------------------------------------- calhoun ATR high / SMA
def _calhoun(start: float) -> pd.DataFrame:
    closes = walk(start=start, up=0.006, down=-0.002)
    p = closes[-1]
    return panel_of([*rows_from(closes, vol=1.2e6), [p, p * 1.05, p * 0.98, p * 1.04, 1.5e6]])


def test_calhoun_buy_stop_over_wide_bar():
    panel = _calhoun(20.0)
    sigs = run("calhoun_atr_high_sma_breakout", panel)
    assert len(sigs) == 1
    s = sigs[0]
    row = row_of(panel, "calhoun_atr_high_sma_breakout")
    assert s.entry_type == EntryType.STOP
    assert s.entry == pytest.approx(row["high"] + 0.15 * row["atr_14"])
    risk = s.entry - s.stop
    assert row["atr_14"] - 1e-9 <= risk <= 2 * row["atr_14"] + 1e-9
    assert s.reward_risk == pytest.approx(2.0)


def test_calhoun_silent_outside_price_band_or_quiet_bar():
    assert run("calhoun_atr_high_sma_breakout", _calhoun(60.0)) == []  # last close above $70
    assert run("calhoun_atr_high_sma_breakout", panel_of(rows_from(walk(start=20.0, up=0.006), vol=1.2e6))) == []


# ----------------------------------------------------------------------------------------------- cooper 1-2-3
def _cooper(n_down: int) -> pd.DataFrame:
    base = walk()
    rows = rows_from(base)
    c = base[-1]
    for _ in range(40):  # strong thrust: tight lows, ADX > 30
        rows.append([c, c * 1.016, c * 0.999, c * 1.015, 1e6])
        c *= 1.015
    rows[-5][1] = rows[-5][3] * 1.08  # a spike high a few bars before the peak = the prior swing high
    for _ in range(n_down):  # lower lows, highs at the open
        nc = c * 0.985
        rows.append([c, c, nc * 0.998, nc, 1e6])
        c = nc
    return panel_of(rows)


def test_cooper_123_buy_stop_over_day_three():
    panel = _cooper(3)
    sigs = run("cooper_123_pullback", panel)
    assert len(sigs) == 1
    s = sigs[0]
    last = panel.iloc[-1]
    assert s.entry_type == EntryType.STOP
    assert s.entry == pytest.approx(last["high"] + 0.01) and s.stop == pytest.approx(last["low"] - 0.01)
    check_geometry(s)
    assert s.reward_risk >= 1.0
    assert strat("cooper_123_pullback").should_exit(pd.Series(), 5)


def test_cooper_123_needs_three_lower_lows():
    assert run("cooper_123_pullback", _cooper(2)) == []


# ----------------------------------------------------------------------------------------------- fibonacci
def _fib(trigger: bool) -> pd.DataFrame:
    base = walk(up=0.002, down=-0.002)  # flat near 50: the impulse low
    impulse = list(np.linspace(base[-1], 70.0, 21)[1:])  # 50 -> 70 in 20 bars
    pull = [*np.linspace(70.0, 59.2, 6)[1:], 59.0]  # ~56% retracement of the low, the last bar small
    last = 59.6 if trigger else 58.9  # trigger: close over the prior bar's high (59.2 x 1.004)
    return panel_of(rows_from(base + impulse + pull + [last]))


def test_fibonacci_pullback_fires_in_zone_on_trigger():
    sigs = run("fibonacci_retracement_pullback", _fib(True))
    assert len(sigs) == 1
    s = sigs[0]
    check_geometry(s)
    assert 0.382 <= s.features["retr_pct"] <= 0.618
    assert s.target == pytest.approx(s.features["impulse_high"]) and s.reward_risk >= 1.5


def test_fibonacci_pullback_silent_without_trigger_or_outside_control_zone():
    assert run("fibonacci_retracement_pullback", _fib(False)) == []
    assert run("fibonacci_retracement_pullback", _fib(True), {"zone_low": 0.62, "zone_high": 0.7}) == []


# ----------------------------------------------------------------------------------------------- IBS
def _ibs(symbol: str) -> pd.DataFrame:
    closes = walk()
    p = closes[-1]
    return panel_of([*rows_from(closes), [p, p * 1.01, p * 0.98, p * 0.982, 1e6]], symbol=symbol)


def test_ibs_fires_on_etf_closing_near_low():
    sigs = run("ibs_mean_reversion", _ibs("SPY"))
    assert len(sigs) == 1 and sigs[0].features["ibs"] < 0.2
    check_geometry(sigs[0])
    st = strat("ibs_mean_reversion")
    assert st.should_exit(pd.Series({"close_pos": 0.9}), 1) and st.should_exit(pd.Series({"close_pos": 0.5}), 3)
    assert not st.should_exit(pd.Series({"close_pos": 0.5}), 1)


def test_ibs_silent_on_single_stock_or_high_close():
    assert run("ibs_mean_reversion", _ibs("AAA")) == []
    assert len(run("ibs_mean_reversion", _ibs("AAA"), {"symbols": None})) == 1
    assert run("ibs_mean_reversion", panel_of(rows_from(walk()), symbol="SPY")) == []


# ----------------------------------------------------------------------------------------------- Kaufman gap momentum
SMALL_GAPM = {"length": 2, "signal_length": 2}


def _gaps() -> pd.DataFrame:
    rows = [[50.0, 50.4, 49.6, 50.0, 1e6]] * WARM  # no gaps: ratio 1, flat signal
    rows += [[49.0, 49.4, 48.6, 49.0, 1e6], [50.0, 50.4, 49.6, 50.0, 1e6]]  # down gap, then up gap
    return panel_of([list(r) for r in rows])


def test_gap_momentum_fires_when_signal_turns_up():
    panel = _gaps()
    sigs = run("kaufman_gap_momentum", panel, SMALL_GAPM)
    assert len(sigs) == 1
    check_geometry(sigs[0])
    st = strat("kaufman_gap_momentum", SMALL_GAPM)
    assert st.should_exit(pd.Series({"gapm_slope_2_2": -1.0}), 1) and not st.should_exit(pd.Series({"gapm_slope_2_2": 1.0}), 1)


def test_gap_momentum_silent_while_falling():
    panel = _gaps()
    prev_day = pd.Timestamp(panel["ts"].iloc[-2]).date()
    assert run("kaufman_gap_momentum", panel, SMALL_GAPM, as_of=prev_day) == []


# ----------------------------------------------------------------------------------------------- lizards
def _lizard(close_frac: float) -> pd.DataFrame:
    closes = walk()
    p = closes[-1]
    return panel_of([*rows_from(closes), [p * 0.99, p, p * 0.95, p * close_frac, 1e6]])


def test_lizard_buy_stop_over_high():
    panel = _lizard(0.995)
    sigs = run("lizards_cooper", panel)
    assert len(sigs) == 1
    s, last = sigs[0], panel.iloc[-1]
    assert s.entry_type == EntryType.STOP and s.entry == pytest.approx(last["high"] + 0.01)
    assert s.stop == pytest.approx(last["low"] - 0.01) and s.target is None
    assert run("lizards_cooper", panel, {"entry_style": "open"})[0].entry_type == EntryType.OPEN


def test_lizard_silent_when_close_low_in_range():
    assert run("lizards_cooper", _lizard(0.96)) == []


# ----------------------------------------------------------------------------------------------- Long Haul
def _long_haul(last_up: bool) -> pd.DataFrame:
    base = walk(up=0.012, down=-0.009)
    dump = ramp(base[-1], 5, -0.025)  # RSI(14) < 30
    rec = []
    c = dump[-1]
    for i in range(10):  # choppy recovery back over sma_50, RSI stays < 70
        c *= 1.02 if i % 2 == 0 else 0.996
        rec.append(c)
    last = rec[-1] * (1.03 if last_up else 0.98)
    return panel_of(rows_from(base + dump + rec + [last]))


def test_long_haul_fires_on_breakout_after_oversold():
    panel = _long_haul(True)
    sigs = run("pendergast_long_haul", panel)
    assert len(sigs) == 1
    s = sigs[0]
    check_geometry(s)
    row = row_of(panel, "pendergast_long_haul")
    st = strat("pendergast_long_haul")
    assert s.stop == pytest.approx(row["low_3"]) and st.trail_stop(row) == pytest.approx(row["low_3"])
    assert st.should_exit(pd.Series({"close": 1.0, "sma_10": 2.0}), 1)


def test_long_haul_silent_without_breakout():
    assert run("pendergast_long_haul", _long_haul(False)) == []


# ----------------------------------------------------------------------------------------------- RSI divergence
def _divergence() -> pd.DataFrame:
    base = walk()
    first = ramp(base[-1], 6, -0.03)  # sharp drop: deep RSI low
    bounce = ramp(first[-1], 8, 0.01)
    second = ramp(bounce[-1], 12, -0.007)  # slow grind to a lower price low, shallower RSI low
    right = ramp(second[-1], 5, 0.004)
    return panel_of(rows_from(base + first + bounce + second + right))


def test_rsi_divergence_regular_bullish():
    panel = _divergence()
    sigs = run("rsi_divergence", panel)
    assert len(sigs) == 1
    s = sigs[0]
    check_geometry(s)
    assert s.features["pivot_rsi"] < 35 and s.target is None


def test_rsi_divergence_not_before_confirmation():
    panel = _divergence()
    assert run("rsi_divergence", panel, as_of=pd.Timestamp(panel["ts"].iloc[-2]).date()) == []
    assert run("rsi_divergence", panel, {"variant": "hidden"}) == []


# ----------------------------------------------------------------------------------------------- three-bar inside bar
def _three_bar(inside: bool) -> pd.DataFrame:
    rows = rows_from(walk())
    p = rows[-1][3]
    rows.append([p, p * 1.02, p * 0.995, p * 1.015, 1e6])  # bar 2 closes up
    q = p * 1.015
    rows.append([q, q * (1.002 if inside else 1.03), q * 0.99, q * 0.998, 1e6])  # bar 3 (inside or not)
    rows.append([q * 0.998, q * 1.012, q * 0.995, q * 1.01, 1e6])  # bar 4 closes higher
    return panel_of(rows)


def test_three_bar_inside_bar_fires():
    panel = _three_bar(True)
    sigs = run("three_bar_inside_bar_prathap", panel)
    assert len(sigs) == 1
    s = sigs[0]
    check_geometry(s)
    assert s.reward_risk == pytest.approx(1.5)
    taught = run("three_bar_inside_bar_prathap", panel, {"bracket_pct": 0.0075, "min_reward_risk": 1.0})[0]
    assert taught.stop == pytest.approx(s.entry * 0.9925) and taught.target == pytest.approx(s.entry * 1.0075)


def test_three_bar_inside_bar_needs_inside_bar():
    assert run("three_bar_inside_bar_prathap", _three_bar(False)) == []


# ----------------------------------------------------------------------------------------------- volatility expansion
def test_volatility_expansion_arms_buy_stop():
    panel = panel_of(rows_from(walk()))
    sigs = run("volatility_expansion_close", panel)
    assert len(sigs) == 1
    s, row = sigs[0], row_of(panel, "volatility_expansion_close")
    assert s.entry_type == EntryType.STOP
    assert s.entry == pytest.approx(row["close"] + 0.75 * row["atr_sma_5"])
    assert s.stop == pytest.approx(row["close"] - 1.5 * row["atr_sma_5"])
    assert strat("volatility_expansion_close").trail_stop(row) == pytest.approx(s.stop)


def test_volatility_expansion_silent_in_warmup_or_gated_market():
    assert run("volatility_expansion_close", panel_of(rows_from(walk(4)))) == []
    gated = {"min_market_trend_state": 0}
    assert run("volatility_expansion_close", panel_of(rows_from(walk())), gated, regime={"market_trend_state": -1}) == []


# ----------------------------------------------------------------------------------------------- canslim
def test_canslim_is_base_breakout_with_eps_surprise():
    panel = build_panel(bars_from_ohlc("BAS", cup_rows()))
    sigs = run("canslim", panel.assign(sue=1.5))
    assert len(sigs) == 1
    s = sigs[0]
    check_geometry(s)
    assert s.strategy == "canslim" and s.features["sue"] == 1.5
    assert s.target == pytest.approx(s.entry * 1.25) and s.stop >= s.entry * 0.92 - 1e-9


def test_canslim_silent_without_or_with_negative_surprise():
    panel = build_panel(bars_from_ohlc("BAS", cup_rows()))
    assert run("canslim", panel) == []
    assert run("canslim", panel.assign(sue=-0.5)) == []
    assert len(run("canslim", panel, {"require_fundamentals": False})) == 1


# ----------------------------------------------------------------------------------------------- heikin-ashi
def _heikin(strong: bool) -> pd.DataFrame:
    rows = rows_from(walk())
    c = rows[-1][3]
    for _ in range(3):  # down HA candles
        nc = c * 0.98
        rows.append([c, c * 1.002, nc * 0.998, nc, 1e6])
        c = nc
    if strong:  # gap up, low at the open, big close
        rows.append([c * 1.03, c * 1.06, c * 1.03, c * 1.055, 1e6])
    else:
        rows.append([c, c * 1.002, c * 0.97, c * 0.975, 1e6])
    return panel_of(rows)


def test_heikin_ashi_first_strong_up_candle():
    panel = _heikin(True)
    sigs = run("heikin_ashi_trend_ride", panel)
    assert len(sigs) == 1
    s = sigs[0]
    check_geometry(s)
    assert s.features["ha_down_run"] >= 2 and s.reward_risk == pytest.approx(3.0)
    st = strat("heikin_ashi_trend_ride")
    assert st.should_exit(pd.Series({"ha_open": 2.0, "ha_close": 1.0}), 1)
    assert not st.should_exit(pd.Series({"ha_open": 1.0, "ha_close": 2.0}), 1)


def test_heikin_ashi_silent_on_down_candle():
    assert run("heikin_ashi_trend_ride", _heikin(False)) == []


# ----------------------------------------------------------------------------------------------- MA crossover family
def _cross_panel() -> tuple[pd.DataFrame, int]:
    closes = [50.0] * WARM + ramp(50.0, 25, -0.01) + ramp(50.0 * 0.99**25, 25, 0.012)
    panel = panel_of(rows_from(closes))
    c = panel["close"]
    fast, slow = c.rolling(9).mean(), c.rolling(18).mean()
    cross = np.flatnonzero(((fast > slow) & (fast.shift() <= slow.shift())).to_numpy())
    return panel, int(cross[-1])


def test_ma_crossover_two_line_fires_on_cross_bar_only():
    panel, k = _cross_panel()
    day = pd.Timestamp(panel["ts"].iloc[k]).date()
    sigs = run("ma_crossover_family", panel, as_of=day)
    assert len(sigs) == 1
    check_geometry(sigs[0])
    assert sigs[0].target is None
    assert run("ma_crossover_family", panel, as_of=pd.Timestamp(panel["ts"].iloc[k + 1]).date()) == []
    st = strat("ma_crossover_family")
    assert st.should_exit(pd.Series({"sma_9": 1.0, "sma_18": 2.0}), 1)
    assert not st.should_exit(pd.Series({"sma_9": 2.0, "sma_18": 1.0}), 1)


def test_ma_crossover_variants_resolve():
    panel, _ = _cross_panel()
    for variant in ("golden_cross", "vwma_sma", "breen_band", "price_ma", "three_line", "mhl_ma", "webull_5_10_20"):
        st = strat("ma_crossover_family", {"variant": variant})
        assert isinstance(st.signals(panel, last_date(panel)), list)  # every variant's columns resolve
        assert set(st.required_features()) <= set(common.CONTRACT_COLUMNS) | set(st.extra_features)


# ----------------------------------------------------------------------------------------------- Rich trend channel
def test_rich_trend_channel_cross_above_sma_of_highs():
    closes = walk(up=0.006) + ramp(walk(up=0.006)[-1], 6, -0.01) + ramp(walk(up=0.006)[-1] * 0.99**6, 4, 0.012)
    panel = ensure_extra(panel_of(rows_from(closes)), ["sma_8_of_high"])
    above = (panel["close"] > panel["sma_8_of_high"]).to_numpy()
    k = int(np.flatnonzero(above[1:] & ~above[:-1])[-1]) + 1
    day = pd.Timestamp(panel["ts"].iloc[k]).date()
    sigs = run("rich_simple_trend_channel", panel, as_of=day)
    assert len(sigs) == 1
    check_geometry(sigs[0])
    assert run("rich_simple_trend_channel", panel, as_of=day, regime={"market_trend_state": -1}) == []
    if k + 1 < len(panel) and above[k + 1]:
        assert run("rich_simple_trend_channel", panel, as_of=pd.Timestamp(panel["ts"].iloc[k + 1]).date()) == []
    st = strat("rich_simple_trend_channel")
    assert st.should_exit(pd.Series({"close": 1.0, "sma_8_of_low": 2.0}), 1)


# ----------------------------------------------------------------------------------------------- Turtle
def test_turtle_s2_buy_stop_over_55_day_high():
    panel = panel_of(rows_from(walk(up=0.006)))
    sigs = run("turtle_breakout_systems", panel)
    assert len(sigs) == 1
    s, row = sigs[0], ensure_extra(panel, [*strat("turtle_breakout_systems").required_features(), "low_10"]).iloc[-1]
    assert s.entry_type == EntryType.STOP and s.entry == pytest.approx(row["high_55"] + 0.01)
    assert s.entry - s.stop == pytest.approx(2 * row["atr_20"])
    assert strat("turtle_breakout_systems").trail_stop(row) == pytest.approx(row["low_20"])
    assert strat("turtle_breakout_systems", {"system": 1}).trail_stop(row) == pytest.approx(row["low_10"])


def test_turtle_silent_far_below_channel():
    closes = walk(up=0.006)
    closes += ramp(closes[-1], 6, -0.04)
    assert run("turtle_breakout_systems", panel_of(rows_from(closes))) == []


def test_point_in_time_on_hand_built_panel():
    panel = _cooper(3)
    as_of = last_date(panel)
    cut = panel.loc[panel["ts"].dt.tz_localize(None).dt.normalize() <= pd.Timestamp(as_of - timedelta(days=1))]
    assert run("cooper_123_pullback", panel, as_of=last_date(cut)) == run("cooper_123_pullback", cut)
