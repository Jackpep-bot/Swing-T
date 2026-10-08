"""Review fix: volatility_expansion_close filters on trend_state >= 1 by default (card's comparison run)."""
from __future__ import annotations

from tests.test_strategy_batch_1 import panel_of, row_of, rows_from, run, walk

NAME = "volatility_expansion_close"


def test_default_requires_uptrend_but_raw_form_still_fires():
    panel = panel_of(rows_from(walk(up=-0.004, down=0.002)))  # mild downtrend, finite ATR5
    row = row_of(panel, NAME)
    assert row["trend_state"] < 1 and row["atr_sma_5"] > 0
    assert run(NAME, panel) == []
    assert len(run(NAME, panel, {"min_trend_state": -1})) == 1
