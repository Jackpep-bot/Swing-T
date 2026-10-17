"""Review regression for cci_correction: the dip lookback is the card's 10 bars (t-9..t), not 11."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.core import registry

N = 20


def _panel(dip_bar: int) -> pd.DataFrame:
    """Bias up (CCI(100) = 150); CCI(26) = -50 except one dip of -150 at ``dip_bar`` bars before the trigger."""
    cci = np.full(N, -50.0)
    cci[-1 - dip_bar], cci[-2], cci[-1] = -150.0, -10.0, 20.0
    low = np.full(N, 100.0)
    low[-1 - dip_bar], low[-11] = 95.0, 90.0  # bar t-10 holds a lower low the stop must not reach when unused
    return pd.DataFrame({
        "symbol": "AAA", "ts": pd.bdate_range("2023-01-02", periods=N, tz="America/New_York"),
        "open": 101.0, "high": 102.0, "low": low, "close": 101.0, "cci_26": cci, "cci_100": 150.0,
        "prev_cci_26": np.r_[np.nan, cci[:-1]], "atr_14": 2.0,
    })


@pytest.mark.parametrize("dip_bar, fires", [(9, True), (10, False)])
def test_dip_lookback_is_ten_bars(dip_bar, fires):
    s = registry.get("strategy", "cci_correction")(None)
    p = _panel(dip_bar)
    sigs = s.signals(p, p["ts"].iloc[-1].date())
    assert len(sigs) == int(fires)
    if fires:
        assert sigs[0].stop == pytest.approx(95.0 - 0.1 * 2.0)
