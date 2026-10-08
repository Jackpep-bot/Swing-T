"""Review regression: price_zone_oscillator exits by ADX mode (card LX trend vs non-trend)."""
from __future__ import annotations

import pandas as pd

from swing_engine.core import registry


def _row(pzo: float, prev: float, adx: float, close: float = 9.0, ema: float = 10.0) -> pd.Series:
    return pd.Series({"close": close, "pzo_14": pzo, "prev_pzo_14": prev, "ema_60": ema, "adx_14": adx})


def test_range_mode_oversold_recovery_does_not_exit_on_first_held_close():
    s = registry.get("strategy", "price_zone_oscillator")(None)
    # range-mode cross_oversold entry (-45 -> -35), close still below EMA60: the old fold exited here
    assert not s.should_exit(_row(-33.0, -35.0, adx=10.0), 1)
    assert not s.should_exit(_row(-33.0, -35.0, adx=float("nan")), 1)  # NaN ADX treated as range
    # trend mode keeps the card's trend LX: close < EMA60 and PZO < 0
    assert s.should_exit(_row(-33.0, -35.0, adx=30.0), 1)


def test_range_mode_exit_crosses():
    s = registry.get("strategy", "price_zone_oscillator")(None)
    assert s.should_exit(_row(-2.0, 5.0, adx=10.0), 3)  # down through 0 with close < EMA60
    assert not s.should_exit(_row(-2.0, 5.0, adx=10.0, close=11.0), 3)  # ... but close above EMA60
    assert s.should_exit(_row(-6.0, 3.0, adx=10.0, close=11.0), 3)  # down through -5 (fail level)
    assert s.should_exit(_row(50.0, 65.0, adx=10.0, close=11.0), 3)  # +60 turn-down, both modes
