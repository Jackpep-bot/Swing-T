"""Review fixes for lizards_cooper: the card's minimum-range rule (range >= 0.75 x atr_14 of the prior bar)."""
from __future__ import annotations

from tests.test_strategy_batch_1 import panel_of, rows_from, run, walk


def _lizard(rng_frac: float):
    """A new 10-day low with open and close at 90% of the range; range = rng_frac x price."""
    closes = walk()
    p = closes[-1]
    lo = p * (1 - rng_frac) * 0.95  # well under the walk's lows
    hi = lo + p * rng_frac
    top = lo + 0.9 * (hi - lo)
    return panel_of([*rows_from(closes), [top, hi, lo, top, 1e6]])


def test_tiny_range_lizard_is_rejected():
    assert run("lizards_cooper", _lizard(0.0004)) == []


def test_wide_range_lizard_still_fires():
    assert len(run("lizards_cooper", _lizard(0.05))) == 1


def test_min_range_param_is_tunable():
    assert len(run("lizards_cooper", _lizard(0.0004), {"min_range_atr": 0.0, "min_stop_pct": 0.0})) == 1
