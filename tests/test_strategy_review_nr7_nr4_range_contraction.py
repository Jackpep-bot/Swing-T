"""Review regressions for nr7_nr4_range_contraction."""
from __future__ import annotations

import pytest

from swing_engine.core import registry
from swing_engine.features.extra import ensure_extra
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, last_date, trend_rows


def test_variant_b_uses_card_bracket_stop():
    """Card variant B (Bulkowski): target entry x 1.07 and stop entry x 0.93, not low - tick."""
    s = registry.get("strategy", "nr7_nr4_range_contraction")(
        {"target_pct": 0.07, "stop_pct": 0.07, "max_hold_days": 40})
    rows = trend_rows(240)
    c = rows[-1][3]
    panel = ensure_extra(add_features(bars_from_ohlc("AAA", [*rows[:-1], [c, c + 0.05, c - 0.05, c, 1e6]])),
                         s.extra_features)
    (sig,) = s.signals(panel, last_date(panel))
    entry = c + 0.06
    assert sig.entry == pytest.approx(entry)
    assert sig.target == pytest.approx(entry * 1.07)
    assert sig.stop == pytest.approx(entry * 0.93)
