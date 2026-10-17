"""Review regressions for strategies/weinstein_stage2_breakout.py."""
from __future__ import annotations

import pytest

from swing_engine.core import registry
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, last_date


def _panel():
    # 39 flat weeks (the 39th on 2x daily volume) then a breakout week on 3x: weekly volumes ..., 5e6, 10e6, 15e6.
    rows = [[100 + 0.01 * i, 100.5 + 0.01 * i, 99.5 + 0.01 * i, 100 + 0.01 * i, 2e6 if i >= 190 else 1e6]
            for i in range(195)]
    rows += [[102 + i, 103.5 + i, 101.5 + i, 103 + i, 3e6] for i in range(5)]
    p = add_features(bars_from_ohlc("AAA", rows, start="2024-01-08"))
    p["mansfield_rs"], p["sma_150"] = 5.0, 90.0
    return p


def test_volume_average_window_is_a_param():
    cls = registry.get("strategy", "weinstein_stage2_breakout")
    assert cls.default_params["vol_avg_weeks"] == 4
    p = _panel()
    sigs = cls(None).signals(p, last_date(p))  # prior 4 weeks average 6.25e6 -> 2.4x
    assert len(sigs) == 1 and sigs[0].features["wk_vol_ratio_4"] == pytest.approx(2.4)
    assert cls({"vol_avg_weeks": 1}).signals(p, last_date(p)) == []  # prior week alone 10e6 -> 1.5x < 2x
