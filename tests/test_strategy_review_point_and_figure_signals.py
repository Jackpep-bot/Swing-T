"""Review fix: point_and_figure_signals raised KeyError on `prior_pf_dir` for an empty panel or an as_of before the
first bar, because rows_as_of returns the bare empty frame without the prior_* helper columns."""
from __future__ import annotations

from datetime import date

from swing_engine.core import registry
from swing_engine.features.extra import ensure_extra
from tests.fixtures.strategies.panel import add_features, bars_from_closes


def test_empty_slice_returns_no_signals():
    s = registry.get("strategy", "point_and_figure_signals")(None)
    panel = ensure_extra(add_features(bars_from_closes("AAA", [100.0 + i % 7 for i in range(260)])), s.extra_features)
    assert s.signals(panel.iloc[0:0], date(2024, 6, 3)) == []
    assert s.signals(panel, date(1990, 1, 2)) == []  # as_of before the first bar
