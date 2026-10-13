"""pocket_pivot_morales_kacher: the down-volume rule, the card's filters, the stop and the 10-day / 50-day trail."""
from __future__ import annotations

import pandas as pd
import pytest

from swing_engine.strategies.pocket_pivot_morales_kacher import TO_EXP, PocketPivotMoralesKacher
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, last_date, trend_rows

SYM = "PPV"
PIVOT = (96.0, 98.0, 95.6, 97.8, 1_500_000.0)  # up day off the 10-day line, volume above every down day
# ten sessions before the pivot: alternating down (800k shares) and up (1M) closes around 96
BASE = [(96.0, 96.6, 95.4, 95.8 if i % 2 == 0 else 96.1, 800_000.0 if i % 2 == 0 else 1_000_000.0) for i in range(10)]


def _panel(base=BASE, pivot=PIVOT, to_exp: float = 30.0, drop: str | None = None) -> pd.DataFrame:
    rows = trend_rows(230, start=50.0, step=0.2) + [list(r) for r in base] + [list(pivot)]
    panel = add_features(bars_from_ohlc(SYM, rows)).assign(mcap_pit=1e9, **{TO_EXP: to_exp})
    # 500 larger companies with a bar on the signal day only, so PPV is market-cap rank 501 (SMALLMID starts there)
    fill = pd.DataFrame({"symbol": [f"BIG{i:03d}" for i in range(500)], "ts": panel["ts"].iloc[-1], "open": 50.0,
                         "high": 50.0, "low": 50.0, "close": 50.0, "volume": 1e6, "mcap_pit": 1e10})
    panel = pd.concat([panel, fill], ignore_index=True)
    return panel.drop(columns=drop) if drop else panel


def test_fires_with_card_geometry():
    panel = _panel()
    sigs = PocketPivotMoralesKacher().signals(panel, last_date(panel))
    assert [s.symbol for s in sigs] == [SYM]
    s = sigs[0]
    assert s.entry == pytest.approx(97.8) and s.target is None
    assert s.stop == pytest.approx(97.8 * 0.92)  # the lower of the pivot low (95.6) and entry x 0.92
    assert s.features["max_down_volume"] == 800_000.0 and s.score == pytest.approx(1.5 / 0.8)
    assert s.features["max_hold_days"] == 63.0


def test_stop_is_the_pivot_low_when_it_is_lower():
    panel = _panel(pivot=(96.0, 98.0, 89.0, 97.8, 1_500_000.0))
    assert PocketPivotMoralesKacher().signals(panel, last_date(panel))[0].stop == pytest.approx(89.0)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(pivot=(96.0, 98.0, 95.6, 97.8, 790_000.0)),  # volume under the largest down-day volume
        dict(pivot=(96.0, 96.2, 95.0, 95.5, 1_500_000.0)),  # down close
        dict(pivot=(96.0, 99.9, 95.6, 96.3, 1_500_000.0)),  # close in the lower half of the range
        dict(pivot=(97.5, 103.0, 97.4, 102.9, 1_500_000.0)),  # low not near sma_10 and close extended above it
        dict(base=[(96.0, 96.6, 95.4, 96.0 + 0.01 * i, 1_000_000.0) for i in range(10)]),  # no down day (and a wedge)
        dict(base=[(96.0, 96.6, 95.4, 95.0 + 0.1 * i if i != 4 else 94.9, 9e5) for i in range(10)]),  # 8 up closes
        dict(to_exp=3.0),  # earnings expected within 3 sessions
        dict(drop="mcap_pit"),  # no market-cap column: silent
        dict(drop=TO_EXP),  # no expected-earnings column: silent
    ],
)
def test_no_signal_cases(kwargs):
    panel = _panel(**kwargs)
    assert PocketPivotMoralesKacher().signals(panel, last_date(panel)) == []


def test_wedge_and_v_tests_are_the_blockers():
    wedge = _panel(base=[(96.0, 96.6, 95.4, 95.0 + 0.1 * i if i != 4 else 94.9, 9e5) for i in range(10)])
    assert len(PocketPivotMoralesKacher({"wedge_up_closes": 11}).signals(wedge, last_date(wedge))) == 1
    panel = _panel()  # the ten sessions before the pivot gained 0.3%
    assert PocketPivotMoralesKacher({"max_prior_return": 0.0}).signals(panel, last_date(panel)) == []
    closes = [95.8, 96.5, 95.8, 96.1, 95.8, 96.1, 95.8, 96.1, 95.8, 96.1]  # t-9 closed at 96.5, above the pivot close
    panel = _panel(base=[(96.0, 96.6, 95.4, c, 9e5) for c in closes], pivot=(96.0, 96.6, 95.6, 96.4, 1_500_000.0))
    assert len(PocketPivotMoralesKacher().signals(panel, last_date(panel))) == 1
    assert PocketPivotMoralesKacher({"downtrend_sessions": 9}).signals(panel, last_date(panel)) == []


def test_outside_smallmid_is_silent():
    panel = _panel()
    panel = panel.loc[~panel["symbol"].str.startswith("BIG")]  # PPV is now the largest name, not rank 501+
    assert PocketPivotMoralesKacher().signals(panel, last_date(panel)) == []


def test_trail_is_the_ten_day_after_seven_weeks_else_the_fifty_day():
    strat = PocketPivotMoralesKacher()
    row = {"close": 99.0, "low": 98.0, "sma_10": 100.0, "sma_50": 90.0, strat.respect_col: 0.6}
    assert strat.trail_stop(pd.Series(row)) == pytest.approx(98.0)  # 35 closes above sma_10, first close below it
    assert strat.trail_stop(pd.Series({**row, "close": 101.0})) is None
    young = {**row, strat.respect_col: 0.4}  # the 10-day was not respected for seven weeks: 50-day rule
    assert strat.trail_stop(pd.Series(young)) is None
    assert strat.trail_stop(pd.Series({**young, "close": 89.0, "low": 88.0})) == pytest.approx(88.0 * 0.975)
    assert strat.trail_stop(pd.Series({"close": 89.0})) is None
