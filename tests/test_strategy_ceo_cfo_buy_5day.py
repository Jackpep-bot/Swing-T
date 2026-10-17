"""ceo_cfo_buy_5day: fires on the session the CEO/CFO purchase becomes visible, the $25k floor, the SMALLMID filter,
the earnings skip and the stop. The exit is the engine's time stop (`max_hold_days` 5). Point-in-time is also covered
by tests/test_strategies_all.py."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from swing_engine.core import registry
from swing_engine.data.calendar import trading_days
from tests.features_gbm import NY_TZ

NAME = "ceo_cfo_buy_5day"
DAYS = trading_days("2024-03-01", "2024-03-15")
FLAG_DAY = date(2024, 3, 12)
# symbol -> (close, mcap, median dollar volume, purchase value visible on FLAG_DAY, sessions to expected earnings)
SPEC: dict[str, tuple[float, float, float, float, float]] = {
    "MEGA": (50.0, 9e9, 5e6, 90_000.0, 30.0),  # rank 1: above the SMALLMID band (ranks 2-8 here)
    "BUY": (50.0, 8e8, 5e6, 30_000.0, 30.0),
    "BIGBUY": (20.0, 7e8, 5e6, 400_000.0, np.nan),  # no expected report date: not skipped
    "SMALLBUY": (50.0, 6e8, 5e6, 20_000.0, 30.0),  # under $25k
    "EARNINGS": (50.0, 5e8, 5e6, 90_000.0, 5.0),  # report expected within 5 sessions
    "THIN": (50.0, 4e8, 5e5, 90_000.0, 30.0),  # median dollar volume under $1M
    "PENNY": (2.0, 3e8, 5e6, 90_000.0, 30.0),  # under $3
    "NOBUY": (50.0, 2e8, 5e6, 0.0, 30.0),
}
SMALL = {"mcap_rank_first": 2, "mcap_rank_last": 8}


def panel() -> pd.DataFrame:
    frames = []
    for sym, (close, mcap, med_dv, value, to_exp) in SPEC.items():
        f = pd.DataFrame({"symbol": sym, "ts": pd.DatetimeIndex(pd.to_datetime(DAYS)).tz_localize(NY_TZ), "open": close,
                          "high": close * 1.005, "low": close * 0.995, "close": close, "volume": med_dv / close})
        f["mcap_pit"], f["med_dv_63"], f["sessions_to_expected_earnings"] = mcap, med_dv, to_exp
        f["ceo_cfo_buy_value"] = np.where(f["ts"].dt.date == FLAG_DAY, value, 0.0)
        f["ceo_buy_value"], f["cfo_buy_value"] = f["ceo_cfo_buy_value"], 0.0
        frames.append(f)
    return pd.concat(frames, ignore_index=True)


def strat(**params):
    return registry.get("strategy", NAME)({**SMALL, **params})


def test_buys_on_the_session_the_purchase_becomes_visible():
    p = panel()
    got = {s.symbol: s for s in strat().signals(p, FLAG_DAY)}
    assert set(got) == {"BUY", "BIGBUY"}
    s = got["BUY"]
    assert s.entry == 50.0 and abs(s.stop - 42.5) < 1e-9 and s.target is None
    assert s.features["ceo_cfo_buy_value"] == 30_000.0 and s.features["ceo_buy_value"] == 30_000.0
    assert got["BIGBUY"].score > s.score  # the larger purchase ranks first when the book is full
    assert strat().signals(p, date(2024, 3, 11)) == [] and strat().signals(p, date(2024, 3, 13)) == []  # one session
    assert {s.symbol for s in strat(min_buy_value=10_000.0).signals(p, FLAG_DAY)} == {"BUY", "BIGBUY", "SMALLBUY"}
    assert {s.symbol for s in strat(earnings_skip_sessions=4).signals(p, FLAG_DAY)} == {"BUY", "BIGBUY", "EARNINGS"}
    assert registry.get("strategy", NAME)().params["max_hold_days"] == 5


def test_silent_without_a_needed_column():
    p = panel()
    for col in ("ceo_cfo_buy_value", "sessions_to_expected_earnings", "mcap_pit"):
        assert strat().signals(p.drop(columns=col), FLAG_DAY) == []
