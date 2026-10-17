"""industry_leader_lag_smallmid (docs/proposals/swing-methods-2026-10/batch6/industry_leader_lag_smallmid.md) on a
hand-built week end: one industry that signals and one for each way an industry or a follower is left out."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing_engine.data.calendar import trading_days
from swing_engine.strategies import industry_leader_lag_smallmid as mod
from tests.features_gbm import NY_TZ

DAYS = trading_days("2025-10-20", "2025-10-27")
FRIDAY, THURSDAY = date(2025, 10, 24), date(2025, 10, 23)
# sic2 -> (leader 5-session returns in percent, number of followers)
INDUSTRIES = {36: ([6.0, 7.0, 8.0], 12), 60: ([3.0, 4.0, 5.0], 10), 28: ([1.0, 1.0, 1.0], 10), 49: ([-2.0] * 3, 10),
              35: ([0.0] * 3, 10), 20: ([10.0] * 3, 9),  # strongest leaders, one follower short
              73: ([9.0, 9.0], 10)}  # two leaders: does not count
N_LEADERS = sum(len(v[0]) for v in INDUSTRIES.values())


def make_panel() -> pd.DataFrame:
    ts = pd.DatetimeIndex(pd.to_datetime(DAYS)).tz_localize(NY_TZ)
    specs: dict[str, dict] = {}
    for sic, (leaders, n_follow) in INDUSTRIES.items():
        for i, r in enumerate(leaders):
            specs[f"L{sic}_{i}"] = {"sic2": float(sic), "roc_5": r, "mcap_pit": 1e12 - len(specs)}
        for i in range(n_follow):
            specs[f"F{sic}_{i}"] = {"sic2": float(sic), "roc_5": float(i), "mcap_pit": 1e9 - len(specs)}
    specs["F36_0"]["days_since_reverse_split"] = 100.0  # inside event_avoid_filters
    specs["F36_1"]["days_since_earnings"] = 2.0  # its own earnings this week
    frames = [pd.DataFrame({"symbol": s, "ts": ts, "open": 20.0, "high": 20.2, "low": 19.8, "close": 20.0, "volume": 1e6,
                            "med_dv_63": 5e6, "days_since_earnings": 30.0, "days_since_reverse_split": np.nan, **c})
              for s, c in specs.items()]
    return pd.concat(frames, ignore_index=True)


def strat(**over):
    return mod.IndustryLeaderLagSmallmid({"leader_top": N_LEADERS, **over})


def test_week_end_follows_the_calendar():
    assert mod.is_week_end(FRIDAY) and not mod.is_week_end(THURSDAY)
    assert mod.is_week_end(date(2025, 4, 17)) and not mod.is_week_end(date(2025, 4, 16))  # Good Friday is closed


def test_buys_the_laggards_of_the_one_strong_industry_at_the_week_end():
    panel, s = make_panel(), strat()
    sigs = sorted(s.signals(panel, FRIDAY), key=lambda x: -x.score)
    # industry 36: L = 7%; followers with own return <= 4% qualify; F36_0 is avoided and F36_1 reported earnings
    assert [x.symbol for x in sigs] == ["F36_2", "F36_3", "F36_4"]
    top = sigs[0]
    assert top.score == pytest.approx(5.0) and top.features["leader_return_pct"] == pytest.approx(7.0)
    assert top.stop == pytest.approx(20.0 * 0.85) and top.target is None
    assert [x.symbol for x in sorted(strat(max_names=2).signals(panel, FRIDAY), key=lambda x: -x.score)] == ["F36_2", "F36_3"]
    assert s.signals(panel, THURSDAY) == [] and s.signals(panel, DAYS[-1]) == []
    assert s.params["max_hold_days"] == 5 and s.engine_trail is False


def test_industry_and_follower_rules_each_bind():
    panel = make_panel()
    syms = lambda **over: {x.symbol for x in strat(**over).signals(panel, FRIDAY)}  # noqa: E731
    # six counting industries: the percentile cut (rank > 0.8) now keeps the two strongest
    assert {s[:3] for s in syms(min_followers=9)} == {"F20", "F36"}  # industry 20 counts with nine followers
    assert {s[:3] for s in syms(min_leaders=2)} == {"F73", "F36"}  # industry 73 counts with two leaders
    assert {s[:3] for s in syms(top_industry_fraction=0.40)} == {"F36", "F60"}  # the two strongest of five
    assert syms(top_industry_fraction=0.40, min_leader_return_pct=5.0) == syms()  # 60's 4% is under the floor
    assert syms(min_gap_pct=5.0) == {"F36_2"} and syms(earnings_sessions=2) == syms() | {"F36_1"}
    thin = panel.assign(med_dv_63=panel["med_dv_63"].where(~panel["symbol"].isin(["F36_10", "F36_11", "F36_9"]), 5e5))
    # nine liquid followers left: industry 36 no longer counts and industry 60 is the strongest of the rest
    assert {x.symbol for x in strat().signals(thin, FRIDAY)} == {"F60_0", "F60_1"}


def test_point_in_time_and_silence_without_the_joins():
    panel, s = make_panel(), strat()
    later = panel["ts"].dt.date > FRIDAY
    shocked = panel.assign(roc_5=panel["roc_5"].where(~later, 50.0))
    dump = lambda p: [x.model_dump_json() for x in s.signals(p, FRIDAY)]  # noqa: E731
    assert dump(shocked) == dump(panel) == dump(panel.loc[~later]) != []
    for col in ("mcap_pit", "sic2", "days_since_earnings"):
        assert s.signals(panel.drop(columns=col), FRIDAY) == []
