"""Review regressions for slope_performance_trend: lookback-dependent extras and the flat-start entry."""
from __future__ import annotations

import numpy as np

from swing_engine.features.extra import required_extras
from swing_engine.strategies.slope_performance_trend import SlopePerformanceTrend
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, last_date

FLAT = [100.0, 100.5, 99.5, 100.0, 1e6]


def test_extras_follow_lookback():
    s = SlopePerformanceTrend({"lookback": 63})
    assert required_extras([s]) == ["linreg_slope_63", "linreg_slope_63_of_rs_line"]
    assert required_extras([SlopePerformanceTrend()]) == ["linreg_slope_252", "linreg_slope_252_of_rs_line"]


def test_flat_start_buys_first_both_positive_bar():
    p = add_features(bars_from_ohlc("AAA", [FLAT] * 30))
    slope = np.full(len(p), np.nan)  # warm-up: no unmixed state before bar 25
    slope[25:] = 1.0
    p["linreg_slope_252"] = slope
    p["linreg_slope_252_of_rs_line"] = slope
    s = SlopePerformanceTrend()
    assert len(s.signals(p, p["ts"].iloc[25].date())) == 1  # flat start: first both-positive bar
    assert s.signals(p, last_date(p)) == []  # later both-positive bars: already long
