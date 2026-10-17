"""strategies._b5: the SMALLMID universe mask."""
from __future__ import annotations

import numpy as np
import pandas as pd

from swing_engine.strategies import _b5


def test_smallmid_is_a_market_cap_band_with_price_and_liquidity_floors() -> None:
    n = 3200
    rows = pd.DataFrame({"symbol": [f"S{i}" for i in range(n)], "close": 10.0, "med_dv_63": 5e6,
                         "mcap_pit": np.linspace(1e11, 1e7, n)})
    rows.loc[600, "close"] = 2.0  # under $3
    rows.loc[700, "med_dv_63"] = 5e5  # under $1M a day
    rows.loc[800, "mcap_pit"] = np.nan  # a fund: no filed share count
    mask = _b5.smallmid(rows)
    assert not mask.iloc[:500].any() and mask.iloc[500] and mask.iloc[2999]  # rank 501 is the first one in
    assert not mask.iloc[[600, 700, 800]].any()
    assert mask.sum() == 2500 - 3 + 1 and not mask.iloc[3001:].any()  # dropping the fund pulls rank 3,000 one row down
    assert not _b5.smallmid(rows.drop(columns="mcap_pit")).any()
