"""episodic_pivot: day-2 entry above the day-1 high after a 10%+ gap on 3x rvol in a neglected stock."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.features import build_panel
from swing_engine.strategies.episodic_pivot import EpisodicPivot
from tests.fixtures.strategies.panel import bars_from_ohlc, last_date

SYM = "EP"


def _base(drift: float = 0.0, n: int = 260, wick: float = 0.025) -> tuple[list[list[float]], float]:
    rng = np.random.default_rng(9)
    c, rows = 30.0, []
    for _ in range(n):
        o, c = c, c * (1 + rng.normal(drift, 0.012))
        rows.append([o, max(o, c) * (1 + wick), min(o, c) * (1 - wick), c, 1e6])
    return rows, c


def ep_rows(gap: float = 1.15, day1_vol: float = 5e6, day1_close: float = 1.19, day1_low: float = 1.14,
            day2_close: float = 1.225, drift: float = 0.0, wick: float = 0.025,
            earlier_ep_at: int | None = None) -> tuple[list[list[float]], float]:
    rows, pc = _base(drift, wick=wick)
    if earlier_ep_at is not None:
        o = rows[earlier_ep_at - 1][3]
        rows[earlier_ep_at] = [o * 1.12, o * 1.14, o * 1.11, o * 1.13, 6e6]
    rows.append([pc * gap, pc * 1.21, pc * day1_low, pc * day1_close, day1_vol])  # day 1: the EP
    rows.append([pc * 1.19, pc * max(day2_close, 1.19) + 0.01, pc * 1.18, pc * day2_close, 3e6])  # day 2
    return rows, pc


def _signals(rows: list[list[float]], params: dict | None = None, regime: dict | None = None):
    panel = build_panel(bars_from_ohlc(SYM, rows))
    return EpisodicPivot(params).signals(panel, last_date(panel), regime)


def test_registered_with_doc02_defaults() -> None:
    strat = registry.get("strategy", "episodic_pivot")()
    p = strat.params
    assert (p["min_gap_pct"], p["min_rvol"], p["neglect_max_ret"], p["repeat_lookback"]) == (0.10, 3.0, 0.30, 252)
    assert (p["max_stop_adr"], p["trail_ma"], p["trail_after_bars"], p["max_hold_days"]) == (1.5, "sma_10", 3, 60)
    assert "min_reward_risk" in strat.default_params


def test_day2_signal() -> None:
    rows, pc = ep_rows()
    sigs = _signals(rows)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.entry == pytest.approx(pc * 1.225)
    assert s.stop == pytest.approx(pc * 1.14)  # day-1 low
    assert s.features["ep_high"] == pytest.approx(pc * 1.21) and s.entry > s.features["ep_high"]
    assert s.features["ep_gap_pct"] == pytest.approx(0.15) and s.features["ep_rvol"] >= 3.0
    assert s.features["catalyst_verified"] == 0.0 and "catalyst not verified" in s.notes
    assert s.features["stop_adr"] <= 1.5 and s.features["prior_ret_126d"] <= 0.30


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(gap=1.08),  # gap < 10%
        dict(day1_vol=2e6),  # rvol < 3
        dict(day1_close=1.15),  # faded: close in the lower half of the day-1 range
        dict(day2_close=1.20),  # day 2 does not close above the day-1 high
        dict(day1_low=1.05),  # stop more than 1.5 ADR below the entry
        dict(drift=0.004),  # not neglected: prior 126-bar return > 30%
        dict(earlier_ep_at=150),  # another EP within 252 bars
    ],
)
def test_rejections(kwargs: dict) -> None:
    rows, _ = ep_rows(**kwargs)
    assert _signals(rows) == []


def test_params_relax_the_rejections() -> None:
    rows, _ = ep_rows(gap=1.08)
    assert len(_signals(rows, {"min_gap_pct": 0.07})) == 1
    rows, _ = ep_rows(earlier_ep_at=150)
    assert len(_signals(rows, {"repeat_lookback": 50})) == 1
    rows, _ = ep_rows(day1_low=1.05)
    assert len(_signals(rows, {"max_stop_adr": 5.0})) == 1
    rows, _ = ep_rows(drift=0.004)
    assert len(_signals(rows, {"neglect_max_ret": 10.0})) == 1


def test_only_day_two_triggers_and_point_in_time() -> None:
    rows, pc = ep_rows()
    day3 = [pc * 1.23, pc * 1.30, pc * 1.22, pc * 1.29, 2e6]
    later = build_panel(bars_from_ohlc(SYM, [*rows, day3]))
    assert EpisodicPivot().signals(later, last_date(later)) == []  # day 3 is not a day-2 entry
    as_of = last_date(build_panel(bars_from_ohlc(SYM, rows)))
    a = [s.model_dump() for s in _signals(rows)]
    assert a and a == [s.model_dump() for s in EpisodicPivot().signals(later, as_of)]


def test_should_exit_trails_after_three_bars() -> None:
    strat = EpisodicPivot()
    below = pd.Series({"close": 9.0, "sma_10": 10.0, "sma_20": 8.0})
    assert not strat.should_exit(below, 2)  # the trail starts after 3 bars
    assert strat.should_exit(below, 3)
    assert not EpisodicPivot({"trail_ma": "sma_20"}).should_exit(below, 3)
    assert strat.should_exit(pd.Series({"close": 11.0, "sma_10": 10.0}), 60)
