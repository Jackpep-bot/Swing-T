"""Review fix: wyckoff_spring_accumulation's SOS volume test is rvol_day >= 1.5, measured against the prior 20-bar
average; dividing by avg_vol_20d (which includes the SOS bar) raised the bar to ~1.54x and dropped borderline LPS."""
from __future__ import annotations

from tests.test_strategy_batch_4 import _wyckoff_rows, day, fire, ohlc, panel_for, strat


def test_sos_at_1_52x_prior_average_volume_counts():
    s = strat("wyckoff_spring_accumulation", entries=["lps"])
    rows = _wyckoff_rows(4e5)[:-4]  # box bars all trade 1e6
    rows.append([113.0, 117.5, 112.8, 117.0, 1.52e6])  # SOS: rvol_day 1.52, but 1.52e6 / avg_vol_20d ~ 1.48
    rows.append([117.0, 117.4, 115.5, 116.0, 8e5])  # quiet pullback above the TR high
    p = panel_for(s, ohlc("AAA", rows))
    assert abs(float(p["rvol_day"].iloc[-2]) - 1.52) < 1e-9
    assert fire(s, p, day(p)).features["lps"] == 1.0
