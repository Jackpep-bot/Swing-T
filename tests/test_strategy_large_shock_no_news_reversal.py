"""large_shock_no_news_reversal (docs/proposals/swing-methods-2026-10/batch6/large_shock_no_news_reversal.md) on a
hand-built shock day: one clean shock and one name for each thing the card excludes."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.data.calendar import trading_days
from swing_engine.strategies import large_shock_no_news_reversal as mod
from tests.features_gbm import NY_TZ

DAYS = trading_days("2025-06-02", "2025-09-12")
SHOCK_DAY = DAYS[-3]
K = len(DAYS)
AT = K - 3
BASE = {"news_flag_1d": 0.0, "days_since_8k": 30.0, "days_since_earnings": 30.0, "sessions_to_expected_earnings": 30.0,
        "med_dv_63": 5e7}
CASES: dict[str, dict] = {
    "SHOCK": {}, "NEWS": {"news_flag_1d": 1.0}, "NOFLAG": {"news_flag_1d": np.nan}, "K8": {"days_since_8k": 1.0},
    "EARN": {"days_since_earnings": 2.0}, "EXPECT": {"sessions_to_expected_earnings": 2.0}, "MILD": {"drop": -0.04},
    "NOISY": {"noise": 0.03}, "THIN": {"med_dv_63": 1e6}, "CHEAP": {"price": 4.0},
    "SPLIT": {"days_since_reverse_split": 100.0},
}


def make_panel() -> pd.DataFrame:
    ts = pd.DatetimeIndex(pd.to_datetime(DAYS)).tz_localize(NY_TZ)
    frames = []
    for sym, case in CASES.items():
        case = dict(case)
        drop, noise, price = case.pop("drop", -0.08), case.pop("noise", 0.005), case.pop("price", 40.0)
        excess = np.where(np.arange(K) % 2 == 0, noise, -noise)  # alternating: a known standard deviation
        excess[AT] = drop
        close = np.full(K, price)
        frames.append(pd.DataFrame({"symbol": sym, "ts": ts, "open": close, "high": close * 1.01, "low": close * 0.96,
                                    "close": close, "volume": 1e6, "rel_ret_1d": excess, "roc_1": 100.0 * excess,
                                    **BASE, **case}))
    return pd.concat(frames, ignore_index=True)


def strat(**over):
    return mod.LargeShockNoNewsReversal({"universe_top": 10, **over})


def test_fires_only_on_the_clean_shock():
    panel, s = make_panel(), strat()
    sigs = s.signals(panel, SHOCK_DAY)
    assert [x.symbol for x in sigs] == ["SHOCK"]  # every other name breaks one rule of the card
    sig = sigs[0]
    assert sig.entry == 40.0 and sig.stop == pytest.approx(40.0 - 2.0 * (40.4 - 38.4)) and sig.target is None
    sd = np.std(np.where(np.arange(AT - 60, AT) % 2 == 0, 0.005, -0.005), ddof=1)
    assert sig.features["shock_sigmas"] == pytest.approx(-0.08 / sd) and sig.score == pytest.approx(0.08 / sd)
    assert s.signals(panel, DAYS[AT - 1]) == [] and s.signals(panel, DAYS[AT + 1]) == []
    assert s.params["max_hold_days"] == 10 and s.engine_trail is False


def test_each_exclusion_is_the_only_thing_stopping_its_name():
    panel = make_panel()
    assert [x.symbol for x in strat(universe_top=11).signals(panel, SHOCK_DAY)] == ["SHOCK", "THIN"]
    assert {x.symbol for x in strat(min_close=3.0).signals(panel, SHOCK_DAY)} == {"SHOCK", "CHEAP"}
    assert {x.symbol for x in strat(max_return_pct=-3.0).signals(panel, SHOCK_DAY)} == {"SHOCK", "MILD"}
    assert {x.symbol for x in strat(shock_sigmas=2.0).signals(panel, SHOCK_DAY)} == {"SHOCK", "NOISY"}
    assert {x.symbol for x in strat(no_8k_sessions=0).signals(panel, SHOCK_DAY)} == {"SHOCK", "K8"}
    assert {x.symbol for x in strat(earnings_sessions=1).signals(panel, SHOCK_DAY)} == {"SHOCK", "EARN", "EXPECT"}


def test_point_in_time_short_history_and_silence_without_the_joins():
    panel, s = make_panel(), strat()
    later = panel["ts"].dt.date > SHOCK_DAY
    shocked = panel.assign(rel_ret_1d=panel["rel_ret_1d"].where(~later, 0.5), close=panel["close"].where(~later, 1.0))
    dump = lambda p: [x.model_dump_json() for x in s.signals(p, SHOCK_DAY)]  # noqa: E731
    assert dump(shocked) == dump(panel) == dump(panel.loc[~later]) != []
    young = panel.loc[panel["ts"].dt.date >= DAYS[AT - 59]]  # 59 sessions before the shock: no 60-session deviation
    assert s.signals(young, SHOCK_DAY) == []
    for col in ("news_flag_1d", "days_since_8k", "days_since_earnings", "sessions_to_expected_earnings"):
        assert s.signals(panel.drop(columns=col), SHOCK_DAY) == []
