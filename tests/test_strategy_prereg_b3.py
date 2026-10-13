"""The pre-registered batch-3 group (docs/preregistration/2026-10-10-batch3.md): large_cap_gross_profitability,
large_cap_residual_momentum. Point-in-time is also covered by tests/test_strategies_all.py."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.core.config import ROOT, load_settings
from swing_engine.data.calendar import trading_days
from swing_engine.features import extra
from swing_engine.research import replay
from swing_engine.risk.sizing import strategy_min_reward_risk
from tests.test_strategy_prereg_b2 import bars

GP, RM = "large_cap_gross_profitability", "large_cap_residual_momentum"
RAW = "ff3_resid_mom_756_231"


def strat(name: str):
    return registry.get("strategy", name)()


def band_panel(score: str, n: int = 30) -> tuple[pd.DataFrame, list]:
    """`n` names on 30 sessions ending at a month end; the extras are given: S00 has the lowest score (rank 1/n)."""
    days = trading_days("2025-09-01", "2025-10-31")[-30:]
    frames = [bars(f"S{i:02d}", days, np.full(len(days), 50.0 + i)).assign(
        **{score: 0.01 * i, f"{score}_rank": (i + 1) / n, RAW: 0.01 * i, "atr_63": 1.0,
           "month_end": [0.0] * (len(days) - 1) + [1.0]}) for i in range(n)]
    return pd.concat(frames, ignore_index=True), days


# ----------------------------------------------------------------------------------------------- features
def test_big_features_take_the_largest_names_then_apply_each_cards_filters(monkeypatch):
    monkeypatch.setattr(extra, "BIG_TOP_N", 3)
    days = trading_days("2025-10-01", "2025-10-03")
    cols = {  # symbol: mcap_pit, gross_prof, close_as_traded, hist_bars, raw score
        "A": (500.0, 0.40, 50.0, 900.0, 1.0), "B": (400.0, np.nan, 50.0, 900.0, 2.0),  # B: a bank, no gross profit
        "C": (300.0, 0.10, 9.0, 900.0, 3.0), "D": (200.0, 0.90, 50.0, 900.0, 4.0),  # C: under $10; D: 4th largest
        "E": (100.0, 0.20, 50.0, 100.0, 5.0),
    }
    panel = pd.concat([bars(s, days, np.full(3, 20.0)).assign(mcap_pit=m, gross_prof=g, close_as_traded=c, hist_bars=h,
                                                             **{RAW: r}) for s, (m, g, c, h, r) in cols.items()])
    out = extra.ensure_extra(panel.reset_index(drop=True), [*strat(GP).extra_features, *strat(RM).extra_features])
    last = out.loc[out["ts"] == out["ts"].max()].set_index("symbol")
    assert last["big_gross_prof"].dropna().to_dict() == {"A": 0.40, "C": 0.10}  # top 3, minus the one without GP
    assert last["big_gross_prof_rank"].dropna().to_dict() == {"A": 1.0, "C": 0.5}
    assert last["big_ff3_resid_mom_756_231"].dropna().to_dict() == {"A": 1.0, "B": 2.0}  # C is under $10
    young = extra.ensure_extra(panel.assign(hist_bars=755.0).reset_index(drop=True), ["big_ff3_resid_mom_756_231"])
    assert young["big_ff3_resid_mom_756_231"].isna().all()  # card: at least 756 bars
    bare = extra.ensure_extra(panel.drop(columns=["mcap_pit"]).reset_index(drop=True), ["big_gross_prof", "big_ff3_resid_mom_756_231"])
    assert bare[["big_gross_prof", "big_ff3_resid_mom_756_231"]].isna().all().all()  # no share join: silent


# ----------------------------------------------------------------------------------------------- strategies
def test_gross_profitability_buys_the_top_third_at_month_end_only():
    s = strat(GP)
    panel, days = band_panel("big_gross_prof")
    sigs = sorted(s.signals(panel, days[-1]), key=lambda x: -x.score)
    assert [x.symbol for x in sigs] == [f"S{i}" for i in range(29, 19, -1)]  # ranks 21/30 .. 30/30; 20/30 is not
    assert sigs[0].stop == pytest.approx(79.0 - 3.0) and sigs[0].target is None and sigs[0].score == 1.0
    assert s.signals(panel, days[-2]) == []  # not the month's last session
    assert s.signals(panel.assign(big_gross_prof_rank=np.nan), days[-1]) == []  # no EDGAR / share join: silent
    assert s.engine_trail is False and s.warmup_calendar_days == 0


def test_gross_profitability_sells_at_or_below_the_median():
    s = strat(GP)
    row = lambda rank, flag=1.0: pd.Series({"month_end": flag, "big_gross_prof_rank": rank})  # noqa: E731
    assert s.should_exit(row(0.50), 21) is True and s.should_exit(row(0.30), 21) is True
    assert s.should_exit(row(0.51), 21) is False and s.should_exit(row(0.60), 21) is False  # hold zone, not buy zone
    assert s.should_exit(row(np.nan), 21) is True  # left the 500 largest or lost its gross profit
    assert s.should_exit(row(0.10, 0.0), 5) is False  # only on a rebalance session


def test_residual_momentum_buys_the_top_decile_and_holds_the_top_fifth():
    s = strat(RM)
    panel, days = band_panel("big_ff3_resid_mom_756_231")
    assert sorted(x.symbol for x in s.signals(panel, days[-1])) == ["S27", "S28", "S29"]  # rank > 0.90 of 30
    assert s.signals(panel, days[-2]) == []
    assert s.signals(panel.assign(big_ff3_resid_mom_756_231_rank=np.nan), days[-1]) == []  # no French factors: no buys
    row = lambda rank, raw=1.0, flag=1.0: pd.Series({"month_end": flag, "big_ff3_resid_mom_756_231_rank": rank, RAW: raw})  # noqa: E731
    assert s.should_exit(row(0.80), 21) is True and s.should_exit(row(0.81), 21) is False
    assert s.should_exit(row(np.nan), 21) is True  # scored, but left the 500 / the price floor
    assert s.should_exit(row(np.nan, np.nan), 21) is False  # no raw score (factor table missing): rebalance skipped
    assert s.should_exit(row(0.10, 1.0, 0.0), 5) is False


def test_replay_warm_up_covers_the_756_bar_fit():
    """Regression (residual_momentum, 2024-26 replay): on the default 400-day warm-up the 756-bar scores were NaN
    until three years into the window, so the strategy only fired on the window's last month start."""
    for name in (RM, "residual_momentum"):
        s = strat(name)
        need = 756 + 1 + 2 * 23  # bars of the fit, one for the first return, two months of French lag
        assert len(trading_days(date(2024, 10, 7) - timedelta(days=s.warmup_calendar_days), date(2024, 10, 4))) >= need
        assert replay.warmup_days([s, strat(GP)]) == s.warmup_calendar_days
    assert replay.warmup_days([strat(GP)]) == replay.WARMUP_CALENDAR_DAYS

    class Store:
        def read_bars(self, symbols, first, end):
            self.first = first
            return bars("SPY", trading_days(first, end), np.linspace(400.0, 500.0, len(trading_days(first, end))))

    store = Store()
    panel = replay.build_replay_panel(store, date(2024, 10, 7), date(2024, 10, 31), None, 1200)
    assert store.first == date(2024, 10, 7) - timedelta(days=1200) and panel["ts"].min().date() <= date(2021, 6, 28)


# ----------------------------------------------------------------------------------------------- settings
def test_batch3_registered_disabled_and_books_fixed():
    settings = load_settings()
    for name in (GP, RM):
        assert settings.strategies[name].get("enabled") is False
        assert strategy_min_reward_risk(settings.strategies, name) == 0.0
    rm = load_settings.__wrapped__(Path(ROOT) / "config" / "prereg_b3.yaml")
    assert (rm.risk.max_position_pct, rm.risk.max_open_positions, rm.risk.risk_per_trade_pct) == (2.0, 50, 0.5)
    gp = load_settings.__wrapped__(Path(ROOT) / "config" / "prereg_b3_gp.yaml")
    assert (gp.risk.max_position_pct, gp.risk.max_open_positions, gp.risk.risk_per_trade_pct) == (1.6667, 60, 0.5)
    assert (rm.execution.max_new_orders_per_day, gp.execution.max_new_orders_per_day) == (50, 60)
    assert rm.data.store_path == gp.data.store_path == "data/live/replay_p3.duckdb"
    assert strat(GP).params["buy_rank_min"] == pytest.approx(2 / 3) and strat(GP).params["hold_rank_min"] == 0.5
    assert (strat(RM).params["buy_rank_min"], strat(RM).params["hold_rank_min"]) == (0.90, 0.80)
    assert all(strat(n).params["stop_atr_mult"] == 3.0 for n in (GP, RM))
