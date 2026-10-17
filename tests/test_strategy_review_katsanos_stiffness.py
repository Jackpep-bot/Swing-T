"""Review regressions for katsanos_stiffness: param-dependent extras reach the engine panel."""
from __future__ import annotations

from swing_engine.features.extra import ensure_extra, required_extras
from swing_engine.strategies.katsanos_stiffness import KatsanosStiffness
from tests.fixtures.strategies.panel import make_panel


def test_extras_follow_params_so_exit_sees_column():
    s = KatsanosStiffness({"stiffness_col": "stiffness_40_100", "market_ema_col": None})
    assert required_extras([s]) == ["stiffness_40_100"]
    panel = ensure_extra(make_panel(("AAA",), n_days=200, seed=3), required_extras([s]))
    row = panel.iloc[-1].copy()
    assert "stiffness_40_100" in row.index  # engine panel row now carries the exit column
    row["stiffness_40_100"] = 10.0
    assert s.should_exit(row, 5)
    assert required_extras([KatsanosStiffness()]) == ["stiffness_60_100", "ema_100_of_market_close"]
    assert KatsanosStiffness.extra_features == ["stiffness_60_100", "ema_100_of_market_close"]  # class default kept
