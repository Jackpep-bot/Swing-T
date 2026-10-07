from __future__ import annotations

import pandas as pd
import pytest

from swing_engine.strategies.momentum_burst import MomentumBurst
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, last_date, set_last

SYM = "BST"
FLAT = [100.0, 100.5, 99.5, 100.0, 1_000_000.0]


def _panel(prior=(100.0, 101.3, 99.8, 101.0, 1_000_000.0), last=(101.2, 105.5, 100.8, 105.1, 2_000_000.0),
           lead_in=(), **overrides):
    rows = [list(FLAT) for _ in range(60)] + [list(r) for r in lead_in] + [list(prior), list(last)]
    panel = add_features(bars_from_ohlc(SYM, rows))
    base = dict(atr_14=1.5, trend_state=0.0)
    base.update(overrides)
    return set_last(panel, SYM, **base)


def test_burst_signal_from_quiet_prior_day():
    panel = _panel()
    row = panel.iloc[-1]
    assert row["burst_4pct"] == 1 and row["up_days_3"] == 2
    sigs = MomentumBurst().signals(panel, last_date(panel))
    assert len(sigs) == 1
    s = sigs[0]
    assert s.entry == pytest.approx(105.1)
    assert s.stop == pytest.approx(100.8)  # entry bar low, no buffer by default
    assert s.target == pytest.approx(105.1 + 2.0 * (105.1 - 100.8))
    assert s.reward_risk == pytest.approx(2.0)
    assert s.features["prior_ret_1d"] == pytest.approx(0.01)
    assert s.features["max_hold_days"] == 5.0
    assert s.score == pytest.approx((2_000_000.0 / row["avg_vol_20d"]) * (105.1 / 101.0))


def test_no_signal_when_prior_move_too_big():
    panel = _panel(prior=(100.0, 103.8, 99.8, 103.5, 1_000_000.0), last=(103.6, 108.0, 103.3, 107.7, 2_000_000.0))
    assert panel.iloc[-1]["burst_4pct"] == 1
    assert MomentumBurst().signals(panel, last_date(panel)) == []
    assert len(MomentumBurst({"max_prev_move": 0.04}).signals(panel, last_date(panel))) == 1


def test_no_signal_when_up_three_days():
    lead = [(100.0, 100.8, 99.8, 100.5, 1_000_000.0)]
    panel = _panel(lead_in=lead, prior=(100.5, 101.3, 100.3, 101.0, 1_000_000.0))
    assert panel.iloc[-1]["up_days_3"] == 3
    assert MomentumBurst().signals(panel, last_date(panel)) == []
    assert len(MomentumBurst({"max_up_days": 3}).signals(panel, last_date(panel))) == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(last=(101.2, 105.5, 100.8, 105.1, 90_000.0)),  # below the 100k volume floor
        dict(last=(101.2, 104.5, 100.8, 104.0, 2_000_000.0)),  # under 4%
        dict(last=(101.2, 105.5, 100.8, 105.1, 900_000.0)),  # volume not above prior day
        dict(trend_state=-1.0, min_trend_state=0),
    ],
)
def test_no_signal_cases(kwargs):
    params = {"min_trend_state": kwargs.pop("min_trend_state")} if "min_trend_state" in kwargs else None
    panel = _panel(**kwargs)
    assert MomentumBurst(params).signals(panel, last_date(panel)) == []


def test_stop_buffer_param():
    panel = _panel()
    sigs = MomentumBurst({"stop_atr_buffer": 0.5}).signals(panel, last_date(panel))
    assert sigs[0].stop == pytest.approx(100.8 - 0.5 * 1.5)


def test_should_exit_is_time_based():
    strat = MomentumBurst()
    row = pd.Series({"close": 110.0})
    assert not strat.should_exit(row, bars_held=2)
    assert strat.should_exit(row, bars_held=5)
    assert MomentumBurst({"max_hold_days": 3}).should_exit(row, bars_held=3)
