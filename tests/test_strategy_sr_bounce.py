from __future__ import annotations

import pytest

from swing_engine.strategies.sr_bounce import SRBounce
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, last_date, range_closes, set_last

SYM = "BNC"


def _panel(last=(102.0, 103.5, 100.3, 103.2, 1_000_000.0), **overrides):
    rows = [[c, c * 1.005, c * 0.995, c, 1_000_000.0] for c in range_closes()]
    rows.append(list(last))
    panel = add_features(bars_from_ohlc(SYM, rows))
    base = dict(support_1=100.0, resistance_1=110.0, range_width=10.0, atr_14=2.0, trend_state=0.0)
    base.update(overrides)
    return set_last(panel, SYM, **base)


def test_bounce_off_support_signal():
    panel = _panel()
    sigs = SRBounce().signals(panel, last_date(panel))
    assert len(sigs) == 1
    s = sigs[0]
    assert s.symbol == SYM and s.strategy == "sr_bounce"
    assert s.entry == pytest.approx(103.2)
    assert s.stop == pytest.approx(100.0 - 1.0 * 2.0)
    assert s.target == pytest.approx(110.0)
    rr = (110.0 - 103.2) / (103.2 - 98.0)
    assert s.reward_risk == pytest.approx(rr)
    assert s.score == pytest.approx(rr + (103.2 - 100.3) / 2.0)
    assert s.features["support_1"] == 100.0 and s.features["touch_dist"] == pytest.approx(0.3 / 103.2)


def test_shakeout_below_support_still_counts_as_touch():
    panel = _panel(last=(101.0, 103.5, 99.5, 103.0, 1_000_000.0))  # low pierced 100 by 0.5%
    assert len(SRBounce().signals(panel, last_date(panel))) == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(last=(102.0, 103.5, 100.3, 99.6, 1_000_000.0)),  # closed back below support
        dict(last=(102.0, 106.0, 104.0, 105.0, 1_000_000.0)),  # never touched the level
        dict(trend_state=-1.0),  # downtrend filter
        dict(resistance_1=103.0),  # no room to the opposite level
        dict(atr_14=float("nan")),  # warm-up
    ],
)
def test_no_signal_cases(kwargs):
    panel = _panel(**kwargs)
    assert SRBounce().signals(panel, last_date(panel)) == []


def test_params_change_geometry():
    panel = _panel(last=(102.0, 106.0, 104.0, 105.0, 1_000_000.0))
    loose = SRBounce({"touch_pct": 0.05, "stop_atr_mult": 2.0, "min_reward_risk": 0.0})
    sigs = loose.signals(panel, last_date(panel))
    assert len(sigs) == 1
    assert sigs[0].stop == pytest.approx(100.0 - 2.0 * 2.0)
    assert sigs[0].reward_risk == pytest.approx(5.0 / 9.0)
    assert SRBounce({"touch_pct": 0.05, "stop_atr_mult": 2.0}).signals(panel, last_date(panel)) == []  # rr floor
    strict_rr = SRBounce({"min_reward_risk": 5.0})
    assert strict_rr.signals(_panel(), last_date(panel)) == []


def test_market_regime_blocks_longs():
    panel = _panel()
    assert SRBounce().signals(panel, last_date(panel), regime={"market_trend_state": -1}) == []
    assert len(SRBounce().signals(panel, last_date(panel), regime={"market_trend_state": 1})) == 1
