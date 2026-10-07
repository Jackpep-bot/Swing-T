from __future__ import annotations

import pandas as pd
import pytest

from swing_engine.strategies.rsi2_meanrev import RSI2MeanRev
from tests.fixtures.strategies.panel import add_features, bars_from_closes, last_date, set_last

SYM = "RSI"


def _panel(**overrides):
    closes = [100.0 + 0.1 * i for i in range(60)] + [99.0, 97.5, 96.0]  # three straight down closes
    panel = add_features(bars_from_closes(SYM, closes))
    base = dict(sma_200=90.0, sma_10=99.0, atr_14=2.0)
    base.update(overrides)
    return set_last(panel, SYM, **base)


def test_oversold_above_200sma_signal():
    panel = _panel()
    assert panel.iloc[-1]["rsi_2"] < 10
    sigs = RSI2MeanRev().signals(panel, last_date(panel))
    assert len(sigs) == 1
    s = sigs[0]
    assert s.entry == pytest.approx(96.0)
    assert s.stop == pytest.approx(96.0 - 2.0 * 2.0)
    assert s.target == pytest.approx(99.0)  # exit MA is the reference target
    assert s.reward_risk == pytest.approx(3.0 / 4.0)
    assert s.score == pytest.approx(10.0 - panel.iloc[-1]["rsi_2"])
    assert s.features["max_hold_days"] == 5.0 and s.features["rsi_exit"] == 70.0


def test_target_is_open_ended_when_exit_ma_below_entry():
    panel = _panel(sma_10=95.0)
    sigs = RSI2MeanRev().signals(panel, last_date(panel))
    assert len(sigs) == 1 and sigs[0].target is None and sigs[0].reward_risk is None


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(sma_200=97.0),  # below the long-term trend filter
        dict(rsi_2=15.0),  # not oversold enough
        dict(atr_14=float("nan")),
    ],
)
def test_no_signal_cases(kwargs):
    panel = _panel(**kwargs)
    assert RSI2MeanRev().signals(panel, last_date(panel)) == []


def test_stricter_entry_param():
    panel = _panel(rsi_2=7.0)
    assert len(RSI2MeanRev().signals(panel, last_date(panel))) == 1
    assert RSI2MeanRev({"rsi_entry": 5.0}).signals(panel, last_date(panel)) == []


def test_required_features_follow_params():
    strat = RSI2MeanRev({"trend_ma": "sma_50", "exit_ma": "sma_20"})
    assert {"sma_50", "sma_20", "rsi_2", "atr_14"} <= set(strat.required_features())
    assert "sma_200" not in strat.required_features()


def test_should_exit_rules():
    strat = RSI2MeanRev()
    hold = pd.Series({"close": 98.0, "sma_10": 99.0, "rsi_2": 40.0})
    assert not strat.should_exit(hold, bars_held=1)
    assert strat.should_exit(pd.Series({"close": 100.0, "sma_10": 99.0, "rsi_2": 40.0}), bars_held=1)
    assert strat.should_exit(pd.Series({"close": 98.0, "sma_10": 99.0, "rsi_2": 75.0}), bars_held=1)
    assert strat.should_exit(hold, bars_held=5)
    assert not RSI2MeanRev({"max_hold_days": 10}).should_exit(hold, bars_held=5)
