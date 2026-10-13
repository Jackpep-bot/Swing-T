"""pre_earnings_runup_winners: winners are ranked on the prior quarter's last session, the trigger is five sessions
before the expected report, the floors, the stop, and the exits (two sessions to go, or an early report).
Point-in-time is also covered by tests/test_strategies_all.py."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from swing_engine.core import registry
from swing_engine.data.calendar import trading_days
from tests.features_gbm import NY_TZ

NAME = "pre_earnings_runup_winners"
DAYS = trading_days("2024-03-01", "2024-04-30")
QUARTER_END, AS_OF = date(2024, 3, 28), date(2024, 4, 22)  # 03-29 is Good Friday
# symbol -> (close, median dollar volume, ret_252d up to the quarter end, ret_252d after it, sessions to report on AS_OF)
SPEC: dict[str, tuple[float, float, float, float, float]] = {
    "WIN": (50.0, 5e6, 3.0, 0.1, 5.0),  # top at the quarter end, ordinary since
    "WIN2": (50.0, 5e6, 2.5, 0.1, 7.0),  # a winner, but its report is 7 sessions away
    "LATE": (50.0, 5e6, 0.2, 9.0, 5.0),  # a winner only after the quarter end
    "CHEAP": (4.0, 5e6, 5.0, 5.0, 5.0),  # under $5: not in the ranked population
    "THIN": (50.0, 5e5, 5.0, 5.0, 5.0),  # under $1M a day: not in the ranked population
    **{f"F{i}": (50.0, 5e6, 0.01 * i, 0.01 * i, 5.0) for i in range(8)},
}
TOP = {"top_fraction": 0.15}  # 11 ranked names: the top two (percentile above 0.85)


def panel() -> pd.DataFrame:
    frames = []
    for sym, (close, med_dv, ret_before, ret_after, to_exp) in SPEC.items():
        days = np.array(DAYS)
        f = pd.DataFrame({"symbol": sym, "ts": pd.DatetimeIndex(pd.to_datetime(DAYS)).tz_localize(NY_TZ), "open": close,
                          "high": close * 1.005, "low": close * 0.995, "close": close, "volume": med_dv / close})
        f["med_dv_63"], f["ret_252d"] = med_dv, np.where(days <= QUARTER_END, ret_before, ret_after)
        f["sessions_to_expected_earnings"] = np.where(days == AS_OF, to_exp, 40.0)
        f["days_since_earnings"] = 58.0
        frames.append(f)
    return pd.concat(frames, ignore_index=True)


def strat(**params):
    return registry.get("strategy", NAME)({**TOP, **params})


def symbols(sigs) -> list[str]:
    return [s.symbol for s in sigs]


def test_buys_quarter_end_winners_five_sessions_before_the_expected_report():
    p = panel()
    got = strat().signals(p, AS_OF)
    assert symbols(got) == ["WIN"]  # WIN2: not due; LATE: ranked on today's return it would be first
    s = got[0]
    assert s.entry == 50.0 and abs(s.stop - 42.5) < 1e-9 and s.target is None
    assert s.features["quarter_end_ret_252d"] == 3.0 and s.features["sessions_to_expected_earnings"] == 5.0
    assert symbols(strat(entry_sessions_to_report=7).signals(p, AS_OF)) == ["WIN2"]
    assert symbols(registry.get("strategy", NAME)().signals(p, AS_OF)) == ["WIN"]  # top 1% of 11 names: the best one
    assert strat().signals(p, date(2024, 4, 19)) == []  # nothing due


def test_silent_without_the_earnings_columns_or_the_quarter_end_bar():
    p = panel()
    for col in ("sessions_to_expected_earnings", "days_since_earnings"):
        assert strat().signals(p.drop(columns=col), AS_OF) == []
    assert strat().signals(p.loc[p["ts"].dt.date > QUARTER_END], AS_OF) == []


def test_exit_two_sessions_before_the_report_or_when_it_comes_early():
    s = strat()
    row = lambda to, since: pd.Series({"sessions_to_expected_earnings": to, "days_since_earnings": since})  # noqa: E731
    assert not s.should_exit(row(4.0, 60.0), 1) and not s.should_exit(row(3.0, 61.0), 2)
    assert s.should_exit(row(2.0, 62.0), 3)  # decided at this close, filled at the open of day -1
    assert s.should_exit(row(63.0, 0.0), 2) and s.should_exit(row(62.0, 1.0), 3)  # the report came while held
    assert not s.should_exit(row(np.nan, np.nan), 2) and not s.should_exit(pd.Series({"close": 1.0}), 2)
    assert not strat(exit_sessions_to_report=1).should_exit(row(2.0, 62.0), 3)
