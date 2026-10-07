from __future__ import annotations

import pytest

from swing_engine.strategies.sr_breakout import SRBreakout
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, last_date, range_closes, set_last

SYM = "BRK"


def _panel(last=(108.5, 111.5, 108.0, 111.0, 2_000_000.0), **overrides):
    rows = [[c, c * 1.005, c * 0.995, c, 1_000_000.0] for c in range_closes()]
    rows.append(list(last))
    panel = add_features(bars_from_ohlc(SYM, rows))
    base = dict(support_1=100.0, resistance_1=110.0, range_width=10.0, atr_14=2.0, avg_vol_50d=1_000_000.0,
                trend_state=0.0)
    base.update(overrides)
    return set_last(panel, SYM, **base)


def test_breakout_measured_move_signal():
    panel = _panel()
    sigs = SRBreakout().signals(panel, last_date(panel))
    assert len(sigs) == 1
    s = sigs[0]
    assert s.entry == pytest.approx(111.0)
    assert s.target == pytest.approx(110.0 + 10.0)  # level + prior range
    assert s.stop == pytest.approx(110.0 - 0.5 * 2.0)  # just below the level
    assert s.reward_risk == pytest.approx(9.0 / 2.0)
    assert s.features["volume_ratio"] == pytest.approx(2.0)
    assert s.score == pytest.approx(2.0 + 4.5)


def test_atr_stop_mode():
    panel = _panel()
    sigs = SRBreakout({"stop_mode": "atr"}).signals(panel, last_date(panel))
    assert len(sigs) == 1
    assert sigs[0].stop == pytest.approx(111.0 - 2.0 * 2.0)
    assert sigs[0].reward_risk == pytest.approx(9.0 / 4.0)


def test_unknown_stop_mode_raises():
    panel = _panel()
    with pytest.raises(ValueError, match="stop_mode"):
        SRBreakout({"stop_mode": "bogus"}).signals(panel, last_date(panel))


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(last=(108.5, 111.5, 108.0, 111.0, 1_200_000.0)),  # volume below 1.5x
        dict(last=(108.5, 110.5, 108.0, 109.5, 2_000_000.0)),  # did not close through the level
        dict(trend_state=-1.0),
        dict(range_width=0.0),
        dict(resistance_1=float("nan")),
    ],
)
def test_no_signal_cases(kwargs):
    panel = _panel(**kwargs)
    assert SRBreakout().signals(panel, last_date(panel)) == []


def test_only_first_close_through_level():
    """If the prior close was already above the level it is not a fresh breakout."""
    rows = [[c, c * 1.005, c * 0.995, c, 1_000_000.0] for c in range_closes()]
    rows.append([110.5, 112.0, 110.2, 111.5, 1_000_000.0])
    rows.append([111.5, 113.0, 111.0, 112.5, 2_000_000.0])
    panel = set_last(add_features(bars_from_ohlc(SYM, rows)), SYM, support_1=100.0, resistance_1=110.0,
                     range_width=10.0, atr_14=2.0, avg_vol_50d=1_000_000.0, trend_state=0.0)
    assert SRBreakout().signals(panel, last_date(panel)) == []


def test_volume_mult_param():
    panel = _panel(last=(108.5, 111.5, 108.0, 111.0, 1_200_000.0))
    assert len(SRBreakout({"volume_mult": 1.1}).signals(panel, last_date(panel))) == 1
