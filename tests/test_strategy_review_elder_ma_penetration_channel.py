"""Review fix: elder_ma_penetration_channel counts a penetration only after at least 3 closes above ema_21 (1-bar
re-touches while price chops around the EMA are not new dips) and averages the last 3 within 60 bars, not the
100-bar channel window."""
from __future__ import annotations

import math

import pytest

from swing_engine.core import registry
from swing_engine.strategies.elder_ma_penetration_channel import penetration_depths
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, last_date

# Sine-on-trend closes: one 2-bar dip under ema_21 every 20 bars (bars 234-235, 254-255, 274-275 in the last 60).
CLOSES = [50 + 0.3 * i + 3 * math.sin(2 * math.pi * i / 20) for i in range(285)]


def _strat():
    return registry.get("strategy", "elder_ma_penetration_channel")(None)


def _panel(lows: dict[int, float] | None = None):
    """Bars from CLOSES with the low of bar i set to ema_21[i] + lows[i] (ema_21 depends on closes only)."""
    rows = [[c, c + 0.4, c - 0.4, c, 1e6] for c in CLOSES]
    ema = add_features(bars_from_ohlc("AAA", rows))["ema_21"].to_numpy()
    for i, off in (lows or {}).items():
        rows[i][2] = ema[i] + off
    return add_features(bars_from_ohlc("AAA", rows))


def test_one_bar_retouch_is_not_a_new_dip():
    ma = [10.0] * 9
    close = [11, 11, 11, 9, 11, 9, 11, 11, 11]  # dip at bar 3, chop re-touch at bar 5 after a single close above
    low = [10.5, 10.5, 10.5, 9.0, 10.5, 9.9, 10.5, 10.5, 10.5]
    assert penetration_depths(low, close, ma, 3) == [pytest.approx(0.1)]


def test_chop_retouch_does_not_dilute_average_depth():
    s = _strat()
    (base,) = s.signals(p := _panel(), last_date(p))
    # bar 257: low pokes 0.05 under the EMA two closes after the 254-255 dip ended
    (chop,) = s.signals(q := _panel({257: -0.05}), last_date(q))
    assert chop.features["pen_depth_avg"] == pytest.approx(base.features["pen_depth_avg"])


def test_penetrations_searched_within_60_bars_only():
    s = _strat()
    p = _panel({233: 0.1, 234: 0.1, 235: 0.1})  # remove the 234-235 dip: 2 dips in 60 bars, 4 in 100
    assert s.signals(p, last_date(p)) == []
