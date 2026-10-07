"""Pivot support/resistance (loop reference + confirmation-delay check) and the pattern flags."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.features import cross_section as cs
from swing_engine.features import levels as lv
from swing_engine.features import patterns as pt
from tests.features_gbm import gbm_bars


def _slow_levels(h: np.ndarray, lo: np.ndarray, c: np.ndarray, lookback: int, width: int):
    n = len(c)
    sup, res = np.full(n, np.nan), np.full(n, np.nan)
    ph = [i for i in range(width, n - width) if h[i] >= h[i - width : i + width + 1].max()]
    pl = [i for i in range(width, n - width) if lo[i] <= lo[i - width : i + width + 1].min()]
    for t in range(1, n):
        ref = c[t - 1]
        above = [h[i] for i in ph if t - lookback <= i <= t - 1 - width and h[i] > ref]
        below = [lo[i] for i in pl if t - lookback <= i <= t - 1 - width and lo[i] < ref]
        if above:
            res[t] = min(above)
        if below:
            sup[t] = max(below)
    return sup, res


def _sine_frame(n: int = 70) -> pd.DataFrame:
    i = np.arange(n)
    price = 90 + 10 * np.sin(2 * np.pi * i / 20) + 0.1 * i
    return pd.DataFrame({"symbol": "SIN", "high": price + 0.5, "low": price - 0.5, "close": price})


def test_levels_match_loop_reference() -> None:
    bars = gbm_bars(["AAA"], n_bars=300, seed=4)
    got = lv.support_resistance(bars.high, bars.low, bars.close)
    sup, res = _slow_levels(bars.high.to_numpy(), bars.low.to_numpy(), bars.close.to_numpy(), 60, 5)
    np.testing.assert_allclose(got.support_1.to_numpy(), sup)
    np.testing.assert_allclose(got.resistance_1.to_numpy(), res)
    assert got.support_1.notna().sum() > 100 and got.resistance_1.notna().sum() > 100


def test_pivot_confirmation_delay_on_sine_wave() -> None:
    df = _sine_frame()
    ph = lv.pivot_highs(df.high)
    pl = lv.pivot_lows(df.low)
    assert list(np.flatnonzero(ph)) == [5, 25, 45]
    assert list(np.flatnonzero(pl)) == [15, 35, 55]
    sr = lv.support_resistance(df.high, df.low, df.close)
    assert sr.resistance_1.iloc[60] == pytest.approx(101.0)
    assert sr.support_1.iloc[60] == pytest.approx(83.0)  # pivot low at 55 is not confirmed until bar 60
    assert sr.support_1.iloc[61] == pytest.approx(85.0)  # ...and is in force from bar 61
    assert sr.support_1.iloc[:16].isna().all() and sr.support_1.iloc[21] == pytest.approx(81.0)


def test_add_levels_derived_columns() -> None:
    bars = gbm_bars(["AAA", "BBB"], n_bars=200, seed=5)
    out = lv.add_levels(bars)
    for _, grp in out.groupby("symbol"):
        sr = lv.support_resistance(grp.high, grp.low, grp.close)
        np.testing.assert_allclose(grp.support_1.to_numpy(), sr.support_1.to_numpy())
        np.testing.assert_allclose(grp.resistance_1.to_numpy(), sr.resistance_1.to_numpy())
        np.testing.assert_allclose(grp.range_width.to_numpy(), (sr.resistance_1 - sr.support_1).to_numpy())
        np.testing.assert_allclose(
            grp.level_touch_pct.to_numpy(), ((grp.low - sr.support_1) / grp.close).to_numpy()
        )
        assert (grp.level_break == (grp.close > sr.resistance_1).astype(int)).all()
    assert out.level_break.dtype == np.int64 and set(out.level_break.unique()) <= {0, 1}


def test_burst_inside_key_reversal_pure() -> None:
    nan = np.nan
    s = pd.Series
    assert pt.burst_4pct(s([100.0, 105.0]), s([nan, 100.0]), s([150e3, 200e3]), s([nan, 150e3])).tolist() == [
        0,
        1,
    ]
    assert pt.burst_4pct(s([100.0, 105.0]), s([nan, 100.0]), s([150e3, 90e3]), s([nan, 80e3])).tolist() == [
        0,
        0,
    ]
    assert pt.burst_4pct(s([100.0, 103.0]), s([nan, 100.0]), s([150e3, 200e3]), s([nan, 150e3])).tolist() == [
        0,
        0,
    ]
    assert pt.inside_day(s([10.0, 9.5]), s([9.0, 9.2]), s([nan, 10.0]), s([nan, 9.0])).tolist() == [0, 1]
    assert pt.inside_day(s([10.0, 10.5]), s([9.0, 9.2]), s([nan, 10.0]), s([nan, 9.0])).tolist() == [0, 0]
    kr = pt.key_reversal(
        s([9.0, 8.5]), s([nan, 9.0]), s([9.5, 9.8]), s([nan, 9.5]), s([1e6, 2e6]), s([nan, 1e6])
    )
    assert kr.tolist() == [0, 1]
    kr = pt.key_reversal(
        s([9.0, 8.5]), s([nan, 9.0]), s([9.5, 9.8]), s([nan, 9.5]), s([1e6, 1.2e6]), s([nan, 1e6])
    )
    assert kr.tolist() == [0, 0]


def test_breakout_52w_and_burst_in_panel() -> None:
    t = 290
    base = gbm_bars(["AAA"], n_bars=300, seed=6)
    hot = base.copy()
    prior_high = base.high.iloc[t - 252 : t].max()
    hot.loc[t, "close"] = prior_high * 1.01
    hot.loc[t, "high"] = prior_high * 1.02
    hot.loc[t, "volume"] = 5 * base.volume.iloc[t - 50 : t].mean()
    out = pt.add_patterns(cs.add_cross_section(hot))
    assert out.breakout_52w.iloc[t] == 1
    cold = hot.copy()
    cold.loc[t, "volume"] = 0.5 * base.volume.iloc[t - 50 : t].mean()
    assert pt.add_patterns(cs.add_cross_section(cold)).breakout_52w.iloc[t] == 0
    burst = base.copy()
    burst.loc[t, "close"] = base.close.iloc[t - 1] * 1.05
    burst.loc[t, "high"] = burst.loc[t, "close"] * 1.01
    burst.loc[t, "volume"] = base.volume.iloc[t - 1] + 1
    assert pt.add_patterns(cs.add_cross_section(burst)).burst_4pct.iloc[t] == 1


def test_base_len_matches_loop_reference() -> None:
    bars = gbm_bars(["UP"], n_bars=400, seed=5, mu=0.6, sigma=0.15)
    out = pt.add_patterns(cs.add_cross_section(bars))
    dist = out.dist_52w_high.to_numpy()
    near = dist >= -0.05
    exp = np.full(len(dist), np.nan)
    last = None
    for i in range(len(dist)):
        if near[i]:
            last = i
        if last is not None:
            exp[i] = i - last
    np.testing.assert_allclose(out.base_len.to_numpy(), exp)
    assert np.nansum(exp) > 0 and (out.base_len == 0).sum() > 10


def test_vcp_contraction_ratio() -> None:
    amp = np.repeat([5.0, 3.0, 1.0], 20)
    high, low = pd.Series(105 + amp), pd.Series(105 - amp)
    got = pt.vcp_contraction(high, low)
    assert got.iloc[:59].isna().all()
    assert got.iloc[59] == pytest.approx(2.0 / 10.0)
    assert pt.bars_since(pd.Series([False, True, False, False, True])).iloc[1:].tolist() == [
        0.0,
        1.0,
        2.0,
        0.0,
    ]
    assert np.isnan(pt.bars_since(pd.Series([False, True])).iloc[0])
