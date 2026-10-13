"""tax_loss_loser_rebound: the signal day, the year-to-date score from the prior year's last close, the SMALLMID and
event filters, the 30-name cap and the stop. The exit is the engine's time stop (`max_hold_days` 19 = the 10th
January session). Point-in-time is also covered by tests/test_strategies_all.py."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from swing_engine.core import registry
from swing_engine.data.calendar import trading_days
from tests.features_gbm import NY_TZ

NAME = "tax_loss_loser_rebound"
DAYS = trading_days("2023-12-01", "2024-12-31")
YEAR_END, SIGNAL_DAY = date(2023, 12, 29), date(2024, 12, 17)  # 9 sessions follow 12-17 in December 2024
EVENT_COLUMNS = ("days_since_reverse_split", "days_since_8k_distress", "days_since_8k_502", "days_since_earnings")
# symbol -> (2023 close, 2024 close, mcap, event columns); $2M a day each
SPEC: dict[str, tuple[float, float, float, dict[str, float]]] = {
    "MEGA": (100.0, 100.0, 9e9, {}),  # rank 1: above the SMALLMID band (ranks 2-9 here)
    "WORST": (100.0, 30.0, 8e8, {}),  # -70%
    "BAD": (100.0, 55.0, 7e8, {}),  # -45%
    "MILD": (100.0, 70.0, 6e8, {}),  # -30%: not a loser
    "PENNY": (10.0, 2.0, 5e8, {}),  # -80% but under $3
    "REVSPLIT": (100.0, 40.0, 4e8, {"days_since_reverse_split": 200.0}),
    "DELIST": (100.0, 40.0, 3e8, {"days_since_8k_distress": 100.0}),
    "CFOLEFT": (100.0, 40.0, 2e8, {"days_since_8k_502": 30.0, "days_since_earnings": 80.0}),
    "ROUTINE": (100.0, 45.0, 1e8, {"days_since_8k_502": 30.0, "days_since_earnings": 30.0}),  # 5.02 with earnings: kept
}
SMALL = {"mcap_rank_first": 2, "mcap_rank_last": 9}


def panel() -> pd.DataFrame:
    frames = []
    for sym, (old, new, mcap, events) in SPEC.items():
        close = np.where(np.array(DAYS) <= YEAR_END, old, new)
        f = pd.DataFrame({"symbol": sym, "ts": pd.DatetimeIndex(pd.to_datetime(DAYS)).tz_localize(NY_TZ), "open": close,
                          "high": close * 1.005, "low": close * 0.995, "close": close, "volume": 2e6 / close})
        f["mcap_pit"], f["med_dv_63"] = mcap, 2e6
        for col in EVENT_COLUMNS:
            f[col] = events.get(col, np.nan)
        frames.append(f)
    return pd.concat(frames, ignore_index=True)


def strat(**params):
    return registry.get("strategy", NAME)({**SMALL, **params})


def symbols(sigs) -> list[str]:
    return [s.symbol for s in sigs]


def test_buys_the_worst_year_to_date_losers_on_the_tenth_to_last_december_session():
    p = panel()
    got = strat().signals(p, SIGNAL_DAY)
    assert symbols(got) == ["WORST", "ROUTINE", "BAD"]  # most negative first; the event names and PENNY are out
    s = got[0]
    assert s.entry == 30.0 and s.stop == 21.0 and s.target is None and s.score > got[1].score
    assert abs(s.features["ytd_return"] + 0.70) < 1e-12
    assert symbols(strat(max_names=1).signals(p, SIGNAL_DAY)) == ["WORST"]
    assert symbols(strat(max_ytd_return=-0.5).signals(p, SIGNAL_DAY)) == ["WORST", "ROUTINE"]
    assert strat().signals(p, date(2024, 12, 16)) == [] and strat().signals(p, date(2024, 12, 18)) == []
    assert registry.get("strategy", NAME)().params["max_hold_days"] == 19


def test_event_windows_follow_the_avoid_filter_card():
    p = panel()
    wide = strat(avoid_reverse_split_sessions=100, avoid_distress_8k_sessions=50, avoid_502_sessions=20)
    assert set(symbols(wide.signals(p, SIGNAL_DAY))) == {"WORST", "BAD", "ROUTINE", "REVSPLIT", "DELIST", "CFOLEFT"}


def test_silent_without_a_needed_column_or_the_prior_year_end_bar():
    p = panel()
    for col in ("mcap_pit", *EVENT_COLUMNS):
        assert strat().signals(p.drop(columns=col), SIGNAL_DAY) == []
    assert strat().signals(p.loc[p["ts"].dt.date > YEAR_END], SIGNAL_DAY) == []
    listed_in_2024 = p.loc[(p["symbol"] != "WORST") | (p["ts"].dt.date > YEAR_END)]
    assert symbols(strat().signals(listed_in_2024, SIGNAL_DAY)) == ["ROUTINE", "BAD"]  # no prior-year close, no YTD
