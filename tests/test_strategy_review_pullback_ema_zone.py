"""Review regressions for pullback_ema_zone: earlier bars of the current dip are not prior zone tests."""
from __future__ import annotations

from tests.test_strategy_batch_0 import _zone_panel, only, run, strat


def test_multi_bar_dip_is_not_a_prior_test():
    s = strat("pullback_ema_zone")
    assert run(s, _zone_panel([60, 99, 100])) == []  # touched once before this dip: second pullback, no fire
    sig = only(run(s, _zone_panel([40, 60, 99, 100])))  # two earlier tests, then a two-bar dip: third pullback
    assert sig.features["prior_tests"] == 2.0
