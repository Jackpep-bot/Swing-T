"""base_breakout: cup-with-handle and flat-base pivot breakouts (doc 04 rules) and their geometry detectors."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.features import build_panel
from swing_engine.features.patterns2 import cup_with_handle, flat_base, prior_advance
from swing_engine.strategies.base_breakout import BaseBreakout
from tests.fixtures.strategies.panel import bars_from_ohlc, last_date

WARMUP = 200  # trend_state needs sma_200
WICK = 0.004


def _path(start: float, legs: list[tuple[int, float]]) -> list[float]:
    """Piecewise-linear closes: each leg is (bars, end price)."""
    closes: list[float] = []
    c = start
    for n, target in legs:
        closes += list(np.linspace(c, target, n + 1)[1:])
        c = target
    return closes


def _rows(closes: list[float], vols: list[float]) -> list[list[float]]:
    out, prev = [], closes[0]
    for c, v in zip(closes, vols, strict=True):
        out.append([prev, max(prev, c) * (1 + WICK), min(prev, c) * (1 - WICK), c, v])
        prev = c
    return out


def _warmup() -> list[float]:
    return [50 * (1 + 0.003 * np.sin(i / 3)) for i in range(WARMUP)]


def cup_rows(advance_to: float = 70.0, cup_low: float = 56.0, handle_to: float = 66.5,
             breakout: tuple[float, float, float, float, float] = (66.6, 70.0, 66.4, 69.9, 2.5e6)) -> list[list[float]]:
    closes = _warmup() + _path(50.0, [(40, advance_to), (20, cup_low), (20, advance_to - 1.0), (7, handle_to)])
    vols = [1e6] * len(closes)
    vols[-7:] = [6e5] * 7  # light handle volume
    return [*_rows(closes, vols), list(breakout)]


def flat_rows(breakout: tuple[float, float, float, float, float] = (68.5, 71.2, 68.3, 71.0, 2.5e6)) -> list[list[float]]:
    base = [67.0 + 2.5 * np.sin(i / 2.0) for i in range(30)]  # 64.5-69.5 band, ~10% deep
    closes = _warmup() + _path(50.0, [(40, 68.0)]) + base
    return [*_rows(closes, [1e6] * len(closes)), list(breakout)]


def _signals(rows: list[list[float]], params: dict | None = None):
    panel = build_panel(bars_from_ohlc("BAS", rows))
    return BaseBreakout(params).signals(panel, last_date(panel))


def test_registered_with_doc04_defaults() -> None:
    strat = registry.get("strategy", "base_breakout")()
    p = strat.params
    assert (p["prior_advance_min"], p["cup_min_bars"], p["cup_depth_min"], p["cup_depth_max"]) == (0.30, 35, 0.12, 0.33)
    assert (p["flat_depth_max"], p["breakout_vol_mult"], p["max_extension"]) == (0.15, 1.4, 0.05)
    assert (p["stop_pct"], p["target_pct"], p["max_hold_days"]) == (0.07, 0.20, 40)
    assert "min_reward_risk" in strat.default_params


def test_cup_with_handle_breakout() -> None:
    sigs = _signals(cup_rows())
    assert len(sigs) == 1
    s = sigs[0]
    assert s.features["is_cup_handle"] == 1.0 and s.features["base_len"] >= 35
    assert 0.12 <= s.features["base_depth"] <= 0.33
    assert s.entry == pytest.approx(69.9)
    assert s.stop == pytest.approx(max(s.features["base_low"], 69.9 * 0.93))  # higher of handle low and -7%
    assert s.stop == pytest.approx(s.features["base_low"])  # the handle low is the tighter one here
    assert s.target == pytest.approx(69.9 * 1.20)
    assert 0 < s.features["extension"] <= 0.05 and s.features["volume_ratio"] >= 1.4


def test_flat_base_breakout_uses_pct_stop() -> None:
    sigs = _signals(flat_rows())
    assert len(sigs) == 1
    s = sigs[0]
    assert s.features["is_cup_handle"] == 0.0 and s.features["base_len"] >= 25
    assert s.features["base_depth"] <= 0.15
    assert s.stop == pytest.approx(71.0 * 0.93)  # base low is deeper than 7%
    assert s.reward_risk == pytest.approx(0.20 / 0.07)


@pytest.mark.parametrize(
    "rows",
    [
        cup_rows(breakout=(66.6, 74.0, 66.4, 73.9, 2.5e6)),  # > 5% above the pivot
        cup_rows(breakout=(66.6, 70.0, 66.4, 69.9, 1.2e6)),  # volume < 1.4x
        cup_rows(breakout=(66.6, 69.0, 66.4, 68.8, 2.5e6)),  # no close over the pivot
        cup_rows(advance_to=60.0, cup_low=48.0, handle_to=57.0,
                 breakout=(57.1, 60.0, 57.0, 59.9, 2.5e6)),  # prior advance only 20%
        cup_rows(handle_to=61.5, breakout=(61.6, 70.0, 61.4, 69.9, 2.5e6)),  # handle in the lower half
    ],
)
def test_rejections(rows: list[list[float]]) -> None:
    assert _signals(rows) == []


def test_prior_advance_and_rs_params() -> None:
    rows = cup_rows(advance_to=60.0, cup_low=48.0, handle_to=57.0, breakout=(57.1, 60.0, 57.0, 59.9, 2.5e6))
    assert len(_signals(rows, {"prior_advance_min": 0.15})) == 1
    assert _signals(cup_rows(), {"rs_rank_min": 1.01}) == []
    low_handle = cup_rows(handle_to=61.5, breakout=(61.6, 70.0, 61.4, 69.9, 2.5e6))
    assert len(_signals(low_handle, {"handle_upper_half": False})) == 1


def test_market_gate_defaults_to_uptrend() -> None:
    panel = build_panel(bars_from_ohlc("BAS", cup_rows()))
    as_of = last_date(panel)
    assert BaseBreakout().signals(panel, as_of, {"market_trend_state": 0}) == []
    assert len(BaseBreakout().signals(panel, as_of, {"market_trend_state": 1})) == 1


def test_point_in_time() -> None:
    rows = cup_rows()
    short = build_panel(bars_from_ohlc("BAS", rows))
    future = [[70.0, 80.0, 60.0, 75.0, 9e6]] * 10
    longer = build_panel(bars_from_ohlc("BAS", rows + future))
    as_of = last_date(short)
    a = [s.model_dump() for s in BaseBreakout().signals(short, as_of)]
    assert a and a == [s.model_dump() for s in BaseBreakout().signals(longer, as_of)]


def test_should_exit_time_and_heavy_volume_50d_break() -> None:
    strat = BaseBreakout()
    quiet = pd.Series({"close": 90.0, "sma_50": 95.0, "volume": 1e6, "avg_vol_50d": 1e6})
    heavy = quiet.copy()
    heavy["volume"] = 1.5e6
    assert not strat.should_exit(quiet, 5)
    assert strat.should_exit(heavy, 5)
    assert strat.should_exit(quiet, 40)


# --------------------------------------------------------------------------- detectors
def test_flat_base_detector() -> None:
    high = np.array([100.0, 50, 52, 51, 52, 51.5])
    low = np.array([90.0, 48, 49, 48.5, 49, 49.5])
    base = flat_base(high, low, end=5, max_depth=0.10, max_bars=10)
    assert base is not None and (base.start, base.length) == (1, 5)
    assert base.top == 52 and base.low == 48 and base.depth == pytest.approx(4 / 52)
    assert flat_base(high, low, end=5, max_depth=0.10, max_bars=3).length == 3
    assert flat_base(high, low, end=-1, max_depth=0.1, max_bars=3) is None


def test_cup_with_handle_detector_and_prior_advance() -> None:
    closes = _path(50.0, [(40, 70.0), (20, 56.0), (20, 69.0), (7, 66.5)])
    high = np.array(closes) * 1.004
    low = np.array(closes) * 0.996
    cup = cup_with_handle(high, low, len(closes) - 1, cup_min_bars=35, cup_max_bars=325,
                          handle_min_bars=5, handle_max_bars=25)
    assert cup is not None
    assert cup.left == 39 and cup.right == 79 and cup.cup_len == 40 and cup.handle_len == 8
    assert cup.depth == pytest.approx((70 * 1.004 - 56 * 0.996) / (70 * 1.004))
    assert cup.handle_low == pytest.approx(66.5 * 0.996)
    assert prior_advance(low, cup.lip, cup.left, 126) == pytest.approx(70 * 1.004 / (low[:39].min()) - 1)
    assert cup_with_handle(high, low, len(closes) - 1, cup_min_bars=45, cup_max_bars=325,
                           handle_min_bars=5, handle_max_bars=25) is None
