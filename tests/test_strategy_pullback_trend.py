from __future__ import annotations

import pytest

from swing_engine.strategies.pullback_trend import PullbackTrend
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, last_date, set_last, trend_rows

SYM = "PBK"
PULLBACK = [  # (open, high, low, close) for the four pullback bars after a 100-bar uptrend ending at 119.6
    (119.6, 119.4, 118.7, 119.0),
    (119.0, 119.1, 118.5, 118.8),
    (118.8, 119.0, 118.4, 118.7),
    (118.7, 119.0, 118.6, 118.9),
]


def _panel(pullback_volume=600_000.0, last=(118.9, 119.6, 118.8, 119.5, 1_100_000.0), **overrides):
    rows = trend_rows(100)
    rows += [[o, h, lo, c, pullback_volume] for o, h, lo, c in PULLBACK]
    rows.append(list(last))
    panel = add_features(bars_from_ohlc(SYM, rows))
    base = dict(ema_21=118.5, atr_14=1.0, avg_vol_20d=1_000_000.0, trend_state=1.0, ret_63d=0.3)
    base.update(overrides)
    return set_last(panel, SYM, **base)


def test_pullback_entry_above_prior_high():
    panel = _panel()
    sigs = PullbackTrend().signals(panel, last_date(panel))
    assert len(sigs) == 1
    s = sigs[0]
    assert s.entry == pytest.approx(119.5)
    assert s.stop == pytest.approx(118.4 - 0.1 * 1.0)  # below the pullback low
    risk = 119.5 - 118.3
    assert s.target == pytest.approx(119.5 + 2.0 * risk)
    assert s.reward_risk == pytest.approx(2.0)
    assert s.features["prior_high"] == pytest.approx(119.0)
    assert s.features["pullback_volume_ratio"] == pytest.approx(0.6)
    assert s.score == pytest.approx(2.0 + 0.3)
    assert "r_multiple" in s.notes


def test_swing_high_target_mode():
    panel = _panel()
    strat = PullbackTrend({"target_mode": "swing_high", "min_reward_risk": 0.0})
    sigs = strat.signals(panel, last_date(panel))
    assert len(sigs) == 1
    assert sigs[0].target == pytest.approx(119.9)  # high of the last trend bar (119.6 + 0.3)
    assert sigs[0].reward_risk == pytest.approx((119.9 - 119.5) / (119.5 - 118.3))
    assert "swing_high" in sigs[0].notes


def test_swing_high_falls_back_to_r_multiple_when_not_above_entry():
    panel = _panel(last=(118.9, 120.5, 118.8, 120.4, 1_100_000.0))
    sigs = PullbackTrend({"target_mode": "swing_high"}).signals(panel, last_date(panel))
    assert len(sigs) == 1 and "r_multiple" in sigs[0].notes


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(trend_state=0.0),  # needs a confirmed uptrend
        dict(pullback_volume=1_200_000.0),  # volume did not dry up
        dict(last=(118.9, 119.2, 118.8, 118.9, 1_100_000.0)),  # close not above prior high
        dict(ema_21=117.0),  # pullback never reached the MA
        dict(last=(118.9, 119.6, 118.8, 119.5, 1_100_000.0), ema_21=119.8),  # close below the MA
    ],
)
def test_no_signal_cases(kwargs):
    panel = _panel(**kwargs)
    assert PullbackTrend().signals(panel, last_date(panel)) == []


def test_alternate_ma_column_is_required_and_used():
    strat = PullbackTrend({"pullback_ma": "sma_20"})
    assert "sma_20" in strat.required_features() and "ema_21" not in strat.required_features()
    panel = _panel(sma_20=118.5, ema_21=50.0)
    assert len(strat.signals(panel, last_date(panel))) == 1


def test_unknown_target_mode_raises():
    panel = _panel()
    with pytest.raises(ValueError, match="target_mode"):
        PullbackTrend({"target_mode": "moon"}).signals(panel, last_date(panel))
