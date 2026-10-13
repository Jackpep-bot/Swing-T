"""russell_recon_addition_frontrun: the reconstitution calendar, the two rank-day snapshots read from the panel, the
candidate rule, the cap, the stop and the recon-day exit. Point-in-time is also covered by tests/test_strategies_all.py."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from swing_engine.core import registry
from swing_engine.data.calendar import trading_days
from swing_engine.strategies.russell_recon_addition_frontrun import CALENDAR_PARAMS, recon_events
from tests.features_gbm import NY_TZ

NAME = "russell_recon_addition_frontrun"
PREV_RANK_DAY, RANK_DAY, RECON_DAY = date(2023, 4, 28), date(2024, 4, 30), date(2024, 6, 28)
DAYS = trading_days("2023-04-03", "2024-07-10")
SWITCH = date(2024, 1, 2)  # market caps change here, between the two rank days
# symbol -> (mcap before, mcap after, daily volume, first bar); close is $20 throughout
SPEC: dict[str, tuple[float, float, float, date]] = {
    "BIG1": (100.0, 100.0, 1e6, DAYS[0]), "BIG2": (90.0, 90.0, 1e6, DAYS[0]), "STAY": (70.0, 70.0, 1e6, DAYS[0]),
    "LOW1": (20.0, 20.0, 1e6, DAYS[0]), "LOW2": (15.0, 15.0, 1e6, DAYS[0]),
    "UP": (10.0, 80.0, 1e6, DAYS[0]),  # previous rank 6 -> rank 4
    "THIN": (9.0, 85.0, 1e3, DAYS[0]),  # previous rank 7 -> rank 3, but $20k a day
    "NEW": (np.nan, 75.0, 1e6, date(2023, 6, 1)),  # listed after the previous rank day: rank 5, under 252 bars
    "FUND": (np.nan, np.nan, 1e6, DAYS[0]),  # no filed share count: never ranked
}
SMALL = {"prev_rank_min": 5, "rank_min": 3, "rank_max": 5}  # the card's 3,100 / 1,300 / 2,800 at toy scale


def panel() -> pd.DataFrame:
    frames = []
    for sym, (before, after, volume, first) in SPEC.items():
        days = [d for d in DAYS if d >= first]
        f = pd.DataFrame({"symbol": sym, "ts": pd.DatetimeIndex(pd.to_datetime(days)).tz_localize(NY_TZ), "open": 20.0,
                          "high": 20.1, "low": 19.9, "close": 20.0, "volume": volume})
        f["mcap_pit"] = np.where(np.array(days) < SWITCH, before, after)
        f["close_as_traded"] = 20.0
        f["med_dv_63"] = 20.0 * volume
        frames.append(f)
    return pd.concat(frames, ignore_index=True)


def strat(**params):
    return registry.get("strategy", NAME)({**SMALL, **params})


def symbols(sigs) -> list[str]:
    return [s.symbol for s in sigs]


def test_calendar_is_last_april_session_and_fourth_june_friday_plus_the_2026_second_event():
    assert recon_events(CALENDAR_PARAMS, 2024) == [(date(2023, 4, 28), date(2023, 6, 23)), (RANK_DAY, RECON_DAY)]
    assert recon_events(CALENDAR_PARAMS, 2026)[-1] == (date(2026, 10, 30), date(2026, 12, 11))
    assert registry.get("strategy", NAME)().params["prev_rank_min"] == 3100


def test_buys_names_that_crossed_into_the_band_on_the_rank_day_only():
    p = panel()
    got = strat().signals(p, RANK_DAY)
    assert symbols(got) == ["UP"]  # THIN: too illiquid; NEW: under 252 bars; STAY / LOW*: no crossing
    s = got[0]
    assert s.entry == 20.0 and s.stop == 15.0 and s.target is None
    assert s.features["rank_r"] == 4.0 and s.features["rank_prev"] == 6.0
    assert symbols(strat(min_history_bars=200).signals(p, RANK_DAY)) == ["UP", "NEW"]  # largest cap first
    assert symbols(strat(min_history_bars=200, max_names=1).signals(p, RANK_DAY)) == ["UP"]
    assert symbols(strat(min_median_dollar_volume=1e4, max_names=1).signals(p, RANK_DAY)) == ["THIN"]
    assert strat().signals(p, date(2024, 4, 29)) == [] and strat().signals(p, date(2024, 5, 1)) == []


def test_silent_without_market_caps_or_without_the_previous_rank_day():
    p = panel()
    assert strat().signals(p.drop(columns="mcap_pit"), RANK_DAY) == []
    assert strat().signals(p.loc[p["ts"].dt.date > PREV_RANK_DAY], RANK_DAY) == []


def test_ranks_use_only_rows_up_to_the_rank_day():
    p = panel()
    later = p["ts"].dt.date > RANK_DAY
    shuffled = p.assign(mcap_pit=np.where(later, 1.0, p["mcap_pit"]))
    cut = strat().signals(p.loc[~later], RANK_DAY)
    assert [s.model_dump_json() for s in strat().signals(shuffled, RANK_DAY)] == [s.model_dump_json() for s in cut]


def test_exit_on_the_reconstitution_day():
    s = strat()
    row = lambda d: pd.Series({"ts": pd.Timestamp(d).tz_localize(NY_TZ), "close": 20.0})  # noqa: E731
    assert not s.should_exit(row(date(2024, 5, 1)), 1) and not s.should_exit(row(date(2024, 6, 27)), 39)
    assert s.should_exit(row(RECON_DAY), 40)
    indexed = pd.Series({"close": 20.0}, name=(pd.Timestamp(RECON_DAY).tz_localize(NY_TZ), "UP"))  # run_backtest row
    assert s.should_exit(indexed, 40) and not s.should_exit(pd.Series({"close": 20.0}), 40)
    assert not s.should_exit(row(date(2026, 12, 10)), 28) and s.should_exit(row(date(2026, 12, 11)), 29)
