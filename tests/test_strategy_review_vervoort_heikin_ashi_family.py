"""Review fixes for vervoort_heikin_ashi_family: SVESC also exits a long on Sell Auto (A crosses below B, bearish bar)."""
from __future__ import annotations

import pandas as pd

from swing_engine.core import registry


def test_svesc_exits_on_sell_auto_cross_with_close_above_exit_sma():
    st = registry.get("strategy", "vervoort_heikin_ashi_family")({"variant": "svesc"})
    c = st.cols
    # A crosses below B on a bearish bar, but close 10.5 is above SMA_5 10.0, so Sell To Close does not fire
    row = pd.Series({"close": 10.5, "open": 11.0, c["a"]: 10.4, c["b"]: 10.6, c["a_prev"]: 10.7, c["b_prev"]: 10.6,
                     c["exit"]: 10.0})
    assert st.should_exit(row, bars_held=1)
    # no cross (A still above B) and close above SMA_5: stays open
    assert not st.should_exit(row.replace({10.4: 10.65}), bars_held=1)
