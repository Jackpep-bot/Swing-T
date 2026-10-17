"""clenow_stocks_on_the_move_midcap (docs/proposals/swing-methods-2026-10/batch5/clenow_stocks_on_the_move_midcap.md)
on hand-built price paths: 500 large names above the mid-cap band, ten mid caps and SPY."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.data.calendar import trading_days
from swing_engine.strategies import clenow_stocks_on_the_move_midcap as mod
from tests.features_gbm import NY_TZ

NAME = "clenow_stocks_on_the_move_midcap"
DAYS = trading_days("2024-11-01", "2025-10-31")
TUE, WED, THU = date(2025, 10, 28), date(2025, 10, 29), date(2025, 10, 30)
N = len(DAYS)


def bars(symbol: str, close: np.ndarray, days: list[date] = DAYS, mcap: float = np.nan,
         gap_at: int | None = None) -> pd.DataFrame:
    """Bars that open at the previous close, except an overnight jump to the close on bar `gap_at`."""
    prev = np.r_[close[0], close[:-1]]
    open_ = prev.copy()
    if gap_at is not None:
        open_[gap_at] = close[gap_at]
    return pd.DataFrame({"symbol": symbol, "ts": pd.DatetimeIndex(pd.to_datetime(days)).tz_localize(NY_TZ), "open": open_,
                         "high": np.maximum(open_, close) * 1.001, "low": np.minimum(open_, close) * 0.999,
                         "close": close, "volume": 1e6, "mcap_pit": mcap, "gap_pct": open_ / prev - 1.0})


def make_panel(spy_drift: float = 0.0005) -> pd.DataFrame:
    t = np.arange(N)
    gap = 50.0 * np.exp(0.005 * t) * np.where(t >= N - 30, 1.2, 1.0)  # +20% overnight 30 sessions ago
    frames = [bars("SPY", 500.0 * np.exp(spy_drift * t)),
              bars("SMOOTH", 50.0 * np.exp(0.004 * t), mcap=5e9), bars("SLOWER", 50.0 * np.exp(0.002 * t), mcap=5e9 - 1),
              bars("GAPPER", gap, mcap=5e9 - 2, gap_at=N - 30)]
    frames += [bars(f"FLAT{i}", 50.0 + np.sin(t / (3.0 + i)), mcap=4e9 - i) for i in range(7)]
    frames += [bars(f"BIG{i:03d}", np.full(5, 100.0), DAYS[-5:], mcap=1e12 - i) for i in range(500)]  # ranks 1-500
    return pd.concat(frames, ignore_index=True)


def strat(**params):
    return registry.get("strategy", NAME)(params or None)


def row(panel: pd.DataFrame, symbol: str, day: date) -> pd.Series:
    return panel.loc[(panel["symbol"] == symbol) & (panel["ts"].dt.date == day)].iloc[0]


def test_rebalance_is_wednesday_or_the_next_session_after_a_holiday():
    assert mod.is_rebalance(WED, 2) and not mod.is_rebalance(TUE, 2) and not mod.is_rebalance(THU, 2)
    assert mod.is_rebalance(date(2024, 12, 26), 2) and not mod.is_rebalance(date(2024, 12, 27), 2)  # Christmas on Wednesday
    assert mod.is_rebalance(date(2024, 6, 20), 2)  # Juneteenth on Wednesday


def test_score_is_annualised_log_slope_times_r_squared():
    t = np.arange(120)
    closes = pd.concat([bars("EXP", 10.0 * np.exp(0.003 * t), DAYS[:120]), bars("FLAT", np.full(120, 10.0), DAYS[:120]),
                        bars("YOUNG", 10.0 * np.exp(0.003 * t[:60]), DAYS[:60])])[["symbol", "ts", "close"]]
    score = mod.trend_scores(closes.sample(frac=1.0, random_state=0), 90)
    assert score["EXP"] == pytest.approx(np.exp(0.003 * 252) - 1.0)  # a perfect fit: R-squared 1
    assert "YOUNG" not in score.index  # under 90 bars
    assert score.get("FLAT", 0.0) == pytest.approx(0.0, abs=1e-9)  # no trend: zero (or no R-squared at all)
    noisy = 10.0 * np.exp(0.003 * t + 0.05 * np.sin(t))
    y, x = np.log(noisy[-90:]), np.arange(90)
    slope, r2 = np.polyfit(x, y, 1)[0], np.corrcoef(x, y)[0, 1] ** 2
    got = mod.trend_scores(bars("N", noisy, DAYS[:120])[["symbol", "ts", "close"]], 90)["N"]
    assert got == pytest.approx((np.exp(slope * 252) - 1.0) * r2) and r2 < 0.9


def test_buys_the_top_fifth_that_is_above_the_average_and_gap_free():
    panel, s = make_panel(), strat()
    (sig,) = s.signals(panel, WED)  # top 20% of ten mid caps = GAPPER and SMOOTH; GAPPER has a 20% gap
    assert sig.symbol == "SMOOTH" and sig.target is None
    assert sig.features["clenow_score"] == pytest.approx(np.exp(0.004 * 252) - 1.0) and sig.features["score_rank"] == 0.9
    assert sig.entry - sig.stop == pytest.approx(10.0 * sig.features["atr_20"])  # 1% risk = equity x 0.001 / ATR shares
    assert s.signals(panel, TUE) == [] and s.signals(panel, THU) == []  # weekly, on the rebalance session
    assert s.signals(make_panel(spy_drift=-0.0005), WED) == []  # SPY below its 200-day: no new buys
    assert strat(max_gap=0.25).signals(panel, WED)[0].symbol == "GAPPER"  # highest score once the gap is allowed
    assert s.signals(panel.drop(columns="mcap_pit"), WED) == []  # no share join: silent
    assert s.engine_trail is False and s.params["max_hold_days"] == 10_000


def test_point_in_time():
    panel, s = make_panel(), strat()
    later = panel["ts"].dt.date > WED
    changed = panel.assign(close=panel["close"].where(~later, panel["close"] * 3.0))
    dump = lambda p: [x.model_dump_json() for x in s.signals(p, WED)]  # noqa: E731
    assert dump(changed) == dump(panel) == dump(panel.loc[~later]) != []


def test_weekly_exits():
    s = strat()
    panel = mod.c1.with_extras(s, make_panel())
    held = lambda sym, day=WED: s.should_exit(row(panel, sym, day), 10)  # noqa: E731
    assert held("SLOWER") is False  # no ranking measured yet (live): nothing is sold on rank
    assert held("GAPPER") is True  # the gap rule needs no ranking
    s.signals(panel, TUE)  # Tuesday's close: the ranking the Wednesday sells use
    assert held("SLOWER") is True and held("FLAT3") is True  # out of the top 20%
    assert held("SMOOTH") is False
    assert held("SLOWER", THU) is False and held("GAPPER", THU) is False  # only on the rebalance session
    below = row(panel, "SMOOTH", WED).copy()
    below["close"] = below["sma_100"] * 0.99
    assert s.should_exit(below, 10) is True  # closed below the 100-day average
