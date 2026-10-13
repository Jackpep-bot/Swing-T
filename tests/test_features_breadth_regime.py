"""features.breadth regime-tool columns (A/D, AD Percent, Zweig, McClellan, Stockbee Q25, Hill high-low) on tiny
hand-built panels whose expected values are worked out by hand."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.features import breadth as br
from tests.features_gbm import gbm_bars
from tests.test_features_breadth import _bars

NAN = float("nan")
VOL = 1_000_000.0


def _panel(closes: dict[str, list[float]]) -> pd.DataFrame:
    return pd.concat([_bars(s, c, [VOL] * len(c)) for s, c in closes.items()], ignore_index=True)


def test_advances_declines_and_ad_line() -> None:
    out = br.market_breadth(_panel({
        "A": [10, 11, 11, 10],  # -, up, flat, down
        "B": [10, 9, 10, 9],  # -, down, up, down
        "C": [10, 11, 9, 9],  # -, up, down, flat
    }))
    assert out["advances"].tolist() == [0, 2, 1, 0]
    assert out["declines"].tolist() == [0, 1, 1, 2]
    assert out["ad_line"].tolist() == [0, 1, 1, -1]
    assert out["advances"].dtype == np.int64 and out["ad_line"].dtype == np.int64


def test_first_session_net_advances_is_undefined_not_zero() -> None:
    """Every symbol rises every session after the first: AD% = 100, A/(A+D) = 1, net = 2 constant. Session 0 has no
    prior close, so it must not count as an input: EMA10 starts on session 10, EMA39 (McClellan) on session 39."""
    n = 45
    rising = list(100.0 * 1.01 ** np.arange(n))
    out = br.market_breadth(_panel({"A": rising, "B": rising}))
    assert out["advances"].tolist() == [0] + [2] * (n - 1)
    assert out["ad_line"].tolist() == [2 * i for i in range(n)]
    for col in ("ad_pct_ema10", "zbt_ema10"):
        assert out[col].iloc[:10].isna().all(), col
        assert out[col].iloc[10:].notna().all(), col
    assert out["ad_pct_ema10"].iloc[10:].tolist() == pytest.approx([100.0] * (n - 10))
    assert out["zbt_ema10"].iloc[10:].tolist() == pytest.approx([1.0] * (n - 10))
    assert out["mcclellan_osc"].iloc[:39].isna().all() and out["mcclellan_osc"].iloc[39:].notna().all()
    assert out["mcclellan_osc"].iloc[39:].tolist() == pytest.approx([0.0] * (n - 39))  # constant net: EMA19 == EMA39
    assert out["mcclellan_sum"].iloc[39:].tolist() == pytest.approx([0.0] * (n - 39))
    assert out["zbt_thrust"].sum() == 0  # never below 0.40: no setup


def test_ema_min_periods_and_recursion() -> None:
    got = br.ema(pd.Series([NAN, 1.0, 2.0, 3.0]), 2)  # alpha = 2/3
    assert np.isnan(got.iloc[0]) and np.isnan(got.iloc[1])  # one defined input < span
    assert got.iloc[2] == pytest.approx(1 + 2 / 3 * (2 - 1))  # 5/3
    assert got.iloc[3] == pytest.approx(5 / 3 + 2 / 3 * (3 - 5 / 3))  # 23/9


def test_zbt_thrust_first_cross_after_recent_setup() -> None:
    x = pd.Series([0.50, 0.39, 0.45, 0.50, 0.60, 0.62, 0.63, 0.64])
    assert br.zbt_thrust(x).tolist() == [0, 0, 0, 0, 0, 1, 0, 0]  # fires once, staying above does not re-fire
    assert br.zbt_thrust(x).dtype == np.int64
    # setup exactly 10 sessions before the cross counts; 11 sessions before does not
    assert br.zbt_thrust(pd.Series([0.39] + [0.50] * 9 + [0.62])).tolist() == [0] * 10 + [1]
    assert br.zbt_thrust(pd.Series([0.39] + [0.50] * 10 + [0.62])).tolist() == [0] * 12
    # thresholds are strict: 0.40 is not a setup, 0.615 is not a signal
    assert br.zbt_thrust(pd.Series([0.40, 0.62])).tolist() == [0, 0]
    assert br.zbt_thrust(pd.Series([0.39, 0.615])).tolist() == [0, 0]
    # NaN warm-up before the setup: the first defined cross still fires
    assert br.zbt_thrust(pd.Series([NAN, NAN, 0.39, 0.62])).tolist() == [0, 0, 0, 1]
    # a jump straight above 0.615 with no setup at all
    assert br.zbt_thrust(pd.Series([NAN, 0.70])).tolist() == [0, 0]


def test_mcclellan_oscillator_and_summation() -> None:
    rng = np.random.default_rng(7)
    net = pd.Series(np.concatenate([[NAN], rng.integers(-5, 6, 60).astype(float)]))
    osc, total = br.mcclellan(net)

    def ema_loop(values: np.ndarray, span: int) -> list[float]:
        alpha, out, level, seen = 2 / (span + 1), [], None, 0
        for v in values:
            if not np.isnan(v):
                level = v if level is None else level + alpha * (v - level)
                seen += 1
            out.append(level if seen >= span else NAN)
        return out

    expect = np.array(ema_loop(net.to_numpy(), 19)) - np.array(ema_loop(net.to_numpy(), 39))
    np.testing.assert_allclose(osc.to_numpy(), expect, equal_nan=True)
    assert osc.iloc[:39].isna().all() and osc.iloc[39:].notna().all()
    assert total.iloc[:39].isna().all()
    np.testing.assert_allclose(total.iloc[39:].to_numpy(), np.cumsum(expect[39:]))


def test_q25_counts_from_closes() -> None:
    n = 66
    flat = [100.0] * n
    up = [100.0] * 63 + [130.0] * 3  # +30% vs 63 sessions earlier on sessions 63..65
    down = [100.0] * 63 + [70.0] * 3
    out = br.market_breadth(_panel({"U1": up, "U2": up, "D": down, "F": flat}))
    assert out["up25q_count"].tolist() == [0] * 63 + [2] * 3
    assert out["down25q_count"].tolist() == [0] * 63 + [1] * 3
    assert out["q25_ratio"].iloc[:63].isna().all(), "no 25% mover either way: undefined, not 0"
    assert out["q25_ratio"].iloc[63:].tolist() == [2.0] * 3
    only_up = br.market_breadth(_panel({"U1": up, "F": flat}))
    assert only_up["q25_ratio"].iloc[63:].tolist() == [1.0] * 3  # denominator floored at 1


def test_q25_counts_read_ret_63d_column_when_present() -> None:
    panel = _panel({"X": [100.0] * 3, "Y": [100.0] * 3})
    panel["ret_63d"] = [NAN, 0.25, 0.10, NAN, -0.30, -0.25]  # X then Y, sessions 0..2
    out = br.market_breadth(panel)
    assert out["up25q_count"].tolist() == [0, 1, 0]
    assert out["down25q_count"].tolist() == [0, 1, 1]
    assert np.isnan(out["q25_ratio"].iloc[0])
    assert out["q25_ratio"].iloc[1:].tolist() == [1.0, 0.0]


def test_pct_new_highs_population_is_warm_52w_window() -> None:
    """OLD (300 bars, rising) is warm from bar 251; NEW lists 100 bars later and never has 252 bars, so it is in
    n_symbols but not in the high-low population: pct_new_highs is 100, not 50."""
    n = 300
    old = _bars("OLD", 50.0 * np.exp(np.linspace(0.0, 0.5, n)), [VOL] * n)
    new = _bars("NEW", np.linspace(80.0, 90.0, n - 100), [VOL] * (n - 100),
                start=str(old["ts"].iloc[100].date()))
    out = br.market_breadth(pd.concat([old, new], ignore_index=True))
    assert out["n_symbols"].iloc[-1] == 2
    assert out["pct_new_highs"].iloc[:251].isna().all() and out["hl_pct"].iloc[:251].isna().all()
    assert out["pct_new_highs"].iloc[251:].tolist() == [100.0] * (n - 251)
    assert out["pct_new_lows"].iloc[251:].tolist() == [0.0] * (n - 251)
    assert out["hl_pct"].iloc[251:].tolist() == [100.0] * (n - 251)


def test_empty_breadth_dtypes_match_a_built_frame() -> None:
    empty = br.empty_breadth()
    assert tuple(empty.columns) == br.BREADTH_COLUMNS and empty.index.name == "session"
    ints = {"up4_count", "down4_count", "new_highs", "new_lows", "n_symbols", "advances", "declines",
            "up25q_count", "down25q_count", "ad_line", "zbt_thrust"}
    for col in br.BREADTH_COLUMNS:
        assert empty[col].dtype == (np.int64 if col in ints else np.float64), col
    built = br.market_breadth(_panel({"A": [10.0, 11.0, 12.0], "B": [10.0, 9.0, 9.5]}))
    pd.testing.assert_series_equal(built.dtypes, empty.dtypes)


def test_regime_columns_are_causal() -> None:
    bars = gbm_bars(["AAA", "BBB", "CCC", "DDD"], n_bars=300, seed=11)
    full = br.market_breadth(bars)
    sessions = bars["ts"].sort_values().unique()
    for cut in (sessions[12], sessions[45], sessions[70], sessions[260]):
        head = br.market_breadth(bars.loc[bars["ts"] <= cut])
        pd.testing.assert_frame_equal(head, full.loc[head.index])


def test_zbt_thrust_one_signal_per_setup():
    s = pd.Series([0.5, 0.39, 0.5, 0.62, 0.6, 0.62])
    assert br.zbt_thrust(s).tolist() == [0, 0, 0, 1, 0, 0]
    s2 = pd.Series([0.5, 0.39, 0.5, 0.62, 0.6, 0.38, 0.62])
    assert br.zbt_thrust(s2).tolist() == [0, 0, 0, 1, 0, 0, 1]
