"""Review fix: pead_sue decided the monthly rebalance per symbol (own bar vs own previous bar), so a symbol that
missed the month's first session was ranked alone on a later mid-month day and bought whatever its SUE."""
from __future__ import annotations

from datetime import date

import pytest

from swing_engine.core import registry
from tests.fixtures.strategies.panel import make_panel


def test_symbol_missing_first_session_is_not_rebalanced_mid_month():
    s = registry.get("strategy", "pead_sue")(None)
    syms = tuple(f"S{i:02d}" for i in range(10))
    p = make_panel(syms, n_days=260, seed=3)
    p = p.assign(sue=p["symbol"].map({x: float(i) for i, x in enumerate(syms)}), days_since_earnings=5.0,
                 days_since_filing=3.0)
    p = p.assign(close=p["close"].clip(lower=10.0), high=p["high"].clip(lower=10.5))
    gap = p.loc[~((p["symbol"] == "S00") & (p["ts"].dt.date == date(2024, 10, 1)))]  # S00 halted on Oct 1
    assert len(gap) == len(p) - 1
    assert s.signals(gap, date(2024, 10, 2)) == []  # Oct 2 is not a rebalance day for anyone
    assert [x.symbol for x in s.signals(gap, date(2024, 10, 1))] == ["S09"]  # the panel's first session still is


def test_stale_sue_after_new_8k_is_not_traded():
    # fixture: the Q4 8-K reacts 2026-02-06 but the 10-K is filed Friday 02-20, so until 02-23 `sue` is still Q3's
    from swing_engine.data import fundamentals as F
    from tests.test_data_fundamentals import EPS, expected_surprise, ingested, panel_index

    feats = F.edgar_panel_features(ingested(), panel_index(date(2026, 2, 20), date(2026, 2, 23))).set_index("ts")
    stale, fresh = feats.iloc[0], feats.iloc[1]
    assert stale["sue"] == pytest.approx(expected_surprise(EPS, 11)) and stale["days_since_earnings"] == 9
    assert stale["days_since_filing"] > 30 and fresh["days_since_filing"] == 0

    s = registry.get("strategy", "pead_sue")(None)
    syms = tuple(f"S{i:02d}" for i in range(10))
    p = make_panel(syms, n_days=260, seed=3)
    p = p.assign(sue=p["symbol"].map({x: float(i) for i, x in enumerate(syms)}), days_since_earnings=5.0,
                 days_since_filing=3.0, close=p["close"].clip(lower=10.0), high=p["high"].clip(lower=10.5))
    assert [x.symbol for x in s.signals(p, date(2024, 10, 1))] == ["S09"]
    assert s.signals(p.assign(days_since_filing=60.0), date(2024, 10, 1)) == []  # last quarter's SUE
    assert s.signals(p.drop(columns=["days_since_filing"]), date(2024, 10, 1)) == []
