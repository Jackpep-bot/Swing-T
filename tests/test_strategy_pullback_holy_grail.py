"""pullback_holy_grail: Raschke Holy Grail rules, and the patterns2 features it reads (ADX, ema_20) being causal."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.features import build_panel
from swing_engine.features.patterns2 import (
    PATTERNS2_COLUMNS,
    add_patterns2,
    adx,
    as_of_view,
    patterns2_frame,
)
from swing_engine.strategies.pullback_holy_grail import PullbackHolyGrail
from tests.features_gbm import gbm_bars
from tests.fixtures.strategies.panel import bars_from_ohlc, last_date

SYM = "HG"
BASE_BARS = 230
TREND_BARS = 30


def _ema20(closes: list[float]) -> float:
    return float(pd.Series(closes).ewm(span=20, adjust=False, min_periods=20).mean().iloc[-1])


def _setup_rows(extra: list[list[float]] | None = None) -> list[list[float]]:
    """Random-walk base, a 30-bar thrust (ADX > 30 and rising), a quiet dip whose low touches ema_20, then a
    trigger bar closing 1.0 above the touch-bar high."""
    rng = np.random.default_rng(5)
    out: list[list[float]] = []
    c = 50.0
    for _ in range(BASE_BARS):
        o, c = c, c * (1 + rng.normal(0.0005, 0.01))
        out.append([o, max(o, c) * 1.004, min(o, c) * 0.996, c, 1e6])
    for _ in range(TREND_BARS):
        o, c = c, c + 1.0
        out.append([o, c + 0.2, o - 0.2, c, 1.5e6])
    for _ in range(10):
        closes = [r[3] for r in out]
        e = _ema20(closes)
        o, nc = c, c - 2.0
        if nc - 0.3 <= e * 1.01:
            ce = _ema20([*closes, e + 0.5])
            out.append([o, o + 0.1, ce, ce + 0.5, 8e5])  # touch bar: low on the ema, close just above
            c = ce + 0.5
            break
        out.append([o, o + 0.1, nc - 0.3, nc, 8e5])
        c = nc
    touch_high = out[-1][1]
    out.append([c + 1.0, touch_high + 1.5, c + 0.9, touch_high + 1.0, 1.2e6])  # trigger bar clears the ema band
    return out + (extra or [])


def _panel(rows: list[list[float]]) -> pd.DataFrame:
    return build_panel(bars_from_ohlc(SYM, rows))


@pytest.fixture(scope="module")
def setup_panel() -> pd.DataFrame:
    return _panel(_setup_rows())


def test_registered_with_defaults() -> None:
    cls = registry.get("strategy", "pullback_holy_grail")
    assert cls is PullbackHolyGrail
    strat = cls()
    assert strat.params["adx_min"] == 30.0 and strat.params["pullback_ma"] == "ema_20"
    assert "min_reward_risk" in strat.default_params and strat.params["max_hold_days"] == 10
    assert {"adx_14", "plus_di_14", "minus_di_14", "ema_20"} <= set(strat.required_features())


def test_signal_geometry(setup_panel: pd.DataFrame) -> None:
    rows = _setup_rows()
    sigs = PullbackHolyGrail().signals(setup_panel, last_date(setup_panel))
    assert len(sigs) == 1
    s = sigs[0]
    touch = rows[-2]
    swing_high = max(r[1] for r in rows[-2 - 20 : -2])
    assert s.entry == pytest.approx(rows[-1][3])
    assert s.stop == pytest.approx(touch[2])  # touch-bar low
    assert s.target == pytest.approx(swing_high)  # prior swing high
    assert s.reward_risk == pytest.approx((swing_high - s.entry) / (s.entry - s.stop))
    assert s.features["touch_age"] == 1.0 and s.features["adx_14"] >= 30.0
    assert s.features["plus_di_14"] > s.features["minus_di_14"]


def test_adx_threshold_and_touch_tolerance_are_params(setup_panel: pd.DataFrame) -> None:
    as_of = last_date(setup_panel)
    assert PullbackHolyGrail({"adx_min": 95.0}).signals(setup_panel, as_of) == []
    assert PullbackHolyGrail({"touch_pct": -0.01}).signals(setup_panel, as_of) == []  # low must undercut by 1%
    assert PullbackHolyGrail({"min_reward_risk": 5.0}).signals(setup_panel, as_of) == []


def test_leader_and_uptrend_gates(setup_panel: pd.DataFrame) -> None:
    """methods.md 6.1 / 3c: leaders only (RS 96+ or near the 52-week high) and trend_state up."""
    as_of = last_date(setup_panel)
    strat = PullbackHolyGrail()
    assert strat.params["min_trend_state"] == 1 and strat.params["rs_rank_min"] == 0.96
    laggard = setup_panel.copy()
    last = laggard["ts"] == laggard["ts"].max()
    laggard.loc[last, "rs_63d_rank"] = 0.40  # not an RS leader ...
    laggard.loc[last, "dist_52w_high"] = -0.30  # ... and 30% below its 52-week high
    assert strat.signals(laggard, as_of) == []
    near_high = laggard.copy()
    near_high.loc[last, "dist_52w_high"] = -0.05  # within 10% of the high: still a leader
    assert len(strat.signals(near_high, as_of)) == 1
    off = PullbackHolyGrail({"rs_rank_min": None, "max_dist_52w_high_pct": None})
    assert len(off.signals(laggard, as_of)) == 1
    flat = setup_panel.copy()
    flat.loc[flat["ts"] == flat["ts"].max(), "trend_state"] = 0  # below its 200-day / no proper order
    assert strat.signals(flat, as_of) == []


def test_no_signal_without_close_over_touch_high() -> None:
    rows = _setup_rows()
    touch_high = rows[-2][1]
    rows[-1] = [rows[-1][0], touch_high + 0.2, rows[-1][2], touch_high - 0.1, 1.2e6]
    panel = _panel(rows)
    assert PullbackHolyGrail().signals(panel, last_date(panel)) == []


def test_only_the_first_close_over_the_touch_high_triggers() -> None:
    rows = _setup_rows()
    last = rows[-1][3]
    panel = _panel([*rows, [last, last + 1.0, last - 0.2, last + 0.8, 1.2e6]])
    assert PullbackHolyGrail().signals(panel, last_date(panel)) == []


def test_point_in_time_future_bars_do_not_change_the_signal(setup_panel: pd.DataFrame) -> None:
    rows = _setup_rows()
    as_of = last_date(setup_panel)
    last = rows[-1][3]
    future = [[last, last + 9.0, last - 9.0, last + 5.0 * (-1) ** i, 9e6] for i in range(15)]
    longer = _panel([*rows, *future])
    a = PullbackHolyGrail().signals(setup_panel, as_of)
    b = PullbackHolyGrail().signals(longer, as_of)
    assert [s.model_dump() for s in a] == [s.model_dump() for s in b] and len(a) == 1


def test_should_exit_time_and_optional_ma() -> None:
    strat = PullbackHolyGrail()
    row = pd.Series({"close": 90.0, "sma_50": 95.0})
    assert not strat.should_exit(row, bars_held=9)
    assert strat.should_exit(row, bars_held=10)
    assert PullbackHolyGrail({"exit_ma": "sma_50"}).should_exit(row, bars_held=1)
    assert not PullbackHolyGrail({"exit_ma": "sma_50"}).should_exit(pd.Series({"close": 99.0, "sma_50": 95.0}), 1)


# --------------------------------------------------------------------------- features/patterns2.py (causal)
@pytest.fixture(scope="module")
def gbm() -> pd.DataFrame:
    return gbm_bars(["AAA", "BBB", "CCC", "DDD"], n_bars=320, seed=13)


def test_add_patterns2_columns_and_adx_reference(gbm: pd.DataFrame) -> None:
    out = add_patterns2(gbm.sort_values(["symbol", "ts"]).reset_index(drop=True))
    assert set(PATTERNS2_COLUMNS) <= set(out.columns)
    one = out[out.symbol == "BBB"].reset_index(drop=True)
    ref = adx(one.high, one.low, one.close)
    np.testing.assert_allclose(one["adx_14"], ref["adx"], rtol=1e-12, equal_nan=True)
    np.testing.assert_allclose(one["plus_di_14"], ref["plus_di"], rtol=1e-12, equal_nan=True)
    assert one["adx_14"].iloc[60:].between(0, 100).all()
    adr = (one.high / one.low).rolling(20).mean() - 1
    np.testing.assert_allclose(one["adr_pct_20"], adr, rtol=1e-12, equal_nan=True)
    prev_avg = one.volume.rolling(50).mean().shift(1)
    np.testing.assert_allclose(one["avg_vol_50d_prev"], prev_avg, rtol=1e-12, equal_nan=True)
    ranks = out.dropna(subset=["rs_63d_rank"]).groupby("ts")["rs_63d_rank"]
    assert (ranks.max() == 1.0).all() and (ranks.min() == 0.25).all()


def test_patterns2_truncation_is_point_in_time(gbm: pd.DataFrame) -> None:
    full = add_patterns2(gbm.sort_values(["symbol", "ts"]).reset_index(drop=True))
    for cut in sorted(gbm.ts.unique())[250::30]:
        trunc = add_patterns2(gbm[gbm.ts <= cut].sort_values(["symbol", "ts"]).reset_index(drop=True))
        part = full[full.ts <= cut].reset_index(drop=True)
        pd.testing.assert_frame_equal(part[list(PATTERNS2_COLUMNS)], trunc[list(PATTERNS2_COLUMNS)], rtol=1e-9)


def test_patterns2_frame_uses_panel_columns_or_caches(gbm: pd.DataFrame) -> None:
    panel = build_panel(gbm)
    first = patterns2_frame(panel)
    assert patterns2_frame(panel) is first  # same object -> cached
    assert first.index.equals(panel.index)
    shuffled = panel.sample(frac=1.0, random_state=1)
    pd.testing.assert_frame_equal(patterns2_frame(shuffled).loc[panel.index], first)
    with_cols = add_patterns2(panel)
    assert patterns2_frame(with_cols) is not first
    view = as_of_view(with_cols, panel.ts.iloc[200].date(), ["close", "adx_14"])
    assert len(view.current) == 4 and view.frame.ts.max() == panel.ts.iloc[200]
    with pytest.raises(KeyError):
        as_of_view(panel, panel.ts.iloc[200].date(), ["not_a_column"])
