"""The pre-registered group of two (docs/preregistration/2026-10-10-two-picks.md): high_volume_return_premium and
momentum_volume_early_stage. Point-in-time is also covered by tests/test_strategies_all.py."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.core.config import load_settings
from swing_engine.data.calendar import trading_days
from swing_engine.features.extra import ensure_extra
from swing_engine.features.panel import build_panel
from swing_engine.risk.sizing import strategy_min_reward_risk
from tests.features_gbm import NY_TZ, gbm_bars

HVRP, EARLY = "high_volume_return_premium", "momentum_volume_early_stage"


def strat(name: str, **params):
    return registry.get("strategy", name)(params or None)


# ----------------------------------------------------------------------------------------------- HVRP
def hvrp_panel(n_bars: int = 320, volume_mult: float = 10.0, last_ret: float | None = None, scale: float = 1.0):
    """One GBM name near $20; the last bar gets `volume_mult` x its largest volume and the median of its last 49
    daily returns (a normal-return day) unless `last_ret` is given."""
    bars = gbm_bars(["AAA"], n_bars=n_bars, seed=1, s0=20.0, mu=0.10, sigma=0.30)
    px = ["open", "high", "low", "close", "vwap", "adj_close"]
    bars[px] *= scale
    i, prev = bars.index[-1], float(bars["close"].iloc[-2])
    rets = bars["close"].pct_change().iloc[-50:-1]
    close = prev * (1.0 + (float(rets.median()) if last_ret is None else last_ret))
    bars.loc[i, ["open", "low"]] = min(prev, close) * 0.999
    bars.loc[i, ["high"]] = max(prev, close) * 1.001
    bars.loc[i, ["close", "vwap", "adj_close"]] = close
    bars.loc[i, "volume"] = float(bars["volume"].iloc[:-1].max()) * volume_mult
    panel = build_panel(bars)
    return panel, panel["ts"].iloc[-1].date()


def test_hvrp_fires_on_high_volume_normal_return_day():
    s = strat(HVRP)
    panel, day = hvrp_panel()
    (sig,) = s.signals(panel, day)
    row = panel.iloc[-1]
    assert sig.entry == pytest.approx(row["close"]) and sig.target is None
    assert sig.stop == pytest.approx(row["close"] - 3.0 * row["atr_14"])
    assert sig.features["dollar_vol_rank"] == 50.0 and 16 <= sig.features["ret_rank"] <= 35
    assert s.params["max_hold_days"] == 20 and s.engine_trail is False
    assert s.signals(panel, panel["ts"].iloc[-2].date()) == []  # the day before: ordinary volume


def test_hvrp_no_fire():
    s = strat(HVRP)
    assert s.signals(*hvrp_panel(volume_mult=0.1)) == []  # an ordinary volume day (not in the top 5 of 50)
    assert s.signals(*hvrp_panel(last_ret=0.10)) == []  # extreme return day (rank 50 of 50)
    assert s.signals(*hvrp_panel(last_ret=-0.10)) == []  # extreme negative return (rank 1 of 50)
    assert s.signals(*hvrp_panel(scale=0.2)) == []  # closes below $5 in the 50 sessions
    assert s.signals(*hvrp_panel(n_bars=200)) == []  # < 252 bars of history
    panel, day = hvrp_panel(n_bars=200)
    assert len(s.signals(panel.assign(pre_panel_bars=100.0), day)) == 1  # older store bars count as history


def test_hvrp_volume_rank_is_dollar_volume_within_own_50_sessions():
    panel, _ = hvrp_panel()
    out = ensure_extra(panel, ["pctile_50_of_dollar_vol"])
    dv = (panel["close"] * panel["volume"]).to_numpy()
    assert out["pctile_50_of_dollar_vol"].iloc[-1] * 50 == pytest.approx((dv[-50:] <= dv[-1]).sum())
    assert out["pctile_50_of_dollar_vol"].iloc[:49].isna().all()


# ----------------------------------------------------------------------------------------------- early-stage momentum
N_SYM, N_BARS = 20, 700


def early_panel(last_day: str = "2025-10-31") -> tuple[pd.DataFrame, list]:
    """20 names, 700 NYSE sessions ending on a month end; S19 and S18 are the two top-decile winners. Turnover is
    lowest for S19 and S00..S04 (bottom tercile = 6 of 20) and highest for S18."""
    days = trading_days("2020-01-01", last_day)[-N_BARS:]
    ts = pd.DatetimeIndex(pd.to_datetime(days)).tz_localize(NY_TZ)
    frames = []
    for i in range(N_SYM):
        close = 20.0 * np.exp((i - 10) * 0.0005 * np.arange(N_BARS))
        prev = np.r_[close[0], close[:-1]]
        turnover = {19: 0.001, 18: 0.05}.get(i, 0.002 + 0.001 * i)
        frames.append(pd.DataFrame({"symbol": f"S{i:02d}", "ts": ts, "open": prev, "high": np.maximum(prev, close) * 1.01,
                                    "low": np.minimum(prev, close) * 0.99, "close": close, "volume": 1e6,
                                    "turnover": turnover}))
    return pd.concat(frames, ignore_index=True), days


def test_early_stage_buys_low_turnover_winner_at_month_end_only():
    s = strat(EARLY)
    panel, days = early_panel()
    (sig,) = s.signals(panel, days[-1])
    assert sig.symbol == "S19" and sig.target is None and sig.stop < sig.entry  # S18 is a winner but high turnover
    assert sig.features["formation_turnover"] == pytest.approx(0.001)
    assert sig.features["formation_ret"] == pytest.approx(np.exp(9 * 0.0005 * 126) - 1.0)  # 126 sessions, constant drift
    assert s.signals(panel, days[-2]) == []  # not the month's last session
    assert s.signals(panel.drop(columns="turnover"), days[-1]) == []  # no EDGAR turnover: silent, no proxy
    assert s.params["max_hold_days"] == 126 and s.engine_trail is False


def test_early_stage_formation_window_and_filters():
    s = strat(EARLY)
    panel, days = early_panel()
    last5 = panel["ts"].dt.date.isin(days[-5:])
    # a loser that jumps 10x in the skipped last week is still a loser: formation ends 5 sessions before the signal
    jump = panel.copy()
    jump.loc[last5 & (jump["symbol"] == "S00"), ["open", "high", "low", "close"]] *= 10.0
    assert [x.symbol for x in s.signals(jump, days[-1])] == ["S19"]
    # turnover in the skipped week is not read; a missing value inside the 126 formation sessions drops the name
    skip_nan = panel.copy()
    skip_nan.loc[last5 & (skip_nan["symbol"] == "S19"), "turnover"] = np.nan
    assert [x.symbol for x in s.signals(skip_nan, days[-1])] == ["S19"]
    form_nan = panel.copy()
    form_nan.loc[(form_nan["ts"].dt.date == days[-6]) & (form_nan["symbol"] == "S19"), "turnover"] = np.nan
    assert s.signals(form_nan, days[-1]) == []
    young = panel.loc[(panel["symbol"] != "S19") | panel["ts"].dt.date.isin(days[-400:])]
    assert s.signals(young, days[-1]) == []  # S19 has < 504 bars of history


# ----------------------------------------------------------------------------------------------- settings
def test_two_picks_registered_disabled_with_zero_reward_risk_floor():
    settings = load_settings()
    for name in (HVRP, EARLY):
        cfg = settings.strategies[name]
        assert cfg.get("enabled") is False if isinstance(cfg, dict) else cfg.enabled is False
        assert strategy_min_reward_risk(settings.strategies, name) == 0.0  # the lesson of three-picks Amendment 1
