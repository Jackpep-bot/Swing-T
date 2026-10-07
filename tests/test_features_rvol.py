"""Time-of-day RVOL profile and the live lookup."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.features import rvol
from tests.features_gbm import intraday_bars

SESSIONS = ["2026-09-28", "2026-09-29", "2026-09-30"]
MINUTES = [570, 571, 572]


def test_profile_averages_last_days_sessions() -> None:
    bars = intraday_bars(["AAA", "BBB"], SESSIONS, MINUTES, seed=3)
    prof = rvol.build_rvol_profile(bars, days=2)
    assert list(prof.columns) == list(rvol.PROFILE_COLUMNS)
    assert len(prof) == 2 * rvol.MINUTES_PER_DAY
    assert (prof.n_sessions == 2).all()
    a = bars[bars.symbol == "AAA"].assign(day=lambda d: d.ts.dt.strftime("%Y-%m-%d"))
    cum = {day: g.sort_values("ts").volume.cumsum().to_numpy() for day, g in a.groupby("day")}
    last_two = SESSIONS[1:]
    exp_571 = np.mean([cum[d][1] for d in last_two])
    exp_full = np.mean([cum[d][2] for d in last_two])
    p = prof[prof.symbol == "AAA"].set_index("minute_of_day").avg_cum_volume
    assert p.loc[571] == pytest.approx(exp_571)
    assert p.loc[600] == pytest.approx(exp_full)  # carried forward after the last bar
    assert p.loc[0] == 0.0 and p.loc[569] == 0.0
    assert p.loc[570] == pytest.approx(np.mean([cum[d][0] for d in last_two]))


def test_rvol_now_frame_and_dict_agree() -> None:
    bars = intraday_bars(["AAA"], SESSIONS, MINUTES, seed=4)
    prof = rvol.build_rvol_profile(bars, days=20)
    lookup = rvol.profile_lookup(prof)
    base = prof[(prof.symbol == "AAA") & (prof.minute_of_day == 571)].avg_cum_volume.iloc[0]
    assert rvol.rvol_now("AAA", 3 * base, 571, prof) == pytest.approx(3.0)
    assert rvol.rvol_now("AAA", 3 * base, 571, lookup) == pytest.approx(3.0)
    assert np.isnan(rvol.rvol_now("ZZZ", 100.0, 571, lookup))
    assert np.isnan(rvol.rvol_now("ZZZ", 100.0, 571, prof))
    assert np.isnan(rvol.rvol_now("AAA", 100.0, 0, lookup))  # zero benchmark before the first bar
    assert rvol.rvol_now("AAA", 3 * base, 10_000, lookup) == rvol.rvol_now("AAA", 3 * base, 1439, lookup)


def test_minute_of_day_is_new_york_clock() -> None:
    ny = pd.Series(pd.to_datetime(["2026-09-28 09:30", "2026-09-28 16:00"]).tz_localize("America/New_York"))
    assert rvol.minute_of_day(ny).tolist() == [570, 960]
    utc = ny.dt.tz_convert("UTC")
    assert rvol.minute_of_day(utc).tolist() == [570, 960]


def test_empty_and_invalid_inputs() -> None:
    empty = rvol.build_rvol_profile(
        pd.DataFrame({"symbol": [], "ts": pd.Series([], dtype="datetime64[ns]"), "volume": []})
    )
    assert len(empty) == 0 and list(empty.columns) == list(rvol.PROFILE_COLUMNS)
    with pytest.raises(ValueError):
        rvol.build_rvol_profile(intraday_bars(["AAA"], SESSIONS, MINUTES), days=0)
    with pytest.raises(ValueError):
        rvol.build_rvol_profile(pd.DataFrame({"symbol": ["A"], "volume": [1.0]}))
