"""Review regressions for calhoun_adx_breakout."""
from __future__ import annotations

from swing_engine.core import registry
from swing_engine.features.extra import ensure_extra
from swing_engine.strategies._base import TREND_DOWN, TREND_FLAT, TREND_UP
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, last_date, set_last, trend_rows

NAME = "calhoun_adx_breakout"
TRIGGER = {"adx_14": 42, "prev_adx_14": 38, "plus_di_14": 30, "minus_di_14": 10}


def _fire(min_trend: int, trend_state: float) -> int:
    s = registry.get("strategy", NAME)({"min_trend_state": min_trend})
    p = ensure_extra(add_features(bars_from_ohlc("AAA", trend_rows(60, start=50, step=1.5))), s.extra_features)
    p = set_last(p, "AAA", **TRIGGER, trend_state=trend_state)
    return len(s.signals(p, last_date(p)))


def test_min_trend_state_gates_signals():
    assert _fire(TREND_UP, TREND_FLAT) == 0  # raised gate blocks a flat trend
    assert _fire(TREND_UP, TREND_UP) == 1
    assert _fire(TREND_FLAT, float("nan")) == 0  # warm-up never passes a raised gate
    assert _fire(TREND_DOWN, float("nan")) == 1  # default leaves the gate off, warm-up still fires
