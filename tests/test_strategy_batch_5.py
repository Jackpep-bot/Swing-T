"""Catalog batch 5 strategies: contract checks plus one hand-built firing and one non-firing panel each.

Also hand-checks the point-and-figure and TD Sequential columns added to features.extra for this batch.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.core.models import EntryType, Side, Signal
from swing_engine.features import extra as ex
from swing_engine.features.extra import ensure_extra, is_extra
from tests.fixtures.strategies.panel import (
    add_features,
    bars_from_ohlc,
    last_date,
    make_bars,
    make_panel,
    trend_rows,
)
from tests.test_strategies_common import CONTRACT_COLUMNS

SLUGS = [
    "chartschool_gap_first_hour", "pead_sue", "bb_bullish_engulfing_kosinski", "bull_flag_breakout",
    "classic_pattern_detector_lmw", "connors_tps_scale_in", "elder_ma_penetration_channel", "hudgin_golden_triangle",
    "ipo_first_base_breakout", "key_reversal_day", "nr7_nr4_range_contraction", "point_and_figure_signals",
    "td_sequential", "turtle_soup", "zscore_mean_reversion_garner", "faber_sector_rotation",
    "kell_cycle_of_price_action", "price_zone_oscillator", "supertrend_flip_strategy",
]


def _strat(name: str, **params):
    return registry.get("strategy", name)(params or None)


def _build(rows, symbol: str = "AAA", strat=None, start: str = "2024-01-02") -> pd.DataFrame:
    panel = add_features(bars_from_ohlc(symbol, rows, start=start))
    return ensure_extra(panel, strat.extra_features) if strat is not None else panel


def _set(panel: pd.DataFrame, back: int = 0, symbol: str = "AAA", **values: float) -> pd.DataFrame:
    """Copy of ``panel`` with ``values`` written on the row ``back`` bars before the symbol's last bar."""
    out = panel.copy()
    idx = out.index[out["symbol"] == symbol][-1 - back]
    for col, val in values.items():
        if col not in out.columns or not np.issubdtype(out[col].dtype, np.floating):
            out[col] = out[col].astype(float) if col in out.columns else np.nan
        out.loc[idx, col] = float(val)
    return out


def _last(panel: pd.DataFrame, col: str, symbol: str = "AAA", back: int = 0) -> float:
    return float(panel.loc[panel["symbol"] == symbol, col].iloc[-1 - back])


def _check(sig: Signal, strat) -> None:
    assert sig.side == Side.LONG and sig.stop < sig.entry
    if sig.target is not None:
        assert sig.target > sig.entry
        assert sig.reward_risk >= strat.params["min_reward_risk"]


def _uptrend(n: int = 240, step: float = 0.4, strat=None) -> pd.DataFrame:
    return _build(trend_rows(n, step=step), strat=strat)


# ----------------------------------------------------------------------------------------------- contract
@pytest.fixture(scope="module")
def panel() -> pd.DataFrame:
    p = make_panel(("AAA", "BBB", "CCC", "DDD"), n_days=320, seed=11)
    return p.assign(sue=np.tile(np.arange(4.0), len(p) // 4 + 1)[: len(p)], days_since_earnings=5.0)


@pytest.mark.parametrize("name", SLUGS)
def test_contract(name, panel):
    cls = registry.get("strategy", name)
    strat = cls()
    assert strat.name == name and "min_reward_risk" in strat.default_params
    assert set(strat.required_features()) <= CONTRACT_COLUMNS | set(strat.extra_features)
    assert all(is_extra(n) for n in strat.extra_features)
    assert cls({"min_reward_risk": 9.75}).params["min_reward_risk"] == 9.75
    full = ensure_extra(panel, strat.extra_features)
    as_of = last_date(full) - timedelta(days=40)
    sigs = strat.signals(full, as_of)
    for s in sigs:
        assert s.strategy == name and s.as_of == as_of
        _check(s, strat)
        assert all(isinstance(v, float) for v in s.features.values())
    day = full["ts"].dt.tz_localize(None).dt.normalize()
    assert strat.signals(full.loc[day <= pd.Timestamp(as_of)], as_of) == sigs, "future bars changed a signal"
    sat = as_of + timedelta(days=(5 - as_of.weekday()) % 7)
    assert [s.symbol for s in strat.signals(full, sat)] == [s.symbol for s in strat.signals(full, sat - timedelta(1))]


# ----------------------------------------------------------------------------------------------- features
def test_point_and_figure_columns_hand_checked():
    h = np.array([10, 11, 12, 13, 14, 12, 11, 10, 10.5, 12, 13, 14.5, 15.2])
    out = dict(zip(ex.PF_COLUMNS, ex._pf_np(h, h - 0.4), strict=True))
    assert out["pf_dir"].tolist() == [1, 1, 1, 1, 1, -1, -1, -1, -1, 1, 1, 1, 1]
    assert out["pf_top"][4] == 14.0 and out["pf_bot"][7] == 10.0  # X to 14, O down to 10 (0.50 boxes)
    assert out["pf_prev_x_top"][11] == 14.0 and out["pf_top"][11] == 14.5  # double top buy on bar 11
    assert out["pf_prev_o_bot"][9] == 10.0 and np.isnan(out["pf_prev_o_bot"][8])
    assert ex._pf_box(20.0) == 0.5 and ex._pf_box(20.01) == 1.0


def test_td_sequential_columns_hand_checked():
    c = np.array([20, 21, 22, 23, 24, 25, *[19 - 0.5 * i for i in range(25)]], dtype=float)
    out = dict(zip(ex.TD_COLUMNS, ex._td_np(c + 0.2, c - 0.2, c, np.full(len(c), 0.4)), strict=True))
    assert out["td_buy_setup"][6] == 1 and out["td_buy_setup"][14] == 9  # flip on bar 6, setup 9 on bar 14
    assert out["td_buy_perfected"][14] == 1.0 and out["td_tdst"][14] == pytest.approx(19.2)
    assert out["td_risk_level"][14] == pytest.approx(15.0 - 0.2 - 0.4)  # setup low minus its true range
    assert out["td_buy_countdown"][26] == 13 and out["td_buy_countdown"][27] == 0
    assert out["td_risk_level"][26] == pytest.approx(9.0 - 0.2 - 0.4)
    # causal through ensure_extra: appending bars never changes earlier values
    bars = make_bars(("AAA",), n_days=150, seed=5)
    names = [*ex.PF_COLUMNS, *ex.TD_COLUMNS]
    full, part = ensure_extra(bars, names), ensure_extra(bars.iloc[:100], names)
    pd.testing.assert_frame_equal(full[names].iloc[:100], part[names])


# ----------------------------------------------------------------------------------------------- strategies
def test_supertrend_flip():
    s = _strat("supertrend_flip_strategy")
    p = _uptrend(strat=s)
    c = _last(p, "close")
    hit = _set(p, st_dir_10_3=1, prev_st_dir_10_3=-1, st_line_10_3=c - 2)
    (sig,) = s.signals(hit, last_date(hit))
    _check(sig, s)
    assert sig.stop == pytest.approx(c - 2) and sig.target == pytest.approx(c + 10)
    assert s.trail_stop(pd.Series({"st_dir_10_3": 1.0, "st_line_10_3": 5.0})) == 5.0
    assert s.should_exit(pd.Series({"st_dir_10_3": -1.0}), 1) and not s.engine_trail
    assert s.signals(_set(p, st_dir_10_3=1, prev_st_dir_10_3=1, st_line_10_3=c - 2), last_date(p)) == []


def test_zscore_mean_reversion():
    s = _strat("zscore_mean_reversion_garner")
    p = _uptrend(strat=s)
    mid, up = _last(p, "sma_20"), _last(p, "bb_upper_20")
    sd = (up - mid) / 2
    hit = _set(p, close=mid - 1.5 * sd)
    (sig,) = s.signals(hit, last_date(hit))
    _check(sig, s)
    assert sig.target == pytest.approx(mid - 0.5 * sd)
    assert sig.features["zscore"] == pytest.approx(-1.5)
    assert s.should_exit(pd.Series({"close": mid, "sma_20": mid, "bb_upper_20": up}), 1)
    prior_low = _set(hit, back=1, close=_last(p, "sma_20", back=1) - 3 * sd)  # already below -1 yesterday
    assert s.signals(prior_low, last_date(p)) == []


def test_bb_bullish_engulfing():
    s = _strat("bb_bullish_engulfing_kosinski")
    p = _uptrend(strat=s)
    p = _set(p, back=1, open=101, close=99, low=98.5, bb_lower_20=98)
    hit = _set(p, open=98.8, high=101.8, low=97.5, close=101.5, bb_lower_20=98, bb_upper_20=110, atr_14=1)
    (sig,) = s.signals(hit, last_date(hit))
    _check(sig, s)
    assert sig.stop == pytest.approx(99.5) and sig.target == pytest.approx(110)
    assert s.should_exit(pd.Series({"high": 111.0, "bb_upper_20": 110.0}), 1)
    assert s.signals(_set(hit, close=100.5), last_date(p)) == []  # body no longer covers the prior open


def test_key_reversal_day():
    s = _strat("key_reversal_day")
    p = _uptrend(strat=s)
    pl, pc = _last(p, "low", back=1), _last(p, "close", back=1)
    hit = _set(p, low=pl - 1, close=pc + 0.2)
    (sig,) = s.signals(hit, last_date(hit))
    _check(sig, s)
    assert sig.stop == pytest.approx(pl - 1.01) and sig.target is None and sig.entry_type == EntryType.OPEN
    (stop_entry,) = _strat("key_reversal_day", entry_stop=True).signals(hit, last_date(hit))
    assert stop_entry.entry_type == EntryType.STOP and stop_entry.entry == pytest.approx(_last(hit, "high") + 0.01)
    assert s.signals(_set(p, low=pl - 1, close=pc - 0.2), last_date(p)) == []


def test_nr7_range_contraction():
    s = _strat("nr7_nr4_range_contraction", min_stop_pct=0.0)  # a 0.1-point bar: below the default stop floor
    rows = trend_rows(240)
    c = rows[-1][3]
    narrow = [*rows[:-1], [c, c + 0.05, c - 0.05, c, 1e6]]
    (sig,) = s.signals(_build(narrow, strat=s), last_date(_build(narrow)))
    _check(sig, s)
    assert sig.entry_type == EntryType.STOP
    assert sig.entry == pytest.approx(c + 0.06) and sig.stop == pytest.approx(c - 0.06)
    assert s.signals(_build(rows, strat=s), last_date(_build(rows))) == []  # equal ranges: no NR7


def test_turtle_soup_plus_one():
    s = _strat("turtle_soup")
    rows = trend_rows(240)
    level = min(r[2] for r in rows[-20:])
    hit = _build([*rows, [level + 0.5, level + 0.6, level - 1, level - 0.2, 1e6]])
    (sig,) = s.signals(hit, last_date(hit))
    _check(sig, s)
    assert sig.entry_type == EntryType.STOP and sig.entry == pytest.approx(level)
    assert sig.stop == pytest.approx((level - 1) * 0.999) and sig.features["prior_low_age"] == 20
    miss = _build([*rows, [level + 0.5, level + 0.6, level - 1, level + 0.2, 1e6]])
    assert s.signals(miss, last_date(miss)) == []  # closed back above the prior low: not Plus One


def test_price_zone_oscillator():
    s = _strat("price_zone_oscillator")
    p = _uptrend(strat=s)
    p = _set(p, back=1, pzo_14=-45)
    hit = _set(p, pzo_14=-35, prev_pzo_14=-45, adx_14=10)
    (sig,) = s.signals(hit, last_date(hit))
    _check(sig, s)
    assert sig.target is None and "cross_oversold" in sig.notes
    assert s.should_exit(pd.Series({"close": 10.0, "pzo_14": 50.0, "prev_pzo_14": 65.0, "ema_60": 5.0}), 1)
    downtrend = _set(hit, adx_14=30, ema_60=_last(p, "close") + 10)
    assert s.signals(downtrend, last_date(p)) == []


def test_chartschool_gap_daily():
    s = _strat("chartschool_gap_first_hour")
    rows = trend_rows(60)
    pc, ph = rows[-1][3], rows[-1][1]
    o = pc * 1.03
    hit = _build([*rows, [o, o * 1.02, o * 0.995, o * 1.02 - 0.01, 1e6]])
    (sig,) = s.signals(hit, last_date(hit))
    _check(sig, s)
    assert o > ph and "full_gap_up" in sig.notes and sig.stop == pytest.approx(o * 0.995)
    assert s.trail_stop(pd.Series({"close": 100.0})) == pytest.approx(92.0) and not s.engine_trail
    weak = _build([*rows, [o, o * 1.02, o * 0.98, o * 0.99, 1e6]])
    assert s.signals(weak, last_date(weak)) == []


def test_connors_tps():
    s = _strat("connors_tps_scale_in")
    p = _set(_set(_uptrend(), back=1, rsi_2=15), rsi_2=10)
    (sig,) = s.signals(p, last_date(p))
    _check(sig, s)
    assert sig.stop == pytest.approx(_last(p, "close") - 3 * _last(p, "atr_14"))
    assert s.should_exit(pd.Series({"rsi_2": 75.0}), 1) and not s.should_exit(pd.Series({"rsi_2": 50.0}), 1)
    assert s.signals(_set(p, back=1, rsi_2=40), last_date(p)) == []


def test_pead_sue():
    s = _strat("pead_sue")
    syms = tuple(f"S{i:02d}" for i in range(10))
    p = make_panel(syms, n_days=260, seed=3)
    p = p.assign(sue=p["symbol"].map({x: float(i) for i, x in enumerate(syms)}), days_since_earnings=5.0,
                 days_since_filing=3.0)
    p = p.assign(close=p["close"].clip(lower=10.0), high=p["high"].clip(lower=10.5))
    (sig,) = s.signals(p, date(2024, 10, 1))  # first session of October
    _check(sig, s)
    assert sig.symbol == "S09" and sig.target is None
    assert s.signals(p, date(2024, 10, 2)) == []  # not a rebalance day
    assert s.signals(p.drop(columns=["sue"]), date(2024, 10, 1)) == []  # no EDGAR columns: nothing


def test_faber_sector_rotation():
    s = _strat("faber_sector_rotation")
    sectors = make_bars(("XLK", "XLE", "XLF", "XLV"), n_days=260, seed=4)
    spy_up = bars_from_ohlc("SPY", trend_rows(260, start=300.0, step=0.5))
    p = ensure_extra(add_features(pd.concat([sectors, spy_up], ignore_index=True)), s.extra_features)
    month_end = date(2024, 11, 29)  # 10 month-ends of SPY history by then
    sigs = s.signals(p, month_end)
    assert len(sigs) == 3 and "SPY" not in {x.symbol for x in sigs}
    rets = p.loc[p["ts"].dt.date == month_end].set_index("symbol")["ret_63d"].drop("SPY")
    assert {x.symbol for x in sigs} == set(rets.nlargest(3).index)
    for x in sigs:
        _check(x, s)
    assert s.signals(p, date(2024, 11, 27)) == []  # not month end
    spy_down = bars_from_ohlc("SPY", trend_rows(260, start=300.0, step=-0.5))
    p_down = ensure_extra(add_features(pd.concat([sectors, spy_down], ignore_index=True)), s.extra_features)
    assert s.signals(p_down, month_end) == []  # SPY below its 10-month average: cash


def test_elder_ma_penetration():
    s = _strat("elder_ma_penetration_channel")
    closes = [50 + 0.3 * i + 3 * math.sin(2 * math.pi * i / 20) for i in range(285)]
    rows = [[c, c + 0.4, c - 0.4, c, 1e6] for c in closes]
    p = _build(rows)
    assert _last(p, "close") > _last(p, "ema_21") and _last(p, "trend_state") == 1
    (sig,) = s.signals(p, last_date(p))
    _check(sig, s)
    assert sig.entry_type == EntryType.LIMIT and sig.entry < _last(p, "ema_21")
    assert sig.stop == pytest.approx(sig.entry - _last(p, "atr_14"))
    straight = _uptrend()  # lows never dip under the lagging EMA: no penetrations to average
    assert s.signals(straight, last_date(straight)) == []


def _golden_rows(last_volume: float) -> list[list[float]]:
    rows = trend_rows(230, start=50.0, step=0.3)
    c = rows[-1][3]
    for _ in range(10):  # acceleration leg: pivot > 10% above sma_50
        rows.append([c, c + 1.2, c - 0.1, c + 1, 1e6])
        c += 1
    top = c
    drop = [top - 8, top - 15, top - 22]
    rows += [[c + 1, c + 1.2, c - 0.3, c, 1e6] for c in drop]
    base = top - 21.5
    rows += [[base, base + 0.4, base - 0.4, base, 1e6] for _ in range(6)]
    c = top - 17
    return [*rows, [base, c + 0.2, base - 0.1, c, last_volume]]


def test_hudgin_golden_triangle():
    s = _strat("hudgin_golden_triangle")
    p = _build(_golden_rows(3e6))
    (sig,) = s.signals(p, last_date(p))
    _check(sig, s)
    assert sig.target == pytest.approx(sig.features["pivot_high"])
    quiet = _build(_golden_rows(1e6))
    assert s.signals(quiet, last_date(quiet)) == []  # no volume confirmation


def _flag_rows(last_volume: float) -> list[list[float]]:
    rows = trend_rows(230, start=60.0, step=0.1)
    c = rows[-1][3]
    for _ in range(10):  # pole: +2 a bar
        rows.append([c, c + 2.2, c - 0.1, c + 2, 1e6])
        c += 2
    for _ in range(6):  # flag: gentle drift down
        rows.append([c, c + 0.2, c - 0.5, c - 0.3, 1e6])
        c -= 0.3
    pivot = max(r[1] for r in rows[-16:])
    return [*rows, [c, pivot + 0.8, c - 0.1, pivot + 0.6, last_volume]]


def test_bull_flag_breakout():
    s = _strat("bull_flag_breakout")
    p = _build(_flag_rows(2e6))
    (sig,) = s.signals(p, last_date(p))
    _check(sig, s)
    assert 3 <= sig.features["flag_len"] <= 15 and sig.features["pole_atr"] >= 5.5
    assert sig.stop == pytest.approx(sig.features["flag_low"] - 0.01)
    quiet = _build(_flag_rows(1e6))
    assert s.signals(quiet, last_date(quiet)) == []  # rvol below 1.2


def _ipo_rows() -> list[list[float]]:
    rows = [[20.0, 26.0, 20.0, 25.0, 5e6]]  # listing day
    rows += [[c, c + 0.4, c - 0.4, c, 1e6] for c in (27.0 + 2.5 * (i % 2) for i in range(29))]
    return [*rows, [29.5, 30.7, 29.4, 30.5, 3e6]]


def test_ipo_first_base_breakout():
    s = _strat("ipo_first_base_breakout")
    old = bars_from_ohlc("OLD", trend_rows(100))
    new = bars_from_ohlc("NEW", _ipo_rows(), start=str(old["ts"].iloc[70].date()))
    p = add_features(pd.concat([old, new], ignore_index=True))
    (sig,) = s.signals(p, last_date(p))
    _check(sig, s)
    assert sig.symbol == "NEW" and sig.features["pivot"] == pytest.approx(29.9)
    assert sig.stop == pytest.approx(30.5 * 0.92) and sig.target == pytest.approx(30.5 * 1.2)
    alone = add_features(new)  # history starts with the panel: not a known new listing
    assert s.signals(alone, last_date(alone)) == []


def test_kell_wedge_pop():
    s = _strat("kell_cycle_of_price_action")
    p = _uptrend(strat=s)
    c, pc = _last(p, "close"), _last(p, "close", back=1)
    p = _set(p, back=5, ema_10=_last(p, "high", back=5) + 10)  # downside extension 5 bars ago
    p = _set(p, back=1, ema_10=pc + 1)  # yesterday closed under the EMAs
    hit = _set(p, ema_10=c - 0.5, ema_20=c - 1, rvol_day=2)
    (sig,) = s.signals(hit, last_date(hit))
    _check(sig, s)
    assert sig.stop == pytest.approx(_last(hit, "low")) and sig.target is None and not s.engine_trail
    assert s.should_exit(pd.Series({"close": 9.0, "ema_20": 10.0}), 1)
    assert s.signals(_set(hit, rvol_day=1.0), last_date(p)) == []


def test_td_sequential_countdown():
    s = _strat("td_sequential")
    p = _uptrend(strat=s)
    c = _last(p, "close")
    hit = _set(p, td_buy_countdown=13, td_risk_level=c - 2, td_tdst=c + 10)
    (sig,) = s.signals(hit, last_date(hit))
    _check(sig, s)
    assert sig.stop == pytest.approx(max(c - 2, c - 3 * _last(p, "atr_14"))) and sig.target == pytest.approx(c + 10)
    assert s.signals(_set(hit, td_buy_countdown=12), last_date(p)) == []
    setup = _set(p, td_buy_setup=9, td_buy_perfected=1, td_risk_level=c - 2, td_tdst=c + 10)
    assert len(_strat("td_sequential", trigger="setup").signals(setup, last_date(p))) == 1


def test_point_and_figure_double_top():
    s = _strat("point_and_figure_signals")
    p = _uptrend(strat=s)
    c = _last(p, "close")
    cols = dict(pf_dir=1, pf_box=1, pf_prev_x_top=c - 1, pf_bot=c - 6, pf_prev_o_bot=c - 8)
    p = _set(p, back=1, pf_top=c - 1, **cols)
    hit = _set(p, pf_top=c, **cols)
    (sig,) = s.signals(hit, last_date(hit))
    _check(sig, s)
    assert sig.stop == pytest.approx(c - 9) and sig.target == pytest.approx(c - 6 + 7 * 3)
    assert s.should_exit(pd.Series({"pf_dir": -1.0, "pf_bot": 5.0, "pf_prev_o_bot": 6.0}), 1)
    already = _set(hit, back=1, pf_top=c - 0.5)  # yesterday's column already beat the prior X top
    assert s.signals(already, last_date(p)) == []


def _ihs_closes(last: float) -> list[float]:
    knots = [(0, 108), (6, 100), (12, 106), (19, 96), (26, 106), (31, 100.5), (37, 105.5)]
    xs, ys = zip(*knots, strict=True)
    pattern = list(np.interp(np.arange(38), xs, ys))
    lead = list(np.linspace(60, 108, 201))[:-1]
    return [*lead, *pattern, last]


def test_lmw_inverse_head_and_shoulders():
    s = _strat("classic_pattern_detector_lmw")
    p = _build([[c, c + 0.3, c - 0.3, c, 1e6] for c in _ihs_closes(107.0)])
    (sig,) = s.signals(p, last_date(p))
    _check(sig, s)
    assert "inverse_hs" in sig.notes and sig.features["neckline"] == pytest.approx(106)
    assert sig.target == pytest.approx(116)
    flat = _build([[c, c + 0.3, c - 0.3, c, 1e6] for c in _ihs_closes(105.8)])
    assert s.signals(flat, last_date(flat)) == []  # no neckline break
