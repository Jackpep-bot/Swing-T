"""Review fixes for xs_momentum_rank: per-instance rank extra (JT variant exit) and the monthly roll (no 21-bar time stop)."""
from __future__ import annotations

import numpy as np

from swing_engine.core import registry
from swing_engine.features.extra import ensure_extra, required_extras
from swing_engine.research.backtest import run_backtest
from tests.fixtures.strategies.panel import add_features, make_bars


def strat(**params):
    return registry.get("strategy", "xs_momentum_rank")(params or None)


def test_jt_variant_rank_reaches_replay_panel_and_exit_fires():
    s = strat(rank_col="mom_7_1_rank")
    assert required_extras([s]) == ["mom_7_1_rank"]
    assert required_extras([strat()]) == ["mom_12_1_rank"]
    # replay / nightly build the panel from required_extras, then hand the held row to should_exit
    syms = [f"S{i:02d}" for i in range(10)]
    panel = ensure_extra(add_features(make_bars(syms, n_days=200, seed=3)), required_extras([s]))
    last = panel.loc[panel["ts"] == panel["ts"].max()]
    worst = last.loc[last["mom_7_1_rank"].idxmin()]
    assert worst["mom_7_1_rank"] < 0.70 and s.should_exit(worst, 5)


def test_top_decile_holding_rolls_across_month_end():
    # AAA stays in the top decile every month: one position held across the Feb (20-session) month end,
    # not time-stopped at 21 bars and then locked out of the 02-29 rebalance as busy.
    p = add_features(make_bars(["AAA", *(f"S{i:02d}" for i in range(9))], n_days=90, seed=5, drift=0.002, vol=0.004))
    p["mom_12_1_rank"] = np.where(p["symbol"] == "AAA", 0.95, 0.5)
    res = run_backtest(strat(), p, start="2024-01-31", end=str(p["ts"].max().date()))
    aaa = res.trades.loc[res.trades["symbol"] == "AAA"]
    assert len(aaa) == 1
    assert aaa["exit_reason"].iloc[0] != "time_stop" and aaa["bars_held"].iloc[0] > 40


def test_replay_reranks_rank_extras_among_the_screened_universe():
    from swing_engine.research.replay import _rerank_extras, _with_extras

    s = strat(rank_col="mom_7_1_rank")
    syms = [f"S{i:02d}" for i in range(6)]
    panel = _with_extras(add_features(make_bars(syms, n_days=200, seed=3)), [s])
    assert "mom_7_1" in panel.columns  # the rank's base column rides along for the re-rank
    member = panel["symbol"].isin(syms[:3])  # store has 6 symbols, the screen keeps 3
    _rerank_extras(panel, member, [s])
    last = panel.loc[panel["ts"] == panel["ts"].max()]
    inside = last.loc[member.loc[last.index]]
    assert sorted(inside["mom_7_1_rank"]) == [1 / 3, 2 / 3, 1.0]
    # a held name that left the screen is ranked as if added to it, so its rank exit still fires
    out = last.loc[~member.loc[last.index]].iloc[0]
    expect = ((inside["mom_7_1"] < out["mom_7_1"]).sum() + 1) / 4
    assert out["mom_7_1_rank"] == expect
