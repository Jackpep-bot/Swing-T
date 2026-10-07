"""Metrics: summary stats, Deflated Sharpe (Bailey & Lopez de Prado) and PBO via CSCV."""
from __future__ import annotations

import itertools
import math

import numpy as np
import pytest

from swing_engine.research.backtest import CostModel, run_backtest
from swing_engine.research.metrics import (
    cagr,
    deflated_sharpe,
    expected_max_sharpe,
    max_drawdown,
    probabilistic_sharpe,
    probability_backtest_overfit,
    profit_factor,
    sharpe,
    sortino,
    summarize,
)
from tests.fixtures.research.strategies import FlagStrategy
from tests.fixtures.research.synthetic_panel import make_panel

N_OBS = 500
SR_ANNUAL = 1.5
PPY = 252


def test_deflated_sharpe_decreases_with_trial_count():
    vals = [deflated_sharpe(SR_ANNUAL, n, N_OBS) for n in (1, 5, 20, 100, 1000)]
    assert all(0.0 <= v <= 1.0 for v in vals)
    assert all(a > b for a, b in itertools.pairwise(vals))


def test_deflated_sharpe_single_trial_is_plain_psr():
    assert deflated_sharpe(SR_ANNUAL, 1, N_OBS) == pytest.approx(probabilistic_sharpe(SR_ANNUAL / math.sqrt(PPY), N_OBS))
    assert deflated_sharpe(SR_ANNUAL, 1, N_OBS, periods_per_year=None) == pytest.approx(
        probabilistic_sharpe(SR_ANNUAL, N_OBS)
    )


def test_non_normality_lowers_deflated_sharpe():
    base = deflated_sharpe(SR_ANNUAL, 10, N_OBS, skew=0.0, kurt=3.0)
    assert deflated_sharpe(SR_ANNUAL, 10, N_OBS, skew=0.0, kurt=12.0) < base
    assert deflated_sharpe(SR_ANNUAL, 10, N_OBS, skew=-1.0, kurt=3.0) < base
    assert math.isnan(deflated_sharpe(SR_ANNUAL, 10, 1))  # too few observations


def test_expected_max_sharpe_grows_with_trials_and_variance():
    assert expected_max_sharpe(1, 0.01) == 0.0
    assert expected_max_sharpe(10, 0.01) < expected_max_sharpe(100, 0.01)
    assert expected_max_sharpe(100, 0.01) < expected_max_sharpe(100, 0.04)


def test_explicit_sharpe_variance_is_used():
    low = deflated_sharpe(SR_ANNUAL, 50, N_OBS, sharpe_var=1e-6)
    high = deflated_sharpe(SR_ANNUAL, 50, N_OBS, sharpe_var=0.05)
    assert low > high


def test_pbo_is_near_half_for_pure_noise():
    rng = np.random.default_rng(7)
    out = probability_backtest_overfit(rng.normal(0.0, 0.01, (800, 20)), n_partitions=8)
    assert 0.25 <= out["pbo"] <= 0.75
    assert out["n_combinations"] == 70 and out["n_trials"] == 20
    assert out["logits"].shape == (70,)
    assert {"prob_oos_loss", "degradation_slope", "is_sharpe_selected", "oos_sharpe_selected"} <= out.keys()


def test_pbo_is_low_when_one_trial_has_a_real_edge():
    rng = np.random.default_rng(8)
    m = rng.normal(0.0, 0.01, (800, 20))
    m[:, 3] += 0.004
    out = probability_backtest_overfit(m, n_partitions=8)
    assert out["pbo"] < 0.15
    assert out["prob_oos_loss"] < 0.15


def test_pbo_input_validation():
    rng = np.random.default_rng(0)
    with pytest.raises(ValueError):
        probability_backtest_overfit(rng.normal(size=(100, 5)), n_partitions=7)
    with pytest.raises(ValueError):
        probability_backtest_overfit(rng.normal(size=(10, 5)), n_partitions=16)
    with pytest.raises(ValueError):
        probability_backtest_overfit(rng.normal(size=(100, 1)), n_partitions=4)


def test_basic_stats():
    assert max_drawdown([100.0, 120.0, 90.0, 130.0]) == pytest.approx(0.25)
    assert max_drawdown([1.0, 2.0, 3.0]) == 0.0
    assert profit_factor([10.0, -5.0, 20.0, -5.0]) == pytest.approx(3.0)
    assert math.isinf(profit_factor([1.0, 2.0]))
    assert math.isnan(profit_factor([]))
    assert sharpe(np.full(50, 0.001)) == 0.0
    r = np.array([0.02, 0.0, 0.01, -0.01])
    assert sharpe(r) == pytest.approx(r.mean() / r.std(ddof=1) * math.sqrt(PPY))
    assert sortino(np.array([0.01, 0.02, 0.03])) == math.inf
    doubling = np.linspace(100.0, 200.0, PPY + 1)
    assert cagr(doubling) == pytest.approx(1.0)


def test_summarize_on_backtest_result():
    res = run_backtest(FlagStrategy(), make_panel(n_symbols=5, n_days=120, seed=2, edge=0.05), costs=CostModel())
    s = summarize(res)
    expected = {"trades", "win_rate", "avg_r", "profit_factor", "cagr", "max_dd", "sharpe", "turnover", "cost_drag",
                "skew", "kurt", "n_obs", "avg_exposure", "total_return"}
    assert expected <= s.keys()
    assert s["trades"] == len(res.trades)
    assert s["n_obs"] == len(res.equity)
    assert 0.0 <= s["win_rate"] <= 1.0
    assert s["max_dd"] >= 0.0
    assert s["turnover"] > 0 and s["cost_drag"] > 0
    assert s["total_return"] == pytest.approx(res.total_return)
