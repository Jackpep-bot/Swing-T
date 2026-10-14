"""merger_target_spread_capture (docs/proposals/swing-methods-2026-10/batch7/merger_target_spread_capture.md) on a
hand-built filing day: one clean deal and one name for each thing the card excludes."""
from __future__ import annotations

import pandas as pd
import pytest

from swing_engine.data.calendar import trading_days
from swing_engine.strategies import merger_target_spread_capture as mod
from tests.features_gbm import NY_TZ

DAYS = trading_days("2025-09-02", "2025-09-12")
SIGNAL = DAYS[-3]
CASES = {"DEAL": {}, "NOEVENT": {"deal_event": 0.0}, "SMALL": {"mcap_pit": 2e8}, "THIN": {"med_dv_63": 4e6},
         "SPIKE": {"roc_20": 35.0}}


def make_panel() -> pd.DataFrame:
    ts = pd.DatetimeIndex(pd.to_datetime(DAYS)).tz_localize(NY_TZ)
    frames = []
    for sym, case in CASES.items():
        base = {"deal_event": [float(d == SIGNAL) for d in DAYS], "mcap_pit": 1e9, "med_dv_63": 1e7, "roc_20": 12.0}
        frames.append(pd.DataFrame({"symbol": sym, "ts": ts, "open": 40.0, "high": 40.2, "low": 39.8, "close": 40.0,
                                    "volume": 1e6, **base, **case}))
    return pd.concat(frames, ignore_index=True)


def test_buys_the_clean_deal_on_its_filing_session_only():
    panel, s = make_panel(), mod.MergerTargetSpreadCapture()
    sigs = s.signals(panel, SIGNAL)
    assert [x.symbol for x in sigs] == ["DEAL"]
    assert sigs[0].stop == pytest.approx(40.0 * 0.85) and sigs[0].target is None
    assert s.signals(panel, DAYS[-2]) == [] and s.signals(panel, DAYS[-4]) == []
    assert s.params["max_hold_days"] == 180 and s.engine_trail is False


def test_point_in_time_and_silence_without_the_join():
    panel, s = make_panel(), mod.MergerTargetSpreadCapture()
    later = panel["ts"].dt.date > SIGNAL
    shocked = panel.assign(close=panel["close"].where(~later, 80.0), deal_event=panel["deal_event"].where(~later, 1.0))
    dump = lambda p: [x.model_dump_json() for x in s.signals(p, SIGNAL)]  # noqa: E731
    assert dump(shocked) == dump(panel) == dump(panel.loc[~later]) != []
    for col in ("deal_event", "mcap_pit"):
        assert s.signals(panel.drop(columns=col), SIGNAL) == []
