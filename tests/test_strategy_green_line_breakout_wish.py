"""green_line_breakout_wish: the dormant all-time-high line from completed months, the cross, the gate and exits."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.core.models import PositionContext
from swing_engine.features.extra import ensure_extra
from swing_engine.strategies.green_line_breakout_wish import LINE, GreenLineBreakoutWish, green_line
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, last_date

SYM, N = "GLB", 560  # 560 business days from 2024-01-02: the last bar is in February 2026


def _bar(close: float, high: float | None = None) -> list[float]:
    return [close, high if high is not None else close + 0.2, close - 0.5, close, 1_000_000.0]


def _panel(peak_at: int, last_close: float = 121.0, spy_step: float = 0.1) -> pd.DataFrame:
    """Flat at 100 with one peak bar (close 120, high 120.6) at ``peak_at``; the day before the signal closes at
    119.5 and the signal day at ``last_close``. SPY trends by ``spy_step`` a day."""
    rows = [_bar(100.0) for _ in range(N)]
    rows[peak_at] = _bar(120.0, high=120.6)
    rows[-2], rows[-1] = _bar(119.5), _bar(last_close, high=last_close + 0.2)
    spy = [_bar(400.0 + spy_step * i) for i in range(N)]
    panel = add_features(pd.concat([bars_from_ohlc(SYM, rows), bars_from_ohlc("SPY", spy)], ignore_index=True))
    panel["mcap_pit"] = np.where(panel["symbol"] == SYM, 1e9, np.nan)
    # 500 larger companies with a bar on the signal day only, so GLB is market-cap rank 501 (SMALLMID starts there)
    fill = pd.DataFrame({"symbol": [f"BIG{i:03d}" for i in range(500)], "ts": panel["ts"].iloc[-1], "open": 50.0,
                         "high": 50.0, "low": 50.0, "close": 50.0, "volume": 1e6, "mcap_pit": 1e10})
    return pd.concat([panel, fill], ignore_index=True)


def test_peak_inside_the_high_window_draws_the_line_at_the_monthly_high():
    panel = _panel(peak_at=N - 160)  # about seven months back: its daily high (120.6) is the line
    sigs = GreenLineBreakoutWish().signals(panel, last_date(panel))
    assert [s.symbol for s in sigs] == [SYM]
    s = sigs[0]
    assert s.features[LINE] == pytest.approx(120.6)
    assert s.entry == pytest.approx(121.0) and s.stop == pytest.approx(121.0 * 0.85) and s.target is None
    between = _panel(peak_at=N - 160, last_close=120.3)  # above the peak close, not above the peak high
    assert GreenLineBreakoutWish().signals(between, last_date(between)) == []


def test_older_peak_is_drawn_at_its_highest_close_and_survives_the_replay_lookback():
    strat = GreenLineBreakoutWish()
    panel = ensure_extra(_panel(peak_at=100), strat.extra_features)  # the replay attaches extras on the full panel
    sigs = strat.signals(panel, last_date(panel))
    assert len(sigs) == 1 and sigs[0].features[LINE] == pytest.approx(120.0)  # ath_close, not the 120.6 high
    recent = panel.groupby("symbol").tail(300)  # research.replay.SIGNAL_LOOKBACK_SESSIONS
    assert [s.model_dump() for s in strat.signals(recent, last_date(panel))] == [s.model_dump() for s in sigs]


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(peak_at=N - 40),  # the high is under three completed months old: no green line
        dict(peak_at=N - 160, last_close=119.9),  # no close above the line
        dict(peak_at=N - 160, spy_step=-0.1),  # SPY below its 50-day average
    ],
)
def test_no_signal_cases(kwargs):
    panel = _panel(**kwargs)
    assert GreenLineBreakoutWish().signals(panel, last_date(panel)) == []


def test_silent_without_columns_history_or_smallmid_rank():
    panel = _panel(peak_at=N - 160)
    as_of = last_date(panel)
    assert GreenLineBreakoutWish().signals(panel.drop(columns="mcap_pit"), as_of) == []
    assert GreenLineBreakoutWish({"min_history_bars": N + 1}).signals(panel, as_of) == []
    assert GreenLineBreakoutWish().signals(panel.loc[~panel["symbol"].str.startswith("BIG")], as_of) == []
    assert GreenLineBreakoutWish().signals(panel.loc[panel["symbol"] != "SPY"], as_of) == []  # no market proxy


def test_green_line_needs_three_completed_months_after_the_high():
    month = np.repeat(np.arange(100, 106), 2)  # six months of two bars; the last month is the current one
    high = np.full(12, 10.0)
    high[2] = 15.0  # month 101: months 102, 103 and 104 completed below it
    assert green_line(high, month, older_high=12.0, dormant_months=3) == 15.0
    assert green_line(high, month, older_high=20.0, dormant_months=3) == 20.0  # an older, higher peak is the line
    high[4] = 16.0  # month 102 beat it and has only two completed months behind it
    assert green_line(high, month, older_high=12.0, dormant_months=3) is None
    high[4], high[11] = 10.0, 30.0  # the current month never counts
    assert green_line(high, month, older_high=12.0, dormant_months=3) == 15.0


def test_exits_close_below_the_line_and_the_150_day_trail():
    strat = GreenLineBreakoutWish()
    pos = PositionContext(entry_price=100.0, best_price=110.0, entry_features={LINE: 98.0})
    row = pd.Series({"close": 97.5, "sma_150": 90.0})
    assert not strat.should_exit(row, 3, pos)  # inside the 1% slack
    assert strat.should_exit(pd.Series({"close": 97.0, "sma_150": 90.0}), 3, pos)  # below 98 x 0.99
    winner = PositionContext(entry_price=100.0, best_price=120.0, entry_features={LINE: 98.0})
    assert strat.should_exit(pd.Series({"close": 110.0, "sma_150": 111.0}), 40, winner)  # +20% reached, under sma_150
    assert not strat.should_exit(pd.Series({"close": 110.0, "sma_150": 111.0}), 40, pos)  # trail not armed
    assert not strat.should_exit(pd.Series({"close": 50.0, "sma_150": 111.0}), 40)  # no position facts: never fires
