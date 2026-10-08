"""Review regression for pe_valuation_reversion: the card exits on the rule (close back at its SMA12), so the signal
carries no resting target that replay would fill intraday at the frozen signal-day SMA12."""
from __future__ import annotations

import pandas as pd

from swing_engine.core import registry
from swing_engine.features.extra import ensure_extra
from swing_engine.features.panel import build_panel


def test_signal_has_no_target():
    s = registry.get("strategy", "pe_valuation_reversion")(None)
    c = [100.0] * 30 + [92.0, 85.0]
    bars = pd.DataFrame({
        "symbol": "AAA", "ts": pd.bdate_range("2023-01-02", periods=len(c), tz="America/New_York"),
        "open": c, "high": [x * 1.005 for x in c], "low": [x * 0.995 for x in c], "close": c, "volume": 1e6,
        "vwap": c, "adj_close": c,
    })
    p = ensure_extra(build_panel(bars), s.extra_features)
    sigs = s.signals(p, p["ts"].iloc[-1].date())
    assert len(sigs) == 1
    assert sigs[0].target is None and sigs[0].reward_risk is None
    assert sigs[0].features["sma_12"] > sigs[0].entry
