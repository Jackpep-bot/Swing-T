"""piotroski_fscore8_small_value (docs/proposals/swing-methods-2026-10/batch5/piotroski_fscore8_small_value.md) on a
hand-built month end: 500 large names above the SMALLMID band and 20 small/mid caps ordered by book-to-market."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.data.calendar import trading_days
from tests.features_gbm import NY_TZ

NAME = "piotroski_fscore8_small_value"
DAYS = trading_days("2025-10-27", "2025-11-04")  # month end 2025-10-31
MONTH_END, EVE = date(2025, 10, 31), date(2025, 10, 30)
SCORES = {"V19": 8.0, "V18": 7.0, "V17": 6.0, "V16": np.nan, "V15": 7.0, "V14": 8.0, "V10": 8.0}


def make_panel() -> pd.DataFrame:
    specs = {f"BIG{i:03d}": {"mcap_pit": 1e12 - i, "b5_book_to_market": 9.0, "b5_fscore": 8.0} for i in range(500)}
    for i in range(20):  # book-to-market 0.1 .. 2.0: the top 30% is V14..V19
        specs[f"V{i:02d}"] = {"mcap_pit": 5e9 - i, "b5_book_to_market": 0.1 * (i + 1), "b5_fscore": SCORES.get(f"V{i:02d}", 3.0)}
    specs["THIN"] = {"mcap_pit": 4e9, "b5_book_to_market": 5.0, "b5_fscore": 8.0, "med_dv_63": 5e5}  # under the $1M floor
    ts = pd.DatetimeIndex(pd.to_datetime(DAYS)).tz_localize(NY_TZ)
    frames = [pd.DataFrame({"symbol": s, "ts": ts, "open": 40.0, "high": 40.5, "low": 39.5, "close": 40.0, "volume": 1e5,
                            "month_end": [float(d == MONTH_END) for d in DAYS], "med_dv_63": 5e6, **cols})
              for s, cols in specs.items()]
    return pd.concat(frames, ignore_index=True)


def strat():
    return registry.get("strategy", NAME)()


def test_buys_cheap_names_scoring_seven_or_eight_at_month_end():
    panel, s = make_panel(), strat()
    sigs = sorted(s.signals(panel, MONTH_END), key=lambda x: -x.score)
    assert [x.symbol for x in sigs] == ["V19", "V14", "V18", "V15"]  # score first, then book-to-market
    top = sigs[0]
    assert top.entry == 40.0 and top.stop == pytest.approx(28.0) and top.target is None
    assert top.features["b5_fscore"] == 8.0 and top.features["bm_rank"] == 1.0
    assert s.signals(panel, EVE) == [] and s.signals(panel, DAYS[5]) == []  # month-end check only
    assert s.engine_trail is False


def test_point_in_time_and_silent_without_the_join_columns():
    panel, s = make_panel(), strat()
    later = panel["ts"].dt.date > MONTH_END
    changed = panel.assign(b5_fscore=panel["b5_fscore"].where(~later, 0.0))
    dump = lambda p: [x.model_dump_json() for x in s.signals(p, MONTH_END)]  # noqa: E731
    assert dump(changed) == dump(panel) == dump(panel.loc[~later]) != []
    for col in ("b5_fscore", "b5_book_to_market", "mcap_pit"):
        assert s.signals(panel.drop(columns=col), MONTH_END) == []


def test_sells_below_six_or_when_the_hold_is_up_and_it_would_not_be_bought_again():
    panel, s = make_panel(), strat()
    ts = pd.Timestamp(MONTH_END).tz_localize(NY_TZ)
    row = lambda score, sym="V19", flag=1.0: pd.Series({"symbol": sym, "ts": ts, "month_end": flag,  # noqa: E731
                                                         "b5_fscore": score})
    assert s.should_exit(row(5.0), 21) is True  # the score has fallen below 6
    assert s.should_exit(row(5.0, flag=0.0), 21) is False  # judged at month-end checks only
    assert s.should_exit(row(6.0), 42) is False and s.should_exit(row(np.nan), 105) is False
    assert s.should_exit(row(8.0), 126) is True  # hold is up and no cheap group is known (live): sold on time
    s.signals(panel, EVE)  # the close before the check: who is in the top 30% by book-to-market
    for held in (124, 126, 128, 252):  # the sixth and twelfth checks
        assert s.should_exit(row(8.0), held) is False  # V19 would be bought again: kept, no trade
        assert s.should_exit(row(6.0), held) is True  # not a buy any more
        assert s.should_exit(row(8.0, sym="V10"), held) is True  # no longer cheap
    assert s.should_exit(row(6.0), 105) is False and s.should_exit(row(6.0), 147) is False  # between expiry checks
    s.signals(panel, DAYS[2])  # a cheap group from two sessions back is stale
    assert s.should_exit(row(8.0), 126) is True
