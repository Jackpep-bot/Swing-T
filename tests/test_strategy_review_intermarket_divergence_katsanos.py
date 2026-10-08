"""Review regressions for intermarket_divergence_katsanos: the 15-day-low exit fires only while the pair has
decoupled (thinkorswim BBDivergenceStrat: corr_20 < -0.4), read from features.extra `corr_market_<corr_len>`."""
from __future__ import annotations

import pandas as pd

from swing_engine.strategies import intermarket_divergence_katsanos as mod


def test_low_15_exit_needs_negative_correlation():
    s = mod.IntermarketDivergenceKatsanos()
    assert "corr_market_20" in s.extra_features
    at_low = {"close": 10.0, "min_15_of_close": 10.0}
    assert s.should_exit(pd.Series({**at_low, "corr_market_20": -0.5}), 1)
    assert not s.should_exit(pd.Series({**at_low, "corr_market_20": 0.3}), 1)
    assert not s.should_exit(pd.Series(at_low), 1)  # no correlation yet: no 15-day-low exit
    assert not s.should_exit(pd.Series({"close": 10.5, "min_15_of_close": 10.0, "corr_market_20": -0.5}), 1)
    assert mod.IntermarketDivergenceKatsanos({"corr_len": 30}).extra_features[-1] == "corr_market_30"
