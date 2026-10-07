"""power_gap: volume gap (>= 10% or 0.75x ATR40 on 2x volume) then a 2-30 bar hold, bought on the break."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.features import build_panel
from swing_engine.features.patterns2 import gap_consolidation
from swing_engine.strategies.power_gap import PowerGap
from tests.fixtures.strategies.panel import bars_from_ohlc, last_date

SYM = "GAP"


def _base() -> tuple[list[list[float]], float]:
    rng = np.random.default_rng(3)
    c, rows = 40.0, []
    for _ in range(220):
        o, c = c, c * (1 + rng.normal(0.0008, 0.01))
        rows.append([o, max(o, c) * 1.005, min(o, c) * 0.995, c, 1e6])
    return rows, c


def gap_rows(gap: float = 1.12, gap_vol: float = 3.5e6, consol: int = 4, consol_low: float = 1.165,
             breakout_close: float = 1.225, breakout_vol: float = 3e6) -> tuple[list[list[float]], float]:
    rows, pc = _base()
    rows.append([pc * gap, pc * 1.20, pc * 1.11, pc * 1.19, gap_vol])  # gap day, strong close
    rows += [[pc * 1.185, pc * 1.195, pc * consol_low, pc * 1.18, 8e5] for _ in range(consol)]
    rows.append([pc * 1.18, pc * (breakout_close + 0.005), pc * 1.175, pc * breakout_close, breakout_vol])
    return rows, pc


def _signals(rows: list[list[float]], params: dict | None = None):
    panel = build_panel(bars_from_ohlc(SYM, rows))
    return PowerGap(params).signals(panel, last_date(panel))


def test_registered_with_doc13_defaults() -> None:
    strat = registry.get("strategy", "power_gap")()
    p = strat.params
    assert (p["min_gap_pct"], p["min_gap_atr40"], p["min_volume_ratio"]) == (0.10, 0.75, 2.0)
    assert (p["consol_min_bars"], p["consol_max_bars"], p["max_stop_adr"], p["trail_ma"]) == (2, 30, 1.5, "sma_20")
    assert "min_reward_risk" in strat.default_params and p["max_hold_days"] == 60


def test_consolidation_break_signal_is_labelled_volume_gap() -> None:
    rows, pc = gap_rows()
    sigs = _signals(rows)
    assert len(sigs) == 1
    s = sigs[0]
    assert s.entry == pytest.approx(pc * 1.225)
    assert s.features["earnings_verified"] == 0.0 and "earnings date not verified" in s.notes
    assert s.features["gap_age"] == 5 and s.features["consol_len"] == 4
    assert s.features["gap_low"] == pytest.approx(pc * 1.11)
    assert s.features["pivot"] == pytest.approx(pc * 1.195)
    adr = s.features["adr_pct_20"]
    assert s.stop == pytest.approx(max(pc * 1.11, s.entry * (1 - 1.5 * adr)))  # gap low capped at 1.5 ADR
    assert s.target == pytest.approx(s.entry + 10.0 * (s.entry - s.stop)) and s.reward_risk == pytest.approx(10.0)


def test_uncapped_stop_is_the_gap_day_low() -> None:
    rows, pc = gap_rows()
    s = _signals(rows, {"max_stop_adr": 50.0})[0]
    assert s.stop == pytest.approx(pc * 1.11)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(gap=1.0),  # no opening gap: a +19% day is not a gap (neither 10% nor 0.75 ATR40)
        dict(gap_vol=1.5e6),  # gap volume < 2x prior 50-day average
        dict(consol=1),  # consolidation shorter than 2 bars
        dict(consol=31),  # longer than 30 bars
        dict(consol_low=1.10),  # consolidation undercuts the gap-day low
        dict(breakout_close=1.19),  # no close above the consolidation high
        dict(breakout_vol=1.0e6),  # breakout rvol < 1.5
    ],
)
def test_rejections(kwargs: dict) -> None:
    rows, _ = gap_rows(**kwargs)
    assert _signals(rows) == []


def test_atr40_gap_qualifies_without_ten_percent() -> None:
    rows, pc = gap_rows(gap=1.06)  # 6% gap, but many ATR(40)s on a 1%-vol stock
    sigs = _signals(rows)
    assert len(sigs) == 1 and sigs[0].features["gap_pct"] < 0.10 and sigs[0].features["gap_atr40"] >= 0.75
    assert _signals(rows, {"min_gap_atr40": 99.0}) == []


def test_one_entry_per_gap_and_point_in_time() -> None:
    rows, pc = gap_rows()
    follow = [pc * 1.225, pc * 1.25, pc * 1.22, pc * 1.245, 3e6]
    later = build_panel(bars_from_ohlc(SYM, [*rows, follow]))
    assert PowerGap().signals(later, last_date(later)) == []  # the earlier close already broke out
    as_of = last_date(build_panel(bars_from_ohlc(SYM, rows)))
    a = [s.model_dump() for s in _signals(rows)]
    assert a == [s.model_dump() for s in PowerGap().signals(later, as_of)]


def test_should_exit_trails_sma20() -> None:
    strat = PowerGap()
    assert strat.should_exit(pd.Series({"close": 9.0, "sma_20": 10.0}), 1)
    assert not strat.should_exit(pd.Series({"close": 11.0, "sma_20": 10.0}), 1)
    assert strat.should_exit(pd.Series({"close": 11.0, "sma_20": 10.0}), 60)


def test_gap_consolidation_detector() -> None:
    high = np.array([10.0, 12.0, 11.8, 11.9, 11.7])
    low = np.array([9.5, 11.0, 11.2, 11.3, 11.1])
    gap = np.array([False, True, False, False, False])
    gc = gap_consolidation(gap, high, low, end=4, min_bars=2, max_bars=30)
    assert gc is not None and (gc.gap_idx, gc.length, gc.gap_low, gc.pivot) == (1, 3, 11.0, 11.9)
    assert gap_consolidation(gap, high, low, end=4, min_bars=4, max_bars=30) is None
    low_break = low.copy()
    low_break[3] = 10.9
    assert gap_consolidation(gap, high, low_break, end=4, min_bars=2, max_bars=30) is None
