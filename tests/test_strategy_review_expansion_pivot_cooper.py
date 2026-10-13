"""Review regressions for expansion_pivot_cooper."""
from __future__ import annotations

from swing_engine.core import registry
from swing_engine.strategies._base import P_MIN_TREND


def test_no_dead_min_trend_param():
    # signals() never applies trend_ok, so advertising min_trend_state would be a silent no-op
    s = registry.get("strategy", "expansion_pivot_cooper")()
    assert P_MIN_TREND not in s.default_params
    assert "trend_state" not in s.required_features()
