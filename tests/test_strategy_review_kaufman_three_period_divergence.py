"""Review regressions for kaufman_three_period_divergence."""
from __future__ import annotations

from swing_engine.features.extra import required_extras
from swing_engine.strategies.kaufman_three_period_divergence import KaufmanThreePeriodDivergence


def test_extras_follow_periods_and_momentum_params():
    s = KaufmanThreePeriodDivergence({"periods": [5, 8, 12], "momentum": "stoch_k_9"})
    assert required_extras([s]) == [
        "linreg_slope_5", "linreg_slope_5_of_stoch_k_9", "linreg_slope_8", "linreg_slope_8_of_stoch_k_9",
        "linreg_slope_12", "linreg_slope_12_of_stoch_k_9",
    ]
    # every column should_exit reads is attached by replay / nightly
    assert set(s.required_features()) - set(s.features_required) <= set(required_extras([s]))
    # class-level default listing unchanged
    assert set(required_extras([KaufmanThreePeriodDivergence])) == set(KaufmanThreePeriodDivergence().extra_features)
