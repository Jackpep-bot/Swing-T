"""code33_trend_template (docs/proposals/swing-methods-2026-10/batch5/code33_trend_template.md) on hand-built rows:
every template and Code 33 column is given, so each rule is switched on and off by one value."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.data.calendar import trading_days
from tests.features_gbm import NY_TZ

NAME = "code33_trend_template"
DAYS = trading_days("2025-11-03", "2025-11-07")
YESTERDAY, TODAY = DAYS[2], DAYS[3]
# a stage-2 bar: close above rising averages in order, 67% above the low, 9% under the high, RS 85
GOOD = {"close": 100.0, "sma_10": 98.0, "sma_20": 96.0, "sma_50": 90.0, "sma_150": 80.0, "sma_200": 75.0,
        "linreg_slope_21_of_sma_200": 0.1, "high_52w": 110.0, "low_52w": 60.0, "rs_rating_ibd": 85.0, "atr_14": 2.0,
        "b5_code33": 1.0, "med_dv_63": 5e6}
CASES = {  # symbol: (values before TODAY, values from TODAY on) as changes to GOOD
    "FILING": ({"b5_code33": 0.0}, {}),  # the filing turns Code 33 on in an existing uptrend
    "TREND": ({"close": 89.0}, {}),  # Code 33 already on; the template completes today
    "OLD": ({}, {}),  # both already true yesterday: not the first session
    "EXTENDED": ({"b5_code33": 0.0}, {"sma_10": 95.0}),  # 5.3% above the 10-day
    "UNKNOWN": ({"b5_code33": 0.0}, {"b5_code33": np.nan}),
    "WEAKRS": ({"b5_code33": 0.0}, {"rs_rating_ibd": 69.0}),
    "FLAT200": ({"b5_code33": 0.0}, {"linreg_slope_21_of_sma_200": -0.1}),
    "NEARLOW": ({"b5_code33": 0.0}, {"low_52w": 80.0}),  # only 25% above the 52-week low
    "FARHIGH": ({"b5_code33": 0.0}, {"high_52w": 140.0}),  # 29% under the 52-week high
    "THIN": ({"b5_code33": 0.0}, {"med_dv_63": 5e5}),  # not in SMALLMID
    "WIDE": ({"b5_code33": 0.0}, {"atr_14": 5.0}),  # 2.5 ATR is wider than 8%
}


def make_panel() -> pd.DataFrame:
    ts = pd.DatetimeIndex(pd.to_datetime(DAYS)).tz_localize(NY_TZ)
    new = np.array([d >= TODAY for d in DAYS])
    frames = [pd.DataFrame({"symbol": f"BIG{i:03d}", "ts": ts, **GOOD, "mcap_pit": 1e12 - i}) for i in range(500)]
    for n, (sym, (before, after)) in enumerate(CASES.items()):
        f = pd.DataFrame({"symbol": sym, "ts": ts, **GOOD, "mcap_pit": 5e9 - n})
        for col in {*before, *after}:
            f[col] = np.where(new, after.get(col, GOOD[col]), before.get(col, GOOD[col]))
        frames.append(f)
    panel = pd.concat(frames, ignore_index=True)
    return panel.assign(open=panel["close"], high=panel["close"] * 1.01, low=panel["close"] * 0.99, volume=1e6)


def strat():
    return registry.get("strategy", NAME)()


def test_buys_the_first_session_code33_and_the_template_are_both_true():
    panel, s = make_panel(), strat()
    sigs = {x.symbol: x for x in s.signals(panel, TODAY)}
    assert sorted(sigs) == ["FILING", "TREND", "WIDE"]
    assert sigs["FILING"].entry == 100.0 and sigs["FILING"].stop == pytest.approx(95.0)  # 2.5 x ATR is the tighter stop
    assert sigs["WIDE"].stop == pytest.approx(92.0) and sigs["WIDE"].target is None  # capped at 8%
    assert sigs["TREND"].features["extension"] == pytest.approx(100.0 / 98.0 - 1.0)
    assert [x.symbol for x in s.signals(panel, YESTERDAY)] == []  # nothing was complete (OLD is not new either)
    assert s.signals(panel, DAYS[4]) == []  # the session after: no longer the first
    assert s.params["max_hold_days"] == 63 and s.engine_trail is False


def test_point_in_time_and_silent_without_the_join_columns():
    panel, s = make_panel(), strat()
    later = panel["ts"].dt.date > TODAY
    changed = panel.assign(close=panel["close"].where(~later, 1.0), b5_code33=panel["b5_code33"].where(~later, 0.0))
    dump = lambda p: [x.model_dump_json() for x in s.signals(p, TODAY)]  # noqa: E731
    assert dump(changed) == dump(panel) == dump(panel.loc[~later]) != []
    assert s.signals(panel.drop(columns="b5_code33"), TODAY) == []
    assert s.signals(panel.drop(columns="mcap_pit"), TODAY) == []


def test_exits_below_the_50_day_or_on_a_broken_code33_below_the_20_day():
    s = strat()
    row = lambda **kw: pd.Series({**GOOD, **kw})  # noqa: E731
    assert s.should_exit(row(), 5) is False
    assert s.should_exit(row(close=89.0), 5) is True  # close below sma_50
    assert s.should_exit(row(close=95.0, b5_code33=0.0), 5) is True  # filing broke Code 33 and close < sma_20
    assert s.should_exit(row(close=97.0, b5_code33=0.0), 5) is False  # broken, but still above the 20-day
    assert s.should_exit(row(close=95.0), 5) is False and s.should_exit(row(close=95.0, b5_code33=np.nan), 5) is False
