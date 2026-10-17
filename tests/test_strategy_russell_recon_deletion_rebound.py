"""russell_recon_deletion_rebound: fires at the reconstitution-day close on names whose market-cap rank fell out of
the band between the two rank days, the exclusions, the order and the stop. The 20-session exit is the engine's time
stop (`max_hold_days`). Point-in-time is also covered by tests/test_strategies_all.py."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from swing_engine.core import registry
from swing_engine.data.calendar import trading_days
from tests.features_gbm import NY_TZ

NAME = "russell_recon_deletion_rebound"
PREV_RANK_DAY, RANK_DAY, RECON_DAY = date(2023, 4, 28), date(2024, 4, 30), date(2024, 6, 28)
DAYS = trading_days("2023-04-03", "2024-07-10")
SWITCH = date(2024, 1, 2)  # market caps change here, between the two rank days
# symbol -> (mcap before, mcap after, daily volume, days_since_reverse_split); close is $20 throughout
SPEC: dict[str, tuple[float, float, float, float]] = {
    "S1": (100.0, 100.0, 1e6, np.nan), "S2": (50.0, 50.0, 1e6, np.nan), "S3": (40.0, 40.0, 1e6, np.nan),
    "S4": (30.0, 30.0, 1e6, np.nan), "S5": (20.0, 20.0, 1e6, np.nan),
    "FALL": (90.0, 4.0, 1e6, np.nan),  # rank 2 -> 9
    "FALL2": (80.0, 10.0, 1e6, np.nan),  # rank 3 -> 6
    "SPLIT": (70.0, 8.0, 1e6, 50.0),  # rank 4 -> 7, reverse split 50 sessions ago
    "THIN": (60.0, 6.0, 1e3, np.nan),  # rank 5 -> 8, $20k a day
}
SMALL = {"prev_rank_min": 2, "prev_rank_max": 5, "rank_min": 6}  # the card's 1,200 / 2,900 / 3,200 at toy scale


def panel(distress: dict[str, float] | None = None) -> pd.DataFrame:
    frames = []
    for sym, (before, after, volume, split) in SPEC.items():
        f = pd.DataFrame({"symbol": sym, "ts": pd.DatetimeIndex(pd.to_datetime(DAYS)).tz_localize(NY_TZ), "open": 20.0,
                          "high": 20.1, "low": 19.9, "close": 20.0, "volume": volume})
        f["mcap_pit"] = np.where(np.array(DAYS) < SWITCH, before, after)
        f["close_as_traded"] = 20.0
        f["med_dv_63"] = 20.0 * volume
        f["days_since_reverse_split"] = split
        f["days_since_8k_distress"] = (distress or {}).get(sym, np.nan)
        frames.append(f)
    return pd.concat(frames, ignore_index=True)


def strat(**params):
    return registry.get("strategy", NAME)({**SMALL, **params})


def symbols(sigs) -> list[str]:
    return [s.symbol for s in sigs]


def test_buys_the_fallen_names_at_the_reconstitution_close_largest_fall_first():
    p = panel()
    got = strat().signals(p, RECON_DAY)
    assert symbols(got) == ["FALL", "FALL2"]  # SPLIT: reverse split inside 126 sessions; THIN: too illiquid
    s = got[0]
    assert s.entry == 20.0 and s.stop == 15.0 and s.target is None and s.score > got[1].score
    assert s.features == {"rank_r": 9.0, "rank_prev": 2.0, "rank_fall": 7.0}
    assert symbols(strat(max_names=1).signals(p, RECON_DAY)) == ["FALL"]
    assert symbols(strat(avoid_sessions=40).signals(p, RECON_DAY)) == ["FALL", "FALL2", "SPLIT"]  # tie: by symbol
    assert strat(min_close=25.0).signals(p, RECON_DAY) == []
    assert strat().signals(p, RANK_DAY) == [] and strat().signals(p, date(2024, 6, 27)) == []  # recon day only
    assert registry.get("strategy", NAME)().params["max_hold_days"] == 20


def test_distress_8k_inside_the_window_is_excluded():
    assert symbols(strat().signals(panel({"FALL2": 100.0}), RECON_DAY)) == ["FALL"]
    assert symbols(strat().signals(panel({"FALL2": 200.0}), RECON_DAY)) == ["FALL", "FALL2"]


def test_silent_without_a_needed_column_or_rank_day():
    p = panel()
    for col in ("mcap_pit", "days_since_reverse_split", "days_since_8k_distress"):
        assert strat().signals(p.drop(columns=col), RECON_DAY) == []
    assert strat().signals(p.loc[p["ts"].dt.date > PREV_RANK_DAY], RECON_DAY) == []


def test_ranks_come_from_the_rank_day_not_from_later_market_caps():
    p = panel()
    after_rank_day = p["ts"].dt.date > RANK_DAY
    moved = p.assign(mcap_pit=np.where(after_rank_day, 1.0, p["mcap_pit"]))  # caps after the rank day are ignored
    assert symbols(strat().signals(moved, RECON_DAY)) == ["FALL", "FALL2"]
