"""Review fixes for pendergast_long_haul: the card's trend_state = 1 stock filter is on by default, and the panel
builders attach the instance's fast/slow MAs so the 'close < fast MA' exit can fire on replay/live rows."""
from __future__ import annotations

from swing_engine.features.extra import ensure_extra, required_extras
from swing_engine.strategies._base import P_MIN_TREND, TREND_DOWN, TREND_UP
from swing_engine.strategies.pendergast_long_haul import PendergastLongHaul
from tests.test_strategy_batch_1 import _long_haul, run


def test_default_requires_uptrend_state():
    assert PendergastLongHaul().params[P_MIN_TREND] == TREND_UP
    panel = _long_haul(True)
    assert len(run("pendergast_long_haul", panel)) == 1  # trend_state 1 on the breakout bar
    panel.loc[panel.index[-1], "trend_state"] = 0.0  # above sma_50 but not a full uptrend
    assert run("pendergast_long_haul", panel) == []
    assert len(run("pendergast_long_haul", panel, {P_MIN_TREND: TREND_DOWN})) == 1


def test_panel_builders_attach_instance_mas():
    st = PendergastLongHaul({"fast_ma": "sma_5", "slow_ma": "hma_10"})
    assert {"low_3", "sma_5", "hma_10"} <= set(required_extras([st]))
    row = ensure_extra(_long_haul(True), required_extras([st])).iloc[-1].copy()  # what replay/live hand should_exit
    row["close"] = row["sma_5"] - 1.0
    assert st.should_exit(row, 1)
