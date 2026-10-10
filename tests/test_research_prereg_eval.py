"""research.prereg_eval: cost top-up, net R, booked costs on the equity curve."""
from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing_engine.research import prereg_eval as pe
from swing_engine.research.cards import WINDOWS


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


def test_build_report_for_another_group(tmp_path) -> None:
    """--slugs / --tag-prefix / --n-trials: files are found by tag prefix, the haircut uses the group's n_trials,
    a missing window fails the strategy; the three-pick defaults are unchanged."""
    rng = np.random.default_rng(0)
    days = pd.bdate_range("2025-01-02", periods=300)
    equity = 100_000.0 * (1.0 + rng.normal(0.002, 0.005, len(days))).cumprod()
    payload = {
        "trades": [{"symbol": "A", "signal_date": "2025-01-02T00:00:00", "exit_ts": "2025-01-10T04:00:00Z", "qty": 100,
                    "entry_price": 10.0, "exit_price": 12.0, "initial_stop": 9.0, "pnl": 200.0, "bars_held": 5}],
        "equity_curve": [{"ts": d.isoformat(), "equity": float(e)} for d, e in zip(days, equity, strict=True)],
    }
    for w in WINDOWS:
        (tmp_path / f"{w.start.isoformat()}_{w.end.isoformat()}_prereg2-good.json").write_text(json.dumps(payload))
    w = WINDOWS[0]
    (tmp_path / f"{w.start.isoformat()}_{w.end.isoformat()}_prereg2-half.json").write_text(json.dumps(payload))
    lines = pe.build_report(tmp_path, {}, ("good", "half"), "prereg2-", 2, "docs/preregistration/x-results.md")
    assert lines[0] == "# Pre-registered group of 2: results" and "x.md (n_trials = 2)" in lines[2]
    assert lines[-2:] == ["- **good**: PASS", "- **half**: FAIL"]
    assert pe.grade_run(payload, {}, 2)["haircut_sharpe"] > pe.grade_run(payload, {})["haircut_sharpe"] > 0
    default = pe.build_report(tmp_path, {})
    assert default[0] == "# Three-pick group: results" and "2026-10-09-three-picks.md (n_trials = 3)" in default[2]
    assert default[-3:] == [f"- **{s}**: FAIL" for s in pe.SLUGS]
