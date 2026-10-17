"""Review regressions for strategies/pivot_extension_reversal.py."""
import pytest

from swing_engine.core import registry
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, last_date

LOWS = [99.5] * 20 + [99, 98.5, 98, 97.5, 95, 96, 96.5]  # 4/2 pivot low at row 24 (95), confirmed on row 26


def run(pivot_high: float):
    rows = [[lo + 1, lo + 2, lo, lo + 1, 1e6] for lo in LOWS]
    for i in range(15, 19):
        rows[i][1] = 100.5
    rows[19][1] = pivot_high  # 4/2 pivot high at row 19
    p = add_features(bars_from_ohlc("AAA", rows, start="2024-01-02"))
    p["trend_state"] = 0.0
    return registry.get("strategy", "pivot_extension_reversal")(None).signals(p, last_date(p))


def test_pivot_high_under_rr_floor_keeps_2r_target():
    sigs = run(101.2)  # ~1.36R above the 97.5 entry: too close, so the card keeps entry + 2R
    assert len(sigs) == 1
    s = sigs[0]
    assert s.target == pytest.approx(97.5 + 2 * (97.5 - s.stop))


def test_pivot_high_between_floor_and_2r_is_the_target():
    sigs = run(102.0)  # ~1.65R: closer than 2R and >= 1.5R
    assert len(sigs) == 1 and sigs[0].target == 102.0
