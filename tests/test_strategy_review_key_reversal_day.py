"""Review fixes for key_reversal_day: docs/strategies/key_reversal_day.md."""
from __future__ import annotations

from datetime import timedelta

from swing_engine.core import registry
from swing_engine.features.extra import ensure_extra
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, last_date, trend_rows


def test_empty_panel_and_as_of_before_first_bar_give_no_signals():
    s = registry.get("strategy", "key_reversal_day")()
    panel = ensure_extra(add_features(bars_from_ohlc("AAA", trend_rows(240))), s.extra_features)
    first = panel["ts"].min().date()
    assert s.signals(panel.iloc[0:0], last_date(panel)) == []
    assert s.signals(panel, first - timedelta(days=3)) == []
