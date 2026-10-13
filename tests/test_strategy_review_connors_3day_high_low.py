"""Review fixes for connors_3day_high_low: rule exit only (no resting target), and a non-base exit/trend MA param
is attached as an extra feature."""
from __future__ import annotations

from swing_engine.core import registry
from swing_engine.features.extra import ensure_extra, required_extras
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, last_date, trend_rows

TAIL = [[182.0, 182.5, 181.0, 181.2, 1e6], [181.0, 181.8, 180.0, 180.3, 1e6], [180.2, 181.0, 179.0, 179.5, 1e6]]


def _signals(params: dict | None = None):
    s = registry.get("strategy", "connors_3day_high_low")(params)
    panel = add_features(bars_from_ohlc("AAA", trend_rows(257) + TAIL))
    return s, s.signals(ensure_extra(panel, required_extras([s])), last_date(panel))


def test_no_target_exit_is_close_above_sma5():
    _, sigs = _signals()
    assert len(sigs) == 1 and sigs[0].target is None


def test_non_base_exit_ma_is_attached():
    s, sigs = _signals({"exit_ma": "sma_3"})
    assert "sma_3" in s.extra_features
    assert len(sigs) == 1 and sigs[0].features["sma_3"] > sigs[0].entry
