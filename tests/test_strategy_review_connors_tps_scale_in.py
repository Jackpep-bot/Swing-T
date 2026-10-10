"""Review regression for connors_tps_scale_in: no bars on or before as_of yields no signals, not a KeyError."""
from __future__ import annotations

from datetime import timedelta

import pandas as pd

from swing_engine.core import registry
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, trend_rows


def test_no_rows_on_or_before_as_of_returns_empty():
    s = registry.get("strategy", "connors_tps_scale_in")(None)
    p = add_features(bars_from_ohlc("AAA", trend_rows(240, step=0.4), start="2024-01-02"))
    first = pd.Timestamp(p["ts"].min()).date()
    assert s.signals(p.iloc[0:0], first) == []  # empty panel (e.g. replay universe filter left nothing)
    assert s.signals(p, first - timedelta(days=3)) == []  # as_of before the first bar
