"""qullamaggie_flag: top-2% RS leader, 30%+ pole within 2 months, ADR >= 5%, 10-40 bar flag, sma_20 trail."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.features import build_panel
from swing_engine.features.patterns2 import flag
from swing_engine.strategies.qullamaggie_flag import QullamaggieFlag
from tests.fixtures.strategies.panel import bars_from_ohlc, last_date

SYM = "QF"
WICK = 0.03  # high/low ~ 1.06 -> ADR% ~ 6-7%


def _path(start: float, legs: list[tuple[int, float]]) -> list[float]:
    closes, c = [], start
    for n, target in legs:
        closes += list(np.linspace(c, target, n + 1)[1:])
        c = target
    return closes


def _rows(closes: list[float], wick: float = WICK, vol: float = 1e6) -> list[list[float]]:
    out, prev = [], closes[0]
    for c in closes:
        out.append([prev, max(prev, c) * (1 + wick), min(prev, c) * (1 - wick), c, vol])
        prev = c
    return out


def flag_rows(pole_to: float = 70.0, pole_bars: int = 30, dip_to: float = 64.0, grind: int = 12,
              wick: float = WICK, breakout: tuple[float, ...] = (69.2, 73.5, 68.9, 73.0, 3e6)) -> list[list[float]]:
    warm = [50 * (1 + 0.01 * np.sin(i / 4)) for i in range(200)]
    closes = warm + _path(50.0, [(pole_bars, pole_to), (3, dip_to), (grind, pole_to - 1.0)])
    return [*_rows(closes, wick), list(breakout)]


def _signals(rows: list[list[float]], params: dict | None = None, regime: dict | None = None):
    panel = build_panel(bars_from_ohlc(SYM, rows))
    return QullamaggieFlag(params).signals(panel, last_date(panel), regime)


def test_registered_with_doc05_defaults() -> None:
    strat = registry.get("strategy", "qullamaggie_flag")()
    p = strat.params
    assert (p["rs_rank_min"], p["prior_move_min"], p["pole_max_bars"], p["adr_min"]) == (0.98, 0.30, 42, 0.05)
    assert (p["flag_min_bars"], p["flag_max_bars"], p["max_stop_adr"], p["trail_ma"]) == (10, 40, 1.0, "sma_20")
    assert "min_reward_risk" in strat.default_params and p["max_hold_days"] == 60


def test_flag_breakout_signal() -> None:
    sigs = _signals(flag_rows())
    assert len(sigs) == 1
    s = sigs[0]
    assert s.entry == pytest.approx(73.0)
    assert s.stop == pytest.approx(max(68.9, 73.0 * (1 - s.features["adr_pct_20"])))  # day low, <= 1 ADR
    assert s.features["pivot"] == pytest.approx(70.0 * (1 + WICK))
    assert 10 <= s.features["flag_len"] <= 40 and s.features["pole_gain"] >= 0.30
    assert s.features["adr_pct_20"] >= 0.05 and s.features["rs_63d_rank"] >= 0.98
    assert s.target == pytest.approx(s.entry + 10.0 * (s.entry - s.stop))


def test_wide_day_low_is_capped_at_one_adr() -> None:
    s = _signals(flag_rows(breakout=(69.2, 73.5, 60.0, 73.0, 3e6)))[0]
    assert s.stop == pytest.approx(73.0 * (1 - s.features["adr_pct_20"]))


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(pole_to=60.0, dip_to=55.0),  # pole only ~20%
        dict(pole_bars=80),  # 40% move but spread over 80 bars (> 2 months)
        dict(wick=0.01),  # ADR ~2%
        dict(grind=3),  # flag shorter than 10 bars
        dict(grind=45),  # flag longer than 40 bars
        dict(breakout=(69.2, 71.5, 68.9, 71.0, 3e6)),  # no close above the flag high
        dict(breakout=(69.2, 73.5, 68.9, 73.0, 1.2e6)),  # rvol < 1.5
        dict(breakout=(69.2, 83.0, 68.9, 82.0, 3e6)),  # more than 1 ADR above the pivot
        dict(dip_to=50.0),  # flag deeper than 25%
    ],
)
def test_rejections(kwargs: dict) -> None:
    assert _signals(flag_rows(**kwargs)) == []


def test_relative_strength_rank_is_cross_sectional() -> None:
    leader = bars_from_ohlc(SYM, flag_rows())
    as_of = leader.ts.iloc[-1]
    others = []
    for i in range(3):  # three names that rose more over 63 bars -> QF ranks 0.25, not top 2%
        closes = [40.0] * 200 + list(np.linspace(40.0, 120.0 + i, 46))
        others.append(bars_from_ohlc(f"Z{i}", _rows(closes, wick=0.01)))
    panel = build_panel(pd.concat([leader, *others], ignore_index=True))
    assert QullamaggieFlag().signals(panel, as_of.date()) == []
    assert len(QullamaggieFlag({"rs_rank_min": 0.2}).signals(panel, as_of.date())) == 1


def test_market_gate_and_point_in_time() -> None:
    rows = flag_rows()
    assert _signals(rows, regime={"market_trend_state": 0}) == []
    short = build_panel(bars_from_ohlc(SYM, rows))
    longer = build_panel(bars_from_ohlc(SYM, rows + [[73.0, 90.0, 50.0, 60.0, 9e6]] * 8))
    as_of = last_date(short)
    a = [s.model_dump() for s in QullamaggieFlag().signals(short, as_of)]
    assert a and a == [s.model_dump() for s in QullamaggieFlag().signals(longer, as_of)]


def test_should_exit_first_close_below_sma20() -> None:
    strat = QullamaggieFlag()
    assert strat.should_exit(pd.Series({"close": 66.0, "sma_20": 67.0}), 2)
    assert not strat.should_exit(pd.Series({"close": 68.0, "sma_20": 67.0}), 2)
    assert strat.should_exit(pd.Series({"close": 68.0, "sma_20": 67.0}), 60)
    assert QullamaggieFlag({"trail_ma": "sma_10"}).should_exit(pd.Series({"close": 68.0, "sma_10": 69.0}), 2)


def test_flag_detector() -> None:
    high = np.array([5.0, 9.0, 10.0, 9.5, 9.2, 9.4, 9.6])
    low = np.array([4.0, 8.0, 9.0, 8.5, 8.6, 8.8, 9.0])
    fl = flag(high, low, end=6, max_bars=10)
    assert fl is not None and (fl.top_idx, fl.length, fl.pivot, fl.low) == (2, 5, 10.0, 8.5)
    assert fl.higher_lows and fl.depth == pytest.approx(0.15)
    falling = low.copy()
    falling[6] = 8.0
    assert not flag(high, falling, end=6, max_bars=10).higher_lows
