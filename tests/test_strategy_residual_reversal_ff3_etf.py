"""residual_reversal_ff3_etf (docs/proposals/swing-methods-2026-10/batch6/residual_reversal_ff3_etf.md): the score
against a direct regression, and the month-end book on a hand-built panel."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing_engine.data.calendar import trading_days
from swing_engine.strategies import residual_reversal_ff3_etf as mod
from tests.features_gbm import NY_TZ

DAYS = trading_days("2023-04-03", "2025-11-04")  # month end 2025-10-31, then two sessions of November
MONTH_END, BEFORE = date(2025, 10, 31), date(2025, 10, 30)
K = len(DAYS)
END = DAYS.index(MONTH_END)
PARAMS = {"buy_count": 2, "hold_count": 4, "universe_top": 8}


def make_panel(n: int = 10) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    f = rng.normal(0.0, 0.01, size=(K, 3))
    ts = pd.DatetimeIndex(pd.to_datetime(DAYS)).tz_localize(NY_TZ)
    frames = []
    for i in range(n):
        beta = np.array([1.0 + 0.1 * i, 0.3, -0.2])
        r = f @ beta + rng.normal(0.0, 0.004, K)
        r[END - 20:END + 1] += -0.004 * (i - 4)  # names 5.. drift down over the last 21 sessions, 0..3 drift up
        close = 50.0 * np.cumprod(1.0 + r)
        frames.append(pd.DataFrame({"symbol": f"S{i}", "ts": ts, "open": close, "high": close * 1.01, "low": close * 0.99,
                                    "close": close, "volume": 1e6, "mcap_pit": 1e10 - i, "days_since_earnings": 40.0,
                                    "etf_mkt": f[:, 0], "etf_smb": f[:, 1], "etf_hml": f[:, 2]}))
    return pd.concat(frames, ignore_index=True)


def strat(**over):
    return mod.ResidualReversalFf3Etf({**PARAMS, **over})


def test_score_matches_a_direct_regression_and_needs_complete_inputs():
    rng = np.random.default_rng(1)
    f = rng.normal(0.0, 0.01, size=(900, 3))
    r = 0.0002 + f @ np.array([1.2, 0.5, -0.3]) + rng.normal(0.0, 0.005, 900)
    r[-21:] -= 0.002
    close = 20.0 * np.cumprod(1.0 + r)
    got = mod.residual_score(close, f, fit=756, gap=22, form=21, min_fit=500)
    ret, x = close[1:] / close[:-1] - 1.0, np.column_stack([np.ones(899), f[1:]])
    xf, yf = x[899 - 22 - 756:899 - 22], ret[899 - 22 - 756:899 - 22]
    beta = np.linalg.solve(xf.T @ xf, xf.T @ yf)
    want = (ret[-21:] - x[-21:] @ beta).sum() / np.std(yf - xf @ beta)
    assert got == pytest.approx(want) and got < -5.0  # 21 x -0.2% against 0.5% daily noise
    hole = close.copy()
    hole[-5] = np.nan
    assert np.isnan(mod.residual_score(hole, f, 756, 22, 21, 500))  # a gap inside the last 21 sessions
    assert np.isnan(mod.residual_score(close[-400:], f[-400:], 756, 22, 21, 500))  # under 500 fit sessions
    assert np.isfinite(mod.residual_score(close[-600:], f[-600:], 756, 22, 21, 500))  # a short history that has 500


def test_buys_the_lowest_residuals_of_the_largest_names_at_month_end_only():
    panel, s = make_panel(), strat()
    sigs = sorted(s.signals(panel, MONTH_END), key=lambda x: -x.score)
    assert [x.symbol for x in sigs] == ["S7", "S6"]  # S8 and S9 fell more but are outside the 8 largest
    top = sigs[0]
    assert top.target is None and top.stop == pytest.approx(top.entry * 0.80) and top.features["rank"] == 1
    assert s.signals(panel, BEFORE) == [] and s.signals(panel, DAYS[END + 1]) == []
    assert s.engine_trail is False and s.warmup_calendar_days == 1200


def test_exclusions_point_in_time_and_silence_without_the_join():
    panel, s = make_panel(), strat()
    earn = panel.assign(days_since_earnings=panel["days_since_earnings"].where(panel["symbol"] != "S7", 20.0))
    assert [x.symbol for x in sorted(s.signals(earn, MONTH_END), key=lambda x: -x.score)] == ["S6", "S5"]
    split = panel.assign(days_since_reverse_split=np.where(panel["symbol"] == "S7", 100.0, np.nan))
    assert [x.symbol for x in s.signals(split, MONTH_END)] == ["S6"]  # an avoided name's slot is not refilled
    later = panel["ts"].dt.date > MONTH_END
    shocked = panel.assign(close=panel["close"].where(~later, panel["close"] * 3.0),
                           etf_mkt=panel["etf_mkt"].where(~later, 0.5))
    dump = lambda p: [x.model_dump_json() for x in s.signals(p, MONTH_END)]  # noqa: E731
    assert dump(shocked) == dump(panel) == dump(panel.loc[~later]) != []
    for col in ("mcap_pit", "days_since_earnings", "etf_hml"):
        assert s.signals(panel.drop(columns=col), MONTH_END) == []


def test_sells_at_month_end_outside_the_hold_zone_of_the_previous_close():
    panel, s = make_panel(), strat()
    row = lambda sym, day: panel.loc[(panel["symbol"] == sym) & (panel["ts"].dt.date == day)].iloc[0]  # noqa: E731
    held = lambda sym, day=MONTH_END: s.should_exit(row(sym, day), 21)  # noqa: E731
    assert held("S0") is False  # no zone measured yet (live): nothing is sold on rank
    assert s.signals(panel, BEFORE) == []  # the close before the month end only measures the zone
    assert held("S0") is True and held("S9") is True  # a winner, and a name outside the 8 largest
    assert held("S7") is False and held("S4") is False  # the four lowest scores: S7, S6, S5, S4
    assert held("S0", DAYS[END + 1]) is False  # only on a month's last session
    s.signals(panel, DAYS[END - 21])  # not a month end or the session before one: the zone is not refreshed
    assert held("S0") is True
