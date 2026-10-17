"""sykes_first_green_day: runner, three-day selloff, first green day; next-open entry held one session."""
from __future__ import annotations

import pandas as pd
import pytest

from swing_engine.core.models import EntryType
from swing_engine.research.backtest import CostModel, run_backtest
from swing_engine.strategies.sykes_first_green_day import SykesFirstGreenDay
from tests.fixtures.strategies.panel import add_features, bars_from_closes, bars_from_ohlc, last_date

SYM = "FGD"
RUN = (5.5, 6.2, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0)  # a double off the $5 base, peak close 12.0
SELLOFF = (10.5, 9.5, 8.8, 8.0)  # four down closes, 33% off the peak
GREEN = (8.0, 9.3, 7.9, 9.2, 3_000_000.0)  # close near the high on 3x volume


def _panel(selloff=SELLOFF, green=GREEN, mcap: float | None = 5e8, after=()) -> pd.DataFrame:
    closes = [5.0] * 70 + list(RUN) + list(selloff)
    bars = bars_from_closes(SYM, closes)
    tail = bars_from_ohlc(SYM, [list(green), *[list(r) for r in after]])
    tail["ts"] = pd.bdate_range(bars["ts"].iloc[-1], periods=len(tail) + 1, tz=bars["ts"].dt.tz)[1:]
    panel = add_features(pd.concat([bars, tail], ignore_index=True))
    return panel if mcap is None else panel.assign(mcap_pit=mcap)


def test_fires_with_the_signal_day_low_as_the_stop():
    panel = _panel()
    (s,) = SykesFirstGreenDay().signals(panel, last_date(panel))
    assert s.entry_type == EntryType.OPEN and s.entry == pytest.approx(9.2) and s.stop == pytest.approx(7.9)
    assert s.target is None and s.features["peak_close"] == 12.0 and s.features["base_close"] == 5.0
    assert s.features["selloff"] == pytest.approx(1 - 8.0 / 12.0) and s.features["max_hold_days"] == 1.0


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(selloff=(10.5, 9.5, 8.8, 8.9)),  # the day before the signal closed up
        dict(selloff=(11.5, 11.0, 10.0, 9.0)),  # only 25% off the peak
        dict(green=(8.0, 9.3, 7.9, 9.2, 1_200_000.0)),  # volume under 1.5x the 20-session average
        dict(green=(8.0, 9.3, 7.9, 8.5, 3_000_000.0)),  # close below the top quarter of the range
        dict(green=(8.3, 8.4, 7.9, 8.2, 3_000_000.0)),  # closes up on the day but below its open: not green
        dict(mcap=3e9),  # market cap above $2B
        dict(mcap=None),  # no market-cap column: silent
    ],
)
def test_no_signal_cases(kwargs):
    panel = _panel(**kwargs)
    assert SykesFirstGreenDay().signals(panel, last_date(panel)) == []


def test_price_band_and_runner_multiple():
    panel = _panel()
    assert SykesFirstGreenDay({"runner_mult": 2.5}).signals(panel, last_date(panel)) == []  # the run was 2.4x
    assert SykesFirstGreenDay({"max_price": 9.0}).signals(panel, last_date(panel)) == []
    assert SykesFirstGreenDay({"min_price": 9.5}).signals(panel, last_date(panel)) == []


def test_backtest_buys_the_next_open_and_sells_that_close():
    panel = _panel(after=[(9.5, 10.2, 9.3, 10.0, 2e6), (10.0, 10.1, 9.0, 9.1, 2e6)])
    days = sorted(panel["ts"].dt.date.unique())
    res = run_backtest(SykesFirstGreenDay(), panel, days[-3], days[-1], costs=CostModel(slippage_bps=0.0))
    trade = res.trades.iloc[0]
    assert trade["entry_ts"].date() == days[-2] and trade["entry_price"] == pytest.approx(9.5)
    assert trade["exit_ts"].date() == days[-2] and trade["exit_price"] == pytest.approx(10.0)
