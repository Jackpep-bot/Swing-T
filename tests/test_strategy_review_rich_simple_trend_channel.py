"""Review regressions for rich_simple_trend_channel."""
from __future__ import annotations

from datetime import date

from swing_engine.core import registry
from tests.fixtures.strategies.panel import make_panel


def test_as_of_before_first_bar_returns_no_signals():
    strat = registry.get("strategy", "rich_simple_trend_channel")()
    assert strat.signals(make_panel(), date(2000, 1, 3)) == []
