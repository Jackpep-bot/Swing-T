"""research.income_view: monthly steadiness figures from an equity curve."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.research import income_view as V


def test_monthly_stats_counts_winning_months_drops_and_losing_runs() -> None:
    days = pd.bdate_range("2024-01-01", "2024-06-28")
    month = days.month.to_numpy()
    # +2% in Jan, -1% in Feb, -3% in Mar, +4% in Apr, flat in May, +1% in June, each made on the month's first day
    step = {1: 1.02, 2: 0.99, 3: 0.97, 4: 1.04, 5: 1.0, 6: 1.01}
    first = np.r_[True, month[1:] != month[:-1]]
    equity = pd.Series(100.0 * np.cumprod(np.where(first, [step[m] for m in month], 1.0)), index=days)
    equity.iloc[0] = 100.0 * 1.02
    st = V.monthly_stats(pd.concat([pd.Series([100.0], index=[pd.Timestamp("2023-12-29")]), equity]))
    assert st["months"] == 7 and st["worst_month"] == pytest.approx(-0.03) and st["losing_run"] == 2
    assert st["pos_months"] == pytest.approx(3 / 7)  # Jan, Apr, June; December's stub and flat May do not count
    assert st["max_dd"] == pytest.approx(1 - 0.99 * 0.97)
    text = V.render([{"strategy": "book", "start": "2024-01-01", "end": "2024-06-28", "equity": equity,
                      "exposure": 0.5, "trades": 12}], equity)
    assert "| book |" in text and "buy and hold SPY" in text and "50%" in text
