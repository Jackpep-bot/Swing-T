"""shareholder_yield_smallmid (docs/proposals/swing-methods-2026-10/batch5/shareholder_yield_smallmid.md) on a
hand-built month end: 500 large names above the SMALLMID band, 20 eligible names and the cases the card excludes."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.core.config import ExecutionConfig, RiskConfig, Settings
from swing_engine.data.calendar import trading_days
from swing_engine.data.store import Store
from swing_engine.research import replay as replay_mod
from tests.features_gbm import NY_TZ

NAME = "shareholder_yield_smallmid"
DAYS = trading_days("2025-10-27", "2025-11-04")  # month end 2025-10-31, then two sessions of November
MONTH_END = date(2025, 10, 31)
BASE = {"b5_div_yield": 0.0, "b5_buyback_yield": 0.0, "b5_ocf_ttm": 1.0, "atr_63": 1.0, "med_dv_63": 5e6}


def make_panel() -> pd.DataFrame:
    specs = {f"BIG{i:03d}": {"mcap_pit": 1e12 - i, "b5_div_yield": 0.24} for i in range(500)}  # ranks 1-500
    for i in range(20):  # yields 1% .. 20%, half dividends and half buybacks
        y = 0.01 * (i + 1)
        specs[f"S{i:02d}"] = {"mcap_pit": 5e9 - i, "b5_div_yield": y / 2, "b5_buyback_yield": y / 2}
    specs["BURN"] = {"mcap_pit": 4e9, "b5_div_yield": 0.22, "b5_ocf_ttm": -1.0}  # paid from debt, not cash flow
    specs["ERR"] = {"mcap_pit": 4e9 - 1, "b5_div_yield": 0.30}  # above the 25% data-error guard
    specs["NOBUY"] = {"mcap_pit": 4e9 - 2, "b5_div_yield": 0.22, "b5_buyback_yield": np.nan}  # an input missing
    specs["THIN"] = {"mcap_pit": 4e9 - 3, "b5_div_yield": 0.22, "med_dv_63": 5e5}  # under the $1M floor
    ts = pd.DatetimeIndex(pd.to_datetime(DAYS)).tz_localize(NY_TZ)
    frames = [pd.DataFrame({"symbol": s, "ts": ts, "open": 50.0, "high": 50.5, "low": 49.5, "close": 50.0, "volume": 1e5,
                            "month_end": [float(d == MONTH_END) for d in DAYS], **BASE, **cols}) for s, cols in specs.items()]
    return pd.concat(frames, ignore_index=True)


def strat():
    return registry.get("strategy", NAME)()


def row(panel: pd.DataFrame, symbol: str, day: date) -> pd.Series:
    return panel.loc[(panel["symbol"] == symbol) & (panel["ts"].dt.date == day)].iloc[0]


def test_buys_the_top_decile_of_eligible_smallmid_names_at_month_end():
    panel, s = make_panel(), strat()
    sigs = sorted(s.signals(panel, MONTH_END), key=lambda x: -x.score)
    assert [x.symbol for x in sigs] == ["S19", "S18"]  # ranks 1.00 and 0.95 of the 20 eligible names
    top = sigs[0]
    assert top.entry == 50.0 and top.stop == pytest.approx(50.0 - 3.0 * 1.0) and top.target is None
    assert top.features["shareholder_yield"] == pytest.approx(0.20) and top.features["b5_div_yield"] == pytest.approx(0.10)
    assert s.signals(panel, DAYS[3]) == [] and s.signals(panel, DAYS[5]) == []  # not a month's last session
    assert s.engine_trail is False and s.params["max_hold_days"] == 10_000


def test_point_in_time_and_silent_without_the_join_columns():
    panel, s = make_panel(), strat()
    later = panel["ts"].dt.date > MONTH_END
    shuffled = panel.assign(b5_div_yield=panel["b5_div_yield"].where(~later, 0.2 - panel["b5_div_yield"]))
    dump = lambda p: [x.model_dump_json() for x in s.signals(p, MONTH_END)]  # noqa: E731
    assert dump(shuffled) == dump(panel) == dump(panel.loc[~later]) != []
    for col in ("b5_div_yield", "b5_buyback_yield", "b5_ocf_ttm", "mcap_pit"):
        assert s.signals(panel.drop(columns=col), MONTH_END) == []


def test_sells_at_month_end_outside_the_hold_zone_of_the_previous_close():
    panel, s = make_panel(), strat()
    held = lambda sym, day=MONTH_END: s.should_exit(row(panel, sym, day), 21)  # noqa: E731
    assert held("S10") is False  # no zone measured yet (live): nothing is sold on rank
    s.signals(panel, DAYS[3])  # the close before the month end
    assert held("S15") is True and held("S10") is True and held("BURN") is True  # rank 0.80 and below, or ineligible
    assert held("S16") is False and held("S19") is False  # hold zone: ranks above 0.80
    assert held("S10", DAYS[5]) is False  # only on a month's last session
    indexed = row(panel, "S15", MONTH_END)
    assert s.should_exit(indexed.drop(["ts", "symbol"]).rename((indexed["ts"], "S15")), 21) is True  # run_backtest rows
    s.signals(panel, DAYS[2])  # a zone from two sessions back is stale
    assert held("S10") is False


def test_replay_sells_the_name_that_left_the_hold_zone_and_refills_its_slot(monkeypatch):
    """The engine loop end to end: `should_exit` runs at the month-end close before `signals` sees it, and reads
    the zone `signals` measured the close before."""
    monkeypatch.setattr(replay_mod, "_load_router", lambda: None)
    monkeypatch.setattr(replay_mod, "_load_breadth", lambda: None)
    days = trading_days("2025-09-22", "2025-11-05")
    ends = {date(2025, 9, 30), MONTH_END}
    late = np.array([d >= date(2025, 10, 15) for d in days])  # S18's yield collapses in mid October
    ts = pd.DatetimeIndex(pd.to_datetime(days)).tz_localize(NY_TZ)
    frames = [pd.DataFrame({"symbol": f"BIG{i:03d}", "ts": ts, "mcap_pit": 1e12 - i, "y": 0.24}) for i in range(500)]
    frames += [pd.DataFrame({"symbol": f"S{i:02d}", "ts": ts, "mcap_pit": 5e9 - i,
                             "y": np.where(late & (i == 18), 0.001, 0.01 * (i + 1))}) for i in range(20)]
    p = pd.concat(frames, ignore_index=True)
    p = p.assign(open=50.0, high=50.5, low=49.5, close=50.0, volume=1e6, vwap=50.0, adj_close=50.0,
                 b5_div_yield=p["y"] / 2, b5_buyback_yield=p["y"] / 2, b5_ocf_ttm=1.0, atr_63=1.0, med_dv_63=5e6,
                 month_end=[float(t.date() in ends) for t in p["ts"]]).drop(columns="y")
    settings = Settings(risk=RiskConfig(max_open_positions=50, max_position_pct=2.0, risk_per_trade_pct=1.0),
                        execution=ExecutionConfig(max_new_orders_per_day=50, reuse_exiting_slots=True),
                        strategies={NAME: {"enabled": True, "min_reward_risk": 0.0}})
    store = Store()
    try:
        res = replay_mod.run_replay(settings, store, days[5], days[-1], strategies=[strat()], use_router=False, panel=p,
                                    record_shadow=False, trials_path=None, screen_universe=False)
    finally:
        store.close()
    trades = {t.symbol: (t.entry_ts.date(), t.exit_ts.date(), str(t.exit_reason)) for t in res.trades.itertuples()}
    assert trades == {"S18": (date(2025, 10, 1), date(2025, 11, 3), "rule"),  # sold at the open after the month end
                      "S19": (date(2025, 10, 1), days[-1], "end"),  # still in the hold zone
                      "S17": (date(2025, 11, 3), days[-1], "end")}  # the new second-best name takes the slot
