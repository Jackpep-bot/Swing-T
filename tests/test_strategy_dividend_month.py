"""dividend_month_premium (docs/preregistration/2026-10-13-dividend-month.md): picks on a month's last session only,
filters, the 50-name cap by liquidity, the month-end exit. Point-in-time is also covered by tests/test_strategies_all.py."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from swing_engine.core import registry
from swing_engine.data.calendar import trading_days
from tests.features_gbm import NY_TZ

NAME = "dividend_month_premium"
DAYS = trading_days("2023-09-01", "2024-01-31")


def panel(spec: dict[str, tuple[float, float, float]], flag_day: date = date(2024, 1, 31)) -> pd.DataFrame:
    """symbol -> (close, daily volume, div_season on ``flag_day``); flat prices with a 1% daily range. Every symbol
    but ``ETF`` has a market cap from filed share counts."""
    frames = []
    for sym, (close, volume, season) in spec.items():
        f = pd.DataFrame({"symbol": sym, "ts": pd.DatetimeIndex(pd.to_datetime(DAYS)).tz_localize(NY_TZ), "open": close,
                          "high": close * 1.005, "low": close * 0.995, "close": close, "volume": volume})
        f["div_season"] = np.where(f["ts"].dt.date == flag_day, season, np.nan)
        f["mcap_pit"] = np.nan if sym == "ETF" else 1e10
        frames.append(f)
    return pd.concat(frames, ignore_index=True)


def strat(**params):
    return registry.get("strategy", NAME)(params or None)


def test_buys_the_most_liquid_predicted_payers_on_the_months_last_session():
    p = panel({"BIG": (100.0, 5e6, 1.0), "MID": (50.0, 1e6, 1.0), "THIN": (50.0, 1e5, 1.0), "PENNY": (4.0, 5e7, 1.0),
               "NOTDUE": (100.0, 9e6, 0.0), "ETF": (400.0, 9e7, 1.0)})
    got = strat().signals(p, date(2024, 1, 31))
    # THIN: $5M a day; PENNY: under $5; NOTDUE: not predicted; ETF: no filed share count
    assert [s.symbol for s in got] == ["BIG", "MID"]
    assert got[0].target is None and got[0].stop < got[0].entry == 100.0 and got[0].score > got[1].score
    assert [s.symbol for s in strat(max_names=1).signals(p, date(2024, 1, 31))] == ["BIG"]
    assert strat().signals(p, date(2024, 1, 30)) == []  # not a month end
    assert strat().signals(p.drop(columns="div_season"), date(2024, 1, 31)) == []  # no dividend join: silent


def test_sold_at_the_next_month_end_unless_predicted_again():
    s = strat()
    row = lambda month_end, season: pd.Series({"month_end": month_end, "div_season": season})  # noqa: E731
    assert not s.should_exit(row(0.0, np.nan), 5)
    assert s.should_exit(row(1.0, 0.0), 21) and s.should_exit(row(1.0, np.nan), 21)
    assert not s.should_exit(row(1.0, 1.0), 21)
