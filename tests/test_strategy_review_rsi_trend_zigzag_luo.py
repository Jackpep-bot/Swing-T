"""Review regressions for rsi_trend_zigzag_luo."""
from __future__ import annotations

from swing_engine.core import registry
from swing_engine.features.extra import required_extras


def test_extra_features_follow_zz_pct():
    """Panels are built from required_extras(); a non-default zz_pct must request its own ZigZag columns, or
    held rows lack zz_trend_{n} and the trend-break exit never fires."""
    cls = registry.get("strategy", "rsi_trend_zigzag_luo")
    s = cls({"zz_pct": 3})
    assert required_extras([s]) == ["prev_rsi_14", "zz_trend_3", "zz_high_3", "zz_low_3"]
    assert set(required_extras([s])) <= set(s.required_features())
    assert required_extras([cls]) == ["prev_rsi_14", "zz_trend_5", "zz_high_5", "zz_low_5"]
