"""bensdorp_adx_reversal: ADX(7) > 45 dip above sma_100 + ATR, the one-session limit entry and the 1.2 ATR close exit."""
from __future__ import annotations

import pandas as pd
import pytest

from swing_engine.core.models import EntryType, PositionContext
from swing_engine.features.extra import ensure_extra
from swing_engine.strategies.bensdorp_adx_reversal import (
    ADX,
    ATR,
    DOLLAR_VOL,
    RSI,
    TO_EXP,
    BensdorpAdxReversal,
)
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, last_date, set_last

SYM = "ADR"


def _panel(to_exp: float = 30.0, **last: float) -> pd.DataFrame:
    """A 150-bar uptrend with 6% daily ranges (20 -> 59.8); the indicators of the last bar are set by hand."""
    rows = [[c, c * 1.03, c * 0.97, c, 2_000_000.0] for c in (20.0 + 0.2 * i for i in range(200))]
    panel = add_features(bars_from_ohlc(SYM, rows)).assign(**{TO_EXP: to_exp})
    panel = ensure_extra(panel, BensdorpAdxReversal().extra_features)
    return set_last(panel, SYM, **{ADX: 50.0, RSI: 40.0, **last})


def test_fires_as_a_limit_four_percent_under_the_close():
    panel = _panel()
    row = panel.iloc[-1]
    (s,) = BensdorpAdxReversal().signals(panel, last_date(panel))
    assert s.entry_type == EntryType.LIMIT and s.entry == pytest.approx(row["close"] * 0.96)
    assert s.stop == pytest.approx(s.entry - 3.0 * row[ATR]) and s.target is None
    assert s.score == 50.0 and s.features[ATR] == pytest.approx(row[ATR]) and s.features["max_hold_days"] == 7.0


@pytest.mark.parametrize(
    "kwargs",
    [
        {ADX: 45.0},  # not above 45
        {RSI: 50.1},
        {ATR: 2.3},  # ATR% 3.8
        {"sma_100": 59.0},  # close under sma_100 + ATR
        {"avg_vol_50d": 499_000.0},
        {DOLLAR_VOL: 2_400_000.0},
        {"to_exp": 6.0},  # earnings expected within 6 sessions
    ],
)
def test_no_signal_cases(kwargs):
    panel = _panel(**kwargs)
    assert BensdorpAdxReversal().signals(panel, last_date(panel)) == []


def test_silent_without_the_expected_earnings_column_and_open_when_the_date_is_unknown():
    panel = _panel()
    assert BensdorpAdxReversal().signals(panel.drop(columns=TO_EXP), last_date(panel)) == []
    assert len(BensdorpAdxReversal().signals(_panel(to_exp=float("nan")), last_date(panel))) == 1


def test_target_is_a_close_one_point_two_atr_over_the_fill():
    strat = BensdorpAdxReversal()
    pos = PositionContext(entry_price=100.0, entry_features={ATR: 5.0})
    assert strat.should_exit(pd.Series({"close": 106.0}), 1, pos)
    assert not strat.should_exit(pd.Series({"close": 105.9}), 3, pos)
    assert not strat.should_exit(pd.Series({"close": 150.0}), 3, PositionContext(entry_price=100.0))  # no entry ATR
    assert not strat.should_exit(pd.Series({"close": 150.0}), 3)
