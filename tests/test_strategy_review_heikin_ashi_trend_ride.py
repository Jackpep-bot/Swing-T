"""Review fixes for heikin_ashi_trend_ride: the indecision candle needs both shadows >= 0.25 x HA range (card)."""
from __future__ import annotations

import numpy as np

from swing_engine.core import registry


def _window(lower_shadow: float) -> dict[str, np.ndarray]:
    """Bars 0-3 are full-body HA candles (no shadows); bar 4 has a small body, a 0.4 upper shadow and the given
    lower shadow; bar 5 is the signal bar."""
    o = np.array([10.0, 10.0, 10.0, 10.0, 10.0, 10.0])
    c = np.array([10.5, 10.5, 9.5, 9.5, 10.1, 11.0])
    h = np.maximum(o, c)
    lo = np.minimum(o, c)
    h[4], lo[4] = 10.5, 10.0 - lower_shadow
    return {"low": np.array([9.0, 9.0, 9.0, 9.5, 9.8, 10.5]), "ha_open": o, "ha_high": h, "ha_low": lo, "ha_close": c}


def test_indecision_candle_needs_both_shadows_at_least_quarter_range():
    st = registry.get("strategy", "heikin_ashi_trend_ride")(None)
    base = 9.5 - 0.1 * 1.0  # min real low over the 2-bar down run - 0.1 x atr
    # lower shadow 0.01 of a 0.51 range: not an indecision candle, stop stays at the down-run low
    assert st.stop_level(_window(0.01), t=5, run=2, close=11.0, atr=1.0) == base
    # lower shadow 0.3 of a 0.8 range (both shadows >= 25%): stop raised to the candle's real low
    assert st.stop_level(_window(0.3), t=5, run=2, close=11.0, atr=1.0) == 9.8
