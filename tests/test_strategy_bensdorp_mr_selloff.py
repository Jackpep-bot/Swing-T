"""bensdorp_mr_selloff: the 12.5% three-day drop setup, the one-session limit entry and the +4% close exit."""
from __future__ import annotations

import pandas as pd
import pytest

from swing_engine.core.models import EntryType, PositionContext
from swing_engine.features.extra import ensure_extra
from swing_engine.research.backtest import CostModel, entry_fill, run_backtest
from swing_engine.strategies.bensdorp_mr_selloff import ATR, TREND_MA, BensdorpMrSelloff
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, last_date, set_last

SYM = "MRS"
DROP = (57.0, 54.5, 52.0)  # three closes after 60.0: 13.3% off, still above sma_150


def _wide(close: float, volume: float = 2_000_000.0) -> list[float]:
    return [close, close * 1.04, close * 0.96, close, volume]  # 8% daily range: ATR% well above 5


def _panel(drop=DROP, volume: float = 2_000_000.0, after=()) -> pd.DataFrame:
    rows = [_wide(20.0 + 0.2 * i, volume) for i in range(201)] + [_wide(c, volume) for c in drop]
    return add_features(bars_from_ohlc(SYM, rows + [list(r) for r in after]))


def test_fires_as_a_limit_seven_percent_under_the_close():
    panel = _panel()
    (s,) = BensdorpMrSelloff().signals(panel, last_date(panel))
    atr = ensure_extra(panel, [ATR])[ATR].iloc[-1]
    assert s.entry_type == EntryType.LIMIT and s.entry == pytest.approx(52.0 * 0.93)
    assert s.stop == pytest.approx(52.0 * 0.93 - 2.5 * atr) and s.target is None
    assert s.score == pytest.approx(1 - 52.0 / 60.0) and s.features["max_hold_days"] == 4.0
    # next session: untouched limit = no trade; a gap under the limit fills at the open
    assert entry_fill(s, 51.0, 52.0, 49.0)[1] == "not_triggered"
    assert entry_fill(s, 51.0, 52.0, 48.0) == (pytest.approx(s.entry), None)
    assert entry_fill(s, 47.0, 48.0, 46.0) == (47.0, None)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(drop=(58.0, 56.0, 54.0)),  # 10% in three sessions
        dict(volume=900_000.0),  # 50-day average volume under 1M shares
    ],
)
def test_no_signal_cases(kwargs):
    panel = _panel(**kwargs)
    assert BensdorpMrSelloff().signals(panel, last_date(panel)) == []


def test_no_signal_below_the_150_day_or_when_calm():
    strat = BensdorpMrSelloff()
    panel = ensure_extra(_panel(), strat.extra_features)
    as_of = last_date(panel)
    assert strat.signals(set_last(panel, SYM, **{TREND_MA: 52.5}), as_of) == []
    assert strat.signals(set_last(panel, SYM, **{ATR: 2.5}), as_of) == []  # ATR% 4.8
    assert len(strat.signals(panel, as_of)) == 1


def test_target_is_a_close_four_percent_over_the_fill():
    strat = BensdorpMrSelloff()
    pos = PositionContext(entry_price=100.0)
    assert strat.should_exit(pd.Series({"close": 104.0}), 1, pos)
    assert not strat.should_exit(pd.Series({"close": 103.9}), 2, pos)
    assert not strat.should_exit(pd.Series({"close": 150.0}), 2)  # no fill price: never fires


def test_backtest_fills_the_limit_and_never_sells_on_the_fill_bar_high():
    # fill session: opens at 51 (above the +4% level of the 48.36 limit), trades down through the limit, closes at 48.5
    after = [(51.0, 51.5, 47.5, 48.5, 2e6), (48.5, 51.0, 48.0, 50.5, 2e6), (50.5, 51.0, 50.0, 50.6, 2e6)]
    panel = _panel(after=after)
    days = sorted(panel["ts"].dt.date.unique())
    res = run_backtest(BensdorpMrSelloff(), panel, days[-4], days[-1], costs=CostModel(slippage_bps=0.0))
    trade = res.trades.iloc[0]
    assert trade["entry_price"] == pytest.approx(52.0 * 0.93) and trade["entry_ts"].date() == days[-3]
    # the first close at or above fill x 1.04 (50.29) is the next session's 50.5, not the fill bar's 51.5 high
    assert trade["exit_ts"].date() == days[-2] and trade["exit_price"] == pytest.approx(50.5)
