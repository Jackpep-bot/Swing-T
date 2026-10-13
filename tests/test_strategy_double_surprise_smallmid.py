"""double_surprise_smallmid (docs/proposals/swing-methods-2026-10/batch5/double_surprise_smallmid.md) on a hand-built
filing day: 500 large names above the SMALLMID band, 20 recent filers as the reference group, and today's filers."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.core.models import PositionContext
from swing_engine.data.calendar import trading_days
from tests.features_gbm import NY_TZ

NAME = "double_surprise_smallmid"
DAYS = trading_days("2025-11-03", "2025-11-07")
TODAY, NEXT = DAYS[2], DAYS[3]
SUE_CUT, HOLD_CUT = 15.2, 11.4  # 80th and 60th percentile of the reference values 0..19


def make_panel() -> pd.DataFrame:
    """Per symbol: (close, sue yesterday, sue today, revenue surprise, gross profit, sessions since filing today)."""
    specs = {f"R{i:02d}": (20.0, i, i, i, 0.3, 10) for i in range(20)}  # filed 10 sessions ago
    specs |= {
        "BOTH": (20.0, 1.0, 18.0, 17.0, 0.3, 0),  # new quarter, both surprises in the top fifth
        "EPSONLY": (20.0, 1.0, 18.0, 10.0, 0.3, 0),
        "AMEND": (20.0, 18.0, 18.0, 18.0, 0.3, 0),  # a 10-K/A: same sue as yesterday, not an event
        "CHEAP": (4.0, 1.0, 18.0, 18.0, 0.3, 0),  # under $5
        "BANK": (20.0, 1.0, 18.0, 18.0, np.nan, 0),  # no gross profit: the card's stand-in for a financial
        "STALE": (20.0, 19.0, 19.0, 19.0, 0.3, 70),  # filed long ago: neither an event nor in the reference group
    }
    ts = pd.DatetimeIndex(pd.to_datetime(DAYS)).tz_localize(NY_TZ)
    k = np.arange(len(DAYS)) - DAYS.index(TODAY)
    frames = [pd.DataFrame({"symbol": f"BIG{i:03d}", "ts": ts, "close": 100.0, "mcap_pit": 1e12 - i, "sue": 50.0,
                            "rev_surprise": 50.0, "gross_prof": 0.3, "days_since_filing": 5.0 + k}) for i in range(500)]
    for n, (sym, (close, before, now, rev, gp, since)) in enumerate(specs.items()):
        frames.append(pd.DataFrame({"symbol": sym, "ts": ts, "close": close, "mcap_pit": 5e9 - n,
                                    "sue": np.where(k < 0, before, now), "rev_surprise": float(rev), "gross_prof": gp,
                                    "days_since_filing": np.where((since == 0) & (k < 0), 60.0, since + np.maximum(k, 0))}))
    panel = pd.concat(frames, ignore_index=True)
    return panel.assign(open=panel["close"], high=panel["close"] * 1.01, low=panel["close"] * 0.99, volume=1e6,
                        med_dv_63=5e6, days_since_earnings=12.0)


def strat():
    return registry.get("strategy", NAME)()


def test_buys_only_a_new_filing_with_both_surprises_in_the_top_quintile():
    panel, s = make_panel(), strat()
    (sig,) = s.signals(panel, TODAY)
    assert sig.symbol == "BOTH" and sig.entry == 20.0 and sig.stop == pytest.approx(15.0) and sig.target is None
    assert sig.features["sue_cut"] == pytest.approx(SUE_CUT) and sig.features["rev_cut"] == pytest.approx(SUE_CUT)
    assert sig.features["reference_names"] == 20 and sig.features["days_since_earnings"] == 12.0
    assert s.signals(panel, NEXT) == []  # the filing day only
    assert s.params["max_hold_days"] == 63 and s.engine_trail is False


def test_needs_a_quintile_of_recent_filers_and_the_join_columns():
    panel, s = make_panel(), strat()
    few = panel.loc[~panel["symbol"].str.startswith("R") | panel["symbol"].isin(["R16", "R17", "R18", "R19"])]
    assert s.signals(few, TODAY) == []  # four reference names: no quintile
    for col in ("sue", "rev_surprise", "gross_prof", "days_since_filing", "days_since_earnings", "mcap_pit"):
        assert s.signals(panel.drop(columns=col), TODAY) == []


def test_point_in_time():
    panel, s = make_panel(), strat()
    later = panel["ts"].dt.date > TODAY
    changed = panel.assign(sue=panel["sue"].where(~later, 99.0), close=panel["close"].where(~later, 1.0))
    dump = lambda p: [x.model_dump_json() for x in s.signals(p, TODAY)]  # noqa: E731
    assert dump(changed) == dump(panel) == dump(panel.loc[~later]) != []


def test_exits_at_the_next_filing_when_both_surprises_left_the_top_two_quintiles():
    panel, s = make_panel(), strat()
    held = PositionContext(entry_price=20.0, stop=15.0, bars_held=40, entry_features={"sue": 18.0})
    ts = pd.Timestamp(NEXT).tz_localize(NY_TZ)
    row = lambda sue, rev, filed=0.0, at=ts: pd.Series({"ts": at, "sue": sue, "rev_surprise": rev,  # noqa: E731
                                                         "days_since_filing": filed})
    assert s.should_exit(row(5.0, 5.0), 40, held) is False  # no percentiles measured yet (live)
    s.signals(panel, TODAY)  # the close before: hold cut = 60th percentile of the reference group
    assert s.should_exit(row(5.0, 5.0), 40, held) is True
    assert s.should_exit(row(HOLD_CUT - 0.1, HOLD_CUT - 0.1), 40, held) is True
    assert s.should_exit(row(5.0, HOLD_CUT + 0.1), 40, held) is False  # one surprise still in the top two quintiles
    assert s.should_exit(row(5.0, 5.0, filed=3.0), 40, held) is False  # not a filing session
    assert s.should_exit(row(18.0, 5.0), 40, held) is False  # the entry quarter again (amendment)
    assert s.should_exit(row(5.0, np.nan), 40, held) is False
    assert s.should_exit(row(5.0, 5.0), 40) is False and s.should_exit(row(5.0, 5.0), 40, PositionContext()) is False
    stale = pd.Timestamp(DAYS[4]).tz_localize(NY_TZ)  # the percentiles are two closes old
    assert s.should_exit(row(5.0, 5.0, at=stale), 40, held) is False
