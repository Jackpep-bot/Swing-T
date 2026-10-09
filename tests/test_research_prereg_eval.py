"""research.prereg_eval: cost top-up, net R, booked costs on the equity curve."""
from __future__ import annotations

from datetime import date

import pytest

from swing_engine.research import prereg_eval as pe


def test_top_up_charges_only_above_the_replay_cost() -> None:
    payload = {
        "trades": [{"symbol": "A", "signal_date": "2025-01-02T00:00:00", "exit_ts": "2025-01-10T04:00:00Z", "qty": 100,
                    "entry_price": 10.0, "exit_price": 12.0, "initial_stop": 9.0, "pnl": 200.0, "bars_held": 5}],
        "equity_curve": [{"ts": f"2025-01-{d:02d}T04:00:00Z", "equity": 100_000.0 + (200.0 if d >= 10 else 0.0),
                          "exposure": 0.01} for d in range(2, 15)],
    }
    costs = {("A", date(2025, 1, 2)): 30.0, ("A", date(2025, 1, 10)): 10.0}  # 20 bp extra on entry only
    g = pe.grade_run(payload, costs)
    # extra = 0.002 x 10 x 100 = $2 -> net R = (200 - 2) / (100 x 1) = 1.98
    assert g["trades"] == 1 and g["net_r"] == pytest.approx(1.98)
    assert g["total_return"] == pytest.approx((100_198.0) / 100_000.0 - 1.0)
    assert g["exposure"] == pytest.approx(0.01)
