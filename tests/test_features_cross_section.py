"""Cross-section features: each column checked at a fixed bar against a hand-written formula."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.features import cross_section as cs
from tests.features_gbm import gbm_bars

N = 300
T = 280  # bar under test; past every warm-up


@pytest.fixture(scope="module")
def out() -> pd.DataFrame:
    return cs.add_cross_section(gbm_bars(["AAA"], n_bars=N, seed=3))


def test_returns_momentum_reversal(out: pd.DataFrame) -> None:
    c = out.close.to_numpy()
    for n in cs.RETURN_WINDOWS:
        assert out[f"ret_{n}d"].iloc[T] == pytest.approx(c[T] / c[T - n] - 1)
        assert out[f"ret_{n}d"].iloc[:n].isna().all()
    assert out.mom_12_1.iloc[T] == pytest.approx(c[T - 21] / c[T - 252] - 1)
    assert out.rev_5d.iloc[T] == pytest.approx(-out.ret_5d.iloc[T])
    assert out.rev_21d.iloc[T] == pytest.approx(-out.ret_21d.iloc[T])


def test_realized_vol_and_amihud(out: pd.DataFrame) -> None:
    c, v = out.close.to_numpy(), out.volume.to_numpy()
    lr = np.diff(np.log(c))  # lr[k] is the return of bar k+1
    for n in cs.VOL_WINDOWS:
        exp = np.std(lr[T - n : T], ddof=1) * np.sqrt(252)
        assert out[f"vol_{n}d"].iloc[T] == pytest.approx(exp)
        assert out[f"vol_{n}d"].iloc[:n].isna().all()
    ratios = [abs(c[k] / c[k - 1] - 1) / (c[k] * v[k]) for k in range(T - 20, T + 1)]
    assert out.amihud_21d.iloc[T] == pytest.approx(np.mean(ratios) * 1e6)


def test_volume_features(out: pd.DataFrame) -> None:
    c, v = out.close.to_numpy(), out.volume.to_numpy()
    assert out.avg_vol_20d.iloc[T] == pytest.approx(v[T - 19 : T + 1].mean())
    assert out.avg_vol_50d.iloc[T] == pytest.approx(v[T - 49 : T + 1].mean())
    assert out.dollar_vol_20d.iloc[T] == pytest.approx((c * v)[T - 19 : T + 1].mean())
    # rvol_day benchmarks today's volume against the average of the *prior* 20 bars
    assert out.rvol_day.iloc[T] == pytest.approx(v[T] / v[T - 20 : T].mean())
    assert out.rvol_day.iloc[:20].isna().all() and out.rvol_day.iloc[20:].notna().all()


def test_52w_levels_and_bar_shape(out: pd.DataFrame) -> None:
    h, lo, c, o = (out[k].to_numpy() for k in ("high", "low", "close", "open"))
    assert out.high_52w.iloc[T] == pytest.approx(h[T - 251 : T + 1].max())
    assert out.low_52w.iloc[T] == pytest.approx(lo[T - 251 : T + 1].min())
    assert out.high_52w.iloc[:251].isna().all()
    assert out.dist_52w_high.iloc[T] == pytest.approx(c[T] / h[T - 251 : T + 1].max() - 1)
    assert (out.dist_52w_high.dropna() <= 0).all()
    assert out.gap_pct.iloc[T] == pytest.approx(o[T] / c[T - 1] - 1)
    assert out.range_pct.iloc[T] == pytest.approx((h[T] - lo[T]) / c[T])
    assert out.close_pos.iloc[T] == pytest.approx((c[T] - lo[T]) / (h[T] - lo[T]))
    assert out.close_pos.between(0, 1).all()
    assert out.prev_close.iloc[T] == c[T - 1] and np.isnan(out.prev_close.iloc[0])


def test_close_pos_flat_bar_is_midpoint() -> None:
    s = pd.Series([10.0, np.nan])
    got = cs.close_position(s, s, s)
    assert got.iloc[0] == 0.5 and np.isnan(got.iloc[1])


def test_up_days_counts() -> None:
    close = pd.Series([1.0, 2.0, 3.0, 4.0, 3.0, 2.0, 1.0])
    got = cs.up_days(close, 3).tolist()
    assert np.isnan(got[:3]).all()
    assert got[3:] == [3.0, 2.0, 1.0, 0.0]


def test_pure_functions_agree_with_panel_columns(out: pd.DataFrame) -> None:
    np.testing.assert_allclose(cs.momentum_12_1(out.close).to_numpy(), out.mom_12_1.to_numpy())
    np.testing.assert_allclose(cs.realized_vol(out.close, 21).to_numpy(), out.vol_21d.to_numpy())
    np.testing.assert_allclose(cs.amihud(out.close, out.volume).to_numpy(), out.amihud_21d.to_numpy())
    np.testing.assert_allclose(cs.reversal(out.close, 5).to_numpy(), out.rev_5d.to_numpy())
