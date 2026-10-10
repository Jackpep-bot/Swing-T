"""Review regression for rsi_oversold_macd_confirm: RSI cross back over 30 counts when bars-since <= pair_window (5)."""
from __future__ import annotations

import pytest

from swing_engine.core import registry
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, last_date, set_last, trend_rows
from tests.test_strategy_batch_0 import set_tail


@pytest.mark.parametrize("bars_since, fires", [(4, True), (5, True), (6, False)])
def test_rsi_cross_pair_window_inclusive(bars_since, fires):
    s = registry.get("strategy", "rsi_oversold_macd_confirm")()
    rsi = [25.0] * (10 - bars_since) + [35.0 + 5 * i for i in range(bars_since + 1)]  # bars t-10..t, cross at t-k
    p = set_tail(add_features(bars_from_ohlc("AAA", trend_rows(120))), "AAA", "rsi_14", rsi)
    p = set_last(p, "AAA", macd=1.0, macd_signal=0.5, prev_macd=-0.5, prev_macd_signal=0.0)
    assert bool(s.signals(p, last_date(p))) is fires
