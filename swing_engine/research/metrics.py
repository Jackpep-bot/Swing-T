"""Performance statistics and the overfitting corrections the gate in docs/gates.md requires.

- ``summarize(result)``: headline numbers for a ``BacktestResult``.
- ``deflated_sharpe``: Bailey & Lopez de Prado (2014), "The Deflated Sharpe Ratio", J. Portfolio Mgmt 40(5).
- ``probability_backtest_overfit``: Bailey, Borwein, Lopez de Prado & Zhu (2017), CSCV procedure.

Conventions: returns are per-period simple returns; ``sharpe`` is annualized by ``sqrt(periods_per_year)``;
``max_dd`` is a positive fraction; ``cagr``, ``turnover`` and ``cost_drag`` are annualized.
"""
from __future__ import annotations

import itertools
import math
from typing import Any

import numpy as np
import pandas as pd
import structlog
from scipy.stats import norm

from swing_engine.research.backtest import TRADING_DAYS_PER_YEAR, BacktestResult

log = structlog.get_logger(__name__)

DEFAULT_PERIODS_PER_YEAR = TRADING_DAYS_PER_YEAR
MIN_YEARS = 1.0 / TRADING_DAYS_PER_YEAR
EULER_MASCHERONI = 0.5772156649015329
NORMAL_KURTOSIS = 3.0
DEFAULT_CSCV_PARTITIONS = 16
LOGIT_EPS = 1e-6
MIN_OBS_FOR_MOMENTS = 4


# ----------------------------------------------------------------------------------------------- basics


def returns_from_equity(equity: pd.Series) -> pd.Series:
    eq = equity.astype(float)
    return eq.pct_change().fillna(0.0)


def sharpe(returns: pd.Series | np.ndarray, periods_per_year: int = DEFAULT_PERIODS_PER_YEAR, risk_free: float = 0.0) -> float:
    """Annualized Sharpe of per-period returns (0.0 when the volatility is zero)."""
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]
    if r.size < 2:
        return math.nan
    excess = r - risk_free / periods_per_year
    sd = excess.std(ddof=1)
    if sd == 0:
        return 0.0
    return float(excess.mean() / sd * math.sqrt(periods_per_year))


def sortino(returns: pd.Series | np.ndarray, periods_per_year: int = DEFAULT_PERIODS_PER_YEAR) -> float:
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]
    if r.size < 2:
        return math.nan
    downside = np.minimum(r, 0.0)
    dd = math.sqrt(float(np.mean(downside**2)))
    if dd == 0:
        return 0.0 if r.mean() <= 0 else math.inf
    return float(r.mean() / dd * math.sqrt(periods_per_year))


def max_drawdown(equity: pd.Series | np.ndarray) -> float:
    """Largest peak-to-trough decline as a positive fraction of the peak."""
    eq = np.asarray(equity, dtype=float)
    if eq.size == 0:
        return math.nan
    peaks = np.maximum.accumulate(eq)
    dd = 1.0 - eq / peaks
    return float(np.nanmax(dd))


def cagr(equity: pd.Series | np.ndarray, periods_per_year: int = DEFAULT_PERIODS_PER_YEAR) -> float:
    eq = np.asarray(equity, dtype=float)
    if eq.size < 2 or eq[0] <= 0 or eq[-1] <= 0:
        return math.nan
    years = max((eq.size - 1) / periods_per_year, MIN_YEARS)
    return float((eq[-1] / eq[0]) ** (1.0 / years) - 1.0)


def profit_factor(pnl: pd.Series | np.ndarray) -> float:
    p = np.asarray(pnl, dtype=float)
    p = p[~np.isnan(p)]
    if p.size == 0:
        return math.nan
    gains = p[p > 0].sum()
    losses = -p[p < 0].sum()
    if losses == 0:
        return math.inf if gains > 0 else math.nan
    return float(gains / losses)


# ----------------------------------------------------------------------------------------------- summary


def summarize(result: BacktestResult, periods_per_year: int = DEFAULT_PERIODS_PER_YEAR) -> dict[str, Any]:
    """Headline metrics: trades, win_rate, avg_r, profit_factor, cagr, max_dd, sharpe, turnover, cost_drag, ..."""
    eq = result.equity["equity"].astype(float) if len(result.equity) else pd.Series([result.initial_equity])
    rets = returns_from_equity(eq)
    n_obs = int(len(rets))
    years = max(n_obs / periods_per_year, MIN_YEARS)
    mean_equity = float(eq.mean()) if n_obs else result.initial_equity

    t = result.trades
    n = int(len(t))
    pnl = t["pnl"].astype(float) if n else pd.Series(dtype=float)
    r = t["r_multiple"].astype(float) if n else pd.Series(dtype=float)
    wins = pnl > 0
    losses = pnl < 0

    def _mean(s: pd.Series) -> float:
        return float(s.mean()) if len(s) else math.nan

    moments_ok = n_obs >= MIN_OBS_FOR_MOMENTS
    out: dict[str, Any] = {
        "strategy": result.strategy,
        "start": result.start.isoformat(),
        "end": result.end.isoformat(),
        "trades": n,
        "win_rate": float(wins.mean()) if n else math.nan,
        "avg_r": _mean(r),
        "avg_win_r": _mean(r[wins]),
        "avg_loss_r": _mean(r[losses]),
        "expectancy": _mean(pnl),
        "profit_factor": profit_factor(pnl) if n else math.nan,
        "total_return": result.total_return,
        "cagr": cagr(eq, periods_per_year),
        "max_dd": max_drawdown(eq),
        "sharpe": sharpe(rets, periods_per_year),
        "sortino": sortino(rets, periods_per_year),
        "turnover": float(t["entry_notional"].sum()) / mean_equity / years if n else 0.0,
        "cost_drag": float(t["costs"].sum()) / mean_equity / years if n else 0.0,
        "total_costs": float(t["costs"].sum()) if n else 0.0,
        "avg_hold_bars": _mean(t["bars_held"].astype(float)) if n else math.nan,
        "avg_exposure": result.exposure,
        "n_obs": n_obs,
        "years": years,
        "skew": float(rets.skew()) if moments_ok else math.nan,
        "kurt": float(rets.kurt() + NORMAL_KURTOSIS) if moments_ok else math.nan,
        "n_signals": result.n_signals,
        "n_entries_skipped": result.n_entries_skipped,
    }
    return out


# ----------------------------------------------------------------------------------------------- deflated Sharpe


def probabilistic_sharpe(
    sr: float, n_obs: int, skew: float = 0.0, kurt: float = NORMAL_KURTOSIS, benchmark: float = 0.0
) -> float:
    """PSR: probability that the true per-period Sharpe exceeds ``benchmark`` given the observed ``sr``.

    ``kurt`` is the raw (non-excess) kurtosis, 3 for a normal distribution.
    """
    if n_obs < 2 or not math.isfinite(sr):
        return math.nan
    denom = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr**2
    if denom <= 0:
        return math.nan
    z = (sr - benchmark) * math.sqrt(n_obs - 1) / math.sqrt(denom)
    return float(norm.cdf(z))


def expected_max_sharpe(n_trials: int, sharpe_var: float) -> float:
    """E[max SR] over ``n_trials`` independent zero-skill trials with SR variance ``sharpe_var`` (B&LdP eq. 2)."""
    if n_trials <= 1 or sharpe_var <= 0:
        return 0.0
    n = float(n_trials)
    z1 = norm.ppf(1.0 - 1.0 / n)
    z2 = norm.ppf(1.0 - 1.0 / (n * math.e))
    return float(math.sqrt(sharpe_var) * ((1.0 - EULER_MASCHERONI) * z1 + EULER_MASCHERONI * z2))


def deflated_sharpe(
    sharpe_ratio: float,
    n_trials: int,
    n_obs: int,
    skew: float = 0.0,
    kurt: float = NORMAL_KURTOSIS,
    *,
    sharpe_var: float | None = None,
    periods_per_year: int | None = DEFAULT_PERIODS_PER_YEAR,
) -> float:
    """Deflated Sharpe Ratio: PSR against the expected maximum Sharpe of ``n_trials`` zero-skill trials.

    ``sharpe_ratio`` is annualized by ``sqrt(periods_per_year)`` (pass ``periods_per_year=None`` for a
    per-period value). ``sharpe_var`` is the cross-sectional variance of the per-period trial Sharpes; when
    unknown it defaults to the null-hypothesis estimator variance ``1 / n_obs``. Returns a probability in
    [0, 1]; the gate in docs/gates.md asks for significance with the full logged trial count.
    """
    if n_obs < 2 or not math.isfinite(sharpe_ratio):
        return math.nan
    scale = math.sqrt(periods_per_year) if periods_per_year else 1.0
    sr = sharpe_ratio / scale
    var = sharpe_var if sharpe_var is not None else 1.0 / n_obs
    sr0 = expected_max_sharpe(max(int(n_trials), 1), var)
    return probabilistic_sharpe(sr, n_obs, skew, kurt, benchmark=sr0)


# ----------------------------------------------------------------------------------------------- PBO / CSCV


def _sharpe_from_stats(sums: np.ndarray, sq: np.ndarray, n: float, periods_per_year: int) -> np.ndarray:
    mean = sums / n
    var = (sq - n * mean**2) / max(n - 1.0, 1.0)
    sd = np.sqrt(np.clip(var, 0.0, None))
    with np.errstate(divide="ignore", invalid="ignore"):
        sr = np.where(sd > 0, mean / sd * math.sqrt(periods_per_year), 0.0)
    return sr


def probability_backtest_overfit(
    trial_returns: pd.DataFrame | np.ndarray,
    n_partitions: int = DEFAULT_CSCV_PARTITIONS,
    periods_per_year: int = DEFAULT_PERIODS_PER_YEAR,
) -> dict[str, Any]:
    """CSCV estimate of the Probability of Backtest Overfitting for a (observations x trials) return matrix.

    The rows are split into ``n_partitions`` contiguous blocks; for every choice of half the blocks as the
    in-sample set the best in-sample trial (by Sharpe) is located and its out-of-sample relative rank is
    recorded. PBO is the share of combinations where that trial ranks below the OOS median.
    Returns pbo, the logit distribution, OOS Sharpe of the selected trials and the IS->OOS degradation fit.
    """
    m = np.asarray(trial_returns, dtype=float)
    if m.ndim == 1:
        m = m[:, None]
    m = np.nan_to_num(m, nan=0.0)
    n_obs, n_trials = m.shape
    if n_partitions < 2 or n_partitions % 2:
        raise ValueError("n_partitions must be an even number >= 2")
    if n_obs < n_partitions:
        raise ValueError(f"need at least {n_partitions} observations, got {n_obs}")
    if n_trials < 2:
        raise ValueError("need at least two trials")

    blocks = np.array_split(np.arange(n_obs), n_partitions)
    sums = np.stack([m[b].sum(axis=0) for b in blocks])
    sqs = np.stack([(m[b] ** 2).sum(axis=0) for b in blocks])
    counts = np.array([len(b) for b in blocks], dtype=float)
    all_blocks = np.arange(n_partitions)
    half = n_partitions // 2

    logits: list[float] = []
    is_sel: list[float] = []
    oos_sel: list[float] = []
    for combo in itertools.combinations(range(n_partitions), half):
        tr = np.array(combo)
        te = np.setdiff1d(all_blocks, tr)
        sr_tr = _sharpe_from_stats(sums[tr].sum(axis=0), sqs[tr].sum(axis=0), counts[tr].sum(), periods_per_year)
        sr_te = _sharpe_from_stats(sums[te].sum(axis=0), sqs[te].sum(axis=0), counts[te].sum(), periods_per_year)
        best = int(np.argmax(sr_tr))
        omega = float(np.sum(sr_te <= sr_te[best])) / n_trials
        omega = min(max(omega, LOGIT_EPS), 1.0 - LOGIT_EPS)
        logits.append(math.log(omega / (1.0 - omega)))
        is_sel.append(float(sr_tr[best]))
        oos_sel.append(float(sr_te[best]))

    lam = np.array(logits)
    is_arr = np.array(is_sel)
    oos_arr = np.array(oos_sel)
    if is_arr.size > 1 and is_arr.std() > 0:
        slope, intercept = np.polyfit(is_arr, oos_arr, 1)
    else:
        slope, intercept = math.nan, math.nan
    out = {
        "pbo": float(np.mean(lam <= 0.0)),
        "n_combinations": int(lam.size),
        "n_trials": int(n_trials),
        "n_partitions": int(n_partitions),
        "logits": lam,
        "is_sharpe_selected": is_arr,
        "oos_sharpe_selected": oos_arr,
        "prob_oos_loss": float(np.mean(oos_arr < 0.0)),
        "degradation_slope": float(slope),
        "degradation_intercept": float(intercept),
    }
    log.info("metrics.pbo", pbo=out["pbo"], n_trials=n_trials, n_combinations=out["n_combinations"])
    return out
