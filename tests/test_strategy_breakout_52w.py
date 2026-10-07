from __future__ import annotations

import pytest

from swing_engine.strategies.breakout_52w import Breakout52w
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, last_date, set_last, trend_rows

SYM = "B52"


def _panel(last=(119.6, 126.0, 119.0, 125.0, 2_000_000.0), **overrides):
    rows = trend_rows(100) + [list(last)]
    panel = add_features(bars_from_ohlc(SYM, rows))
    base = dict(atr_14=2.0, trend_state=1.0)
    base.update(overrides)
    return set_last(panel, SYM, **base)


def test_generator_flags_the_breakout_and_strategy_fires():
    panel = _panel()
    row = panel.iloc[-1]
    assert row["breakout_52w"] == 1 and row["dist_52w_high"] == pytest.approx(125.0 / 126.0 - 1)
    sigs = Breakout52w().signals(panel, last_date(panel))
    assert len(sigs) == 1
    s = sigs[0]
    assert s.entry == pytest.approx(125.0)
    assert s.stop == pytest.approx(125.0 - 2.0 * 2.0)
    assert s.target == pytest.approx(125.0 + 2.0 * 4.0)
    assert s.reward_risk == pytest.approx(2.0)
    vol_ratio = 2_000_000.0 / row["avg_vol_50d"]
    assert s.features["volume_ratio"] == pytest.approx(vol_ratio)
    assert s.score == pytest.approx(vol_ratio)  # no VCP column value -> no tightness bonus


def test_vcp_filter_and_score():
    panel = _panel(vcp_contraction=0.4)
    sigs = Breakout52w({"vcp_max_contraction": 0.5}).signals(panel, last_date(panel))
    assert len(sigs) == 1
    assert sigs[0].score == pytest.approx(sigs[0].features["volume_ratio"] + (1 - 0.4))
    assert Breakout52w({"vcp_max_contraction": 0.3}).signals(panel, last_date(panel)) == []
    strat = Breakout52w({"vcp_max_contraction": 0.5})
    assert "vcp_contraction" in strat.required_features()
    assert "vcp_contraction" not in Breakout52w().required_features()


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(last=(119.6, 126.0, 119.0, 125.0, 1_200_000.0)),  # volume gate
        dict(breakout_52w=0.0),
        dict(dist_52w_high=-0.05),  # closed too far off the high (reversal bar)
        dict(trend_state=-1.0),
        dict(atr_14=0.0),
    ],
)
def test_no_signal_cases(kwargs):
    panel = _panel(**kwargs)
    assert Breakout52w().signals(panel, last_date(panel)) == []


def test_params_change_geometry():
    panel = _panel()
    sigs = Breakout52w({"stop_atr_mult": 1.0, "target_r": 3.0}).signals(panel, last_date(panel))
    assert sigs[0].stop == pytest.approx(123.0) and sigs[0].target == pytest.approx(131.0)
    assert sigs[0].reward_risk == pytest.approx(3.0)
    assert len(Breakout52w({"max_close_below_high": 0.1}).signals(_panel(dist_52w_high=-0.05), last_date(panel))) == 1
