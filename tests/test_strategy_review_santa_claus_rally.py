"""Review fixes for santa_claus_rally: the calendar hold opts out of the engine breakeven/trail overlay."""
from __future__ import annotations

from swing_engine.research.backtest import strategy_engine_trail
from swing_engine.strategies.santa_claus_rally import SantaClausRally


def test_santa_claus_rally_opts_out_of_engine_trail():
    # card: exit at the 2nd January close (max_hold_days 7) or the 3 x atr_14 stop; no breakeven/10-day-low trail
    assert strategy_engine_trail(SantaClausRally()) is False
