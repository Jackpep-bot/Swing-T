"""Review regressions for the_anti: card price-trend gate (trend_state == 1) and %K-near-%D pullback condition."""
from __future__ import annotations

import pytest

from swing_engine.core import registry
from swing_engine.features.extra import ensure_extra
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, last_date, set_last, trend_rows
from tests.test_strategy_batch_0 import set_tail

D_TAIL = [56, 58, 60, 62, 64]  # %D rising; %D[t-1] = 62
K_HOOK = [80, 75, 70, 65, 68]  # %K falls 3 bars to 65 (<= 62 + 5) then hooks up


def setup(k_tail=K_HOOK):
    s = registry.get("strategy", "the_anti")()
    p = ensure_extra(add_features(bars_from_ohlc("AAA", trend_rows(260))), s.extra_features)
    p = set_tail(set_tail(p, "AAA", "stoch_d_7_4_10", D_TAIL), "AAA", "stoch_k_7_4", k_tail)
    return s, p


def scan(s, p):
    return s.signals(p, last_date(p))


@pytest.mark.parametrize("state, fires", [(1, True), (0, False), (-1, False)])
def test_price_trend_gate(state, fires):
    s, p = setup()
    assert "trend_state" in s.required_features()
    assert bool(scan(s, set_last(p, "AAA", trend_state=state))) is fires


def test_k_must_pull_back_near_d():
    s, p = setup([99, 97, 95, 85, 88])  # falling and hooking, but 85 > 62 + 5: easing from far above %D
    assert scan(s, p) == []
    s, p = setup([99, 97, 95, 67, 70])  # 67 <= 62 + 5: boundary passes
    assert len(scan(s, p)) == 1
