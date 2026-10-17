"""Review regressions for strategies/bull_flag_breakout.py."""
from __future__ import annotations

import pytest

from swing_engine.core import registry
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, last_date, trend_rows


def _panel(flag_bars: int):
    """Uptrend, 10-bar pole (+2 a bar), ``flag_bars`` flat bars under the pole top, then a breakout bar."""
    rows = trend_rows(230, start=60.0, step=0.1)
    c = rows[-1][3]
    for _ in range(10):
        rows.append([c, c + 2.2, c - 0.1, c + 2, 1e6])
        c += 2
    rows += [[c - 0.6, c - 0.3, c - 1.3, c - 0.8, 1e6] for _ in range(flag_bars)]
    rows.append([c - 0.8, c + 0.5, c - 0.9, c + 0.4, 2e6])  # closes over the pole top (c + 0.2)
    return add_features(bars_from_ohlc("AAA", rows))


def _signals(flag_bars: int):
    p = _panel(flag_bars)
    return registry.get("strategy", "bull_flag_breakout")(None).signals(p, last_date(p))


def test_flag_within_limit_fires():
    (sig,) = _signals(12)
    assert sig.features["flag_len"] == 13 and sig.features["pivot"] == pytest.approx(sig.entry - 0.2)


@pytest.mark.parametrize("flag_bars", [20, 25, 30])
def test_flag_longer_than_flag_max_bars_is_rejected(flag_bars):
    # Before the fix the 15-bar window took an in-flag bar as the pivot and fired a 13-15 bar "flag".
    assert _signals(flag_bars) == []
