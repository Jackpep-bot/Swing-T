"""Data-snooping tests over the whole replay board (docs/methods.md, "Optimization and overfitting controls").

Per research window and horizon ``h`` the replay shadow ledgers become one matrix of block returns: rows are
non-overlapping blocks of ``h`` sessions on a shared calendar, columns are strategies, a cell is the mean net R
(per-stock costs, executable signals only: the leaderboard's definition) of the strategy's signals dated in the
block, 0 when it has none. On that matrix, with a stationary block bootstrap (Politis and Romano 1994) and a
benchmark of 0 (no trade):

* White's Reality Check (2000) and Hansen's SPA test (2005, consistent p-value): is the best strategy's edge 0?
* Romano-Wolf (2005) step-down p-values on the studentized means: which strategies pass, family-wise;
* probability of backtest overfitting (CSCV, ``metrics.probability_backtest_overfit``);
* deflated Sharpe with the cross-trial variance of the block Sharpes as ``sharpe_var``.

An extra test beside gate 2 (docs/gates.md), not a replacement for the haircut. It reads the ledgers and logs no
trial. Run::

    uv run python -m swing_engine.research.reality_check --settings config/replay_r2.yaml \
        --store data/live/replay_r1.duckdb --store data/live/replay_news.duckdb --out docs/reality_check.md
"""
from __future__ import annotations

import argparse
import math
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, skew

from swing_engine.research.cards import ROOT, WINDOWS, Window, cost_r, executable, with_costs
from swing_engine.research.leaderboard import MIN_BLOCKS, SESSIONS_PER_YEAR, _sessions
from swing_engine.research.metrics import (
    DEFAULT_CSCV_PARTITIONS,
    deflated_sharpe,
    probability_backtest_overfit,
)
from swing_engine.research.shadow import DEFAULT_HORIZONS, REPLAY_SHADOW_TABLE, TRADE_HITS, horizon_column

DEFAULT_BOOTSTRAPS = 2000
DEFAULT_SEED = 20261009
TOP_N = 10
#: ledger columns the block matrix needs (the full ledger is ~40 columns x 10M rows)
_BASE_COLUMNS = ("strategy", "symbol", "as_of", "entry", "stop", "entry_price")
DAILY_COLUMNS = ("strategy", "as_of", "horizon", "total", "n")


# ----------------------------------------------------------------------------------------------- ledger -> matrix


def daily_net(frame: pd.DataFrame, horizons: Sequence[int] = DEFAULT_HORIZONS) -> pd.DataFrame:
    """``strategy, as_of, horizon, total, n``: sum and count of net R (result_r - cost_r) over the executable
    signals of each strategy-day that became trades at the horizon (leaderboard.edge_stats' definition)."""
    frame = executable(frame)
    if frame.empty:
        return pd.DataFrame(columns=list(DAILY_COLUMNS))
    cost = cost_r(frame).fillna(0.0)
    out = []
    for h in horizons:
        hit, r = horizon_column("hit", h), horizon_column("result_r", h)
        if hit not in frame.columns:
            continue
        traded = frame[hit].astype(str).isin(TRADE_HITS) & frame[r].notna()
        net = (frame.loc[traded, r].astype(float) - cost[traded]).rename("net")
        keys = [frame.loc[traded, "strategy"].astype(str), pd.to_datetime(frame.loc[traded, "as_of"])]
        g = net.groupby(keys).agg(total="sum", n="count").reset_index()
        out.append(g.assign(horizon=int(h)))
    if not out:
        return pd.DataFrame(columns=list(DAILY_COLUMNS))
    return pd.concat(out, ignore_index=True)[list(DAILY_COLUMNS)]


def load_daily(paths: Iterable[Path], cost_store: Path, horizons: Sequence[int] = DEFAULT_HORIZONS) -> pd.DataFrame:
    """`daily_net` over the replay shadow ledgers of ``paths``, read one store and one calendar year at a time
    (read-only) so the ~10M-row ledgers never sit in memory together. A strategy-day present in several stores
    is taken from the last one listed (research.cards.read_shadow keeps the last duplicate signal)."""
    import duckdb

    wanted = [*_BASE_COLUMNS, *(horizon_column(k, h) for h in horizons for k in ("hit", "result_r"))]
    parts = []
    for order, path in enumerate(paths):
        con = duckdb.connect(str(path), read_only=True)
        try:
            tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
            if REPLAY_SHADOW_TABLE not in tables:
                continue
            have = {r[0] for r in con.execute(f"DESCRIBE {REPLAY_SHADOW_TABLE}").fetchall()}
            cols = ", ".join(c for c in wanted if c in have)
            years = [r[0] for r in con.execute(f"SELECT DISTINCT year(as_of) FROM {REPLAY_SHADOW_TABLE} ORDER BY 1").fetchall()]
            for y in years:
                frame = con.execute(f"SELECT {cols} FROM {REPLAY_SHADOW_TABLE} WHERE year(as_of) = ?", [y]).df()
                parts.append(daily_net(with_costs(frame, cost_store), horizons).assign(_order=order))
        finally:
            con.close()
    parts = [p for p in parts if not p.empty]
    if not parts:
        return pd.DataFrame(columns=list(DAILY_COLUMNS))
    daily = pd.concat(parts, ignore_index=True).sort_values("_order", kind="stable")
    return daily.drop_duplicates(["strategy", "as_of", "horizon"], keep="last").drop(columns="_order")


def block_matrix(daily: pd.DataFrame, window: Window, horizon: int, min_blocks: int = MIN_BLOCKS) -> pd.DataFrame:
    """Blocks x strategies mean net R for one window and horizon. Rows run over every ``horizon``-session block
    from the first to the last block in which any strategy traded; a strategy with no trade in a block gets 0.
    Strategies that traded in fewer than ``min_blocks`` blocks (no t-stat on the leaderboard either) are left out."""
    d = pd.to_datetime(daily["as_of"]) if len(daily) else pd.Series(dtype="datetime64[ns]")
    sub = daily.loc[(daily["horizon"] == horizon) & (d >= pd.Timestamp(window.start)) & (d <= pd.Timestamp(window.end))]
    if sub.empty:
        return pd.DataFrame()
    block = pd.Series(_sessions(sub["as_of"]) // horizon, index=sub.index, name="block")
    g = sub.groupby([block, sub["strategy"]])[["total", "n"]].sum()
    means = (g["total"] / g["n"]).unstack("strategy")
    means = means.loc[:, means.notna().sum() >= min_blocks]
    means = means.reindex(range(int(means.index.min()), int(means.index.max()) + 1)).fillna(0.0)
    return means.loc[:, means.std(ddof=1) > 0]


# ----------------------------------------------------------------------------------------------- bootstrap tests


def default_mean_block(n_obs: int) -> int:
    """Mean block length of the stationary bootstrap: n^(1/3), at least 2 (rows are already h-session blocks, so
    the remaining serial dependence is short). ponytail: rule of thumb; use Politis-White (2004) automatic
    selection if the p-values prove sensitive to it."""
    return max(2, round(n_obs ** (1.0 / 3.0)))


def stationary_bootstrap_counts(n_obs: int, n_boot: int, mean_block: float, rng: np.random.Generator) -> np.ndarray:
    """``(n_boot, n_obs)`` counts of how often each row is drawn in a Politis-Romano resample of length n_obs:
    blocks start at a uniform row, have geometric length with mean ``mean_block`` and wrap around the end."""
    pos = np.arange(n_obs)
    restart = rng.random((n_boot, n_obs)) < 1.0 / mean_block
    restart[:, 0] = True
    starts = rng.integers(0, n_obs, size=(n_boot, n_obs))
    last = np.maximum.accumulate(np.where(restart, pos, 0), axis=1)
    idx = (np.take_along_axis(starts, last, axis=1) + pos - last) % n_obs
    flat = (idx + np.arange(n_boot)[:, None] * n_obs).ravel()
    return np.bincount(flat, minlength=n_boot * n_obs).reshape(n_boot, n_obs)


def reality_check(
    matrix: pd.DataFrame | np.ndarray,
    n_boot: int = DEFAULT_BOOTSTRAPS,
    mean_block: float | None = None,
    seed: int | None = DEFAULT_SEED,
    n_trials: int | None = None,
    periods_per_year: float = SESSIONS_PER_YEAR,
) -> dict[str, Any]:
    """White's Reality Check, Hansen's SPA and Romano-Wolf step-down p-values, PBO and deflated Sharpe for an
    (observations x strategies) matrix of returns over a benchmark of 0.

    ``rc_p`` / ``spa_p``: p-value of "no strategy has a positive mean". SPA studentizes and drops strategies
    worse than -sqrt(2 log log n) standard errors from the null. Each resample is studentized by its own
    standard deviation (bootstrap-t, as Romano and Wolf recommend): Hansen's fixed standard error rejected
    23% (100 x 130) to 53% (26 x 130) of pure-noise matrices of the board's shape at the 5% level. ``table`` has
    one row per strategy, sorted by mean: ``mean``, ``t`` (mean / sd x sqrt(n)), ``p_adj`` (step-down,
    family-wise), ``sharpe`` (per observation) and ``dsr`` (deflated over ``n_trials``, default the number of
    columns, with the variance of the columns' Sharpes as ``sharpe_var``).
    """
    names = list(matrix.columns) if isinstance(matrix, pd.DataFrame) else None
    m = np.asarray(matrix, dtype=float)
    n, k = m.shape
    names = names or [f"s{j}" for j in range(k)]
    if n < MIN_BLOCKS or k < 1:
        raise ValueError(f"need at least {MIN_BLOCKS} observations and one strategy, got {m.shape}")
    rng = np.random.default_rng(seed)
    counts = stationary_bootstrap_counts(n, n_boot, mean_block or default_mean_block(n), rng)
    mean = m.mean(axis=0)
    boot = counts @ m / n  # (n_boot, k) resampled means
    root_n = math.sqrt(n)
    sd = m.std(axis=0, ddof=1)
    sd = np.where(sd > 0, sd, np.inf)
    boot_var = (counts @ (m * m) / n - boot**2) * n / (n - 1)
    boot_sd = np.sqrt(np.clip(boot_var, 0.0, None))
    boot_sd = np.where(boot_sd > 0, boot_sd, sd)  # a resample that drew only one value of a sparse column
    t = root_n * mean / sd

    rc_stat = root_n * mean.max()
    rc_p = float(np.mean(root_n * (boot - mean).max(axis=1) >= rc_stat))

    spa_stat = max(float(t.max()), 0.0)
    keep = t >= -math.sqrt(2.0 * math.log(math.log(n)))
    z_spa = root_n * (boot - np.where(keep, mean, 0.0)) / boot_sd
    spa_p = float(np.mean(np.maximum(z_spa.max(axis=1), 0.0) >= spa_stat))

    order = np.argsort(-t)
    z = (root_n * (boot - mean) / boot_sd)[:, order]
    tail_max = np.maximum.accumulate(z[:, ::-1], axis=1)[:, ::-1]  # max over the strategies not yet rejected
    p_adj = np.empty(k)
    p_adj[order] = np.maximum.accumulate((tail_max >= t[order]).mean(axis=0))

    sr = mean / sd
    sharpe_var = float(sr.var(ddof=1)) if k > 1 else None
    trials = max(int(n_trials or 0), k)
    dsr = [deflated_sharpe(float(sr[j]), trials, n, float(skew(m[:, j])), float(kurtosis(m[:, j], fisher=False)),
                           sharpe_var=sharpe_var, periods_per_year=None) for j in range(k)]
    table = pd.DataFrame({"strategy": names, "mean": mean, "t": t, "p_adj": p_adj, "sharpe": sr, "dsr": dsr})
    table = table.sort_values("mean", ascending=False, ignore_index=True)

    pbo = math.nan
    partitions = min(DEFAULT_CSCV_PARTITIONS, n // 2 * 2)
    if k >= 2:
        pbo = float(probability_backtest_overfit(m, partitions, max(int(periods_per_year), 1))["pbo"])
    return {"n_obs": n, "n_strategies": k, "n_boot": n_boot, "n_trials": trials, "rc_p": rc_p, "spa_p": spa_p,
            "pbo": pbo, "sharpe_var": sharpe_var, "table": table}


# ----------------------------------------------------------------------------------------------- report


def run(
    daily: pd.DataFrame,
    windows: Iterable[Window] = WINDOWS,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """`reality_check` for every (window, horizon) with enough blocks; each result also carries both keys."""
    out = []
    for w in windows:
        for h in horizons:
            m = block_matrix(daily, w, h)
            if m.shape[0] < MIN_BLOCKS or m.shape[1] < 1:
                continue
            res = reality_check(m, periods_per_year=SESSIONS_PER_YEAR / h, **kwargs)
            out.append({"window": w, "horizon": h, **res})
    return out


def render(results: Sequence[dict[str, Any]], top: int = TOP_N) -> str:
    def f(x: float | None, spec: str = ".3f") -> str:
        return "-" if x is None or not math.isfinite(x) else format(x, spec)

    lines = [
        "# Reality check: is the best of the board better than no trade?",
        "",
        "Generated by `swing_engine.research.reality_check` from the replay shadow ledgers. Per window and horizon: "
        "a matrix of mean net R per non-overlapping block of the horizon (rows) by strategy (columns, 0 when it did "
        "not trade; strategies with fewer than "
        f"{MIN_BLOCKS} traded blocks left out), resampled with a stationary block bootstrap. `RC p` (White) and "
        "`SPA p` (Hansen) are the p-values of \"the best strategy has no edge over not trading\"; small means some "
        "strategy has one. `PBO` is the share of half/half splits in which the in-sample best ranks below the "
        "median out of sample (0.5 = picking the best is a coin flip; a low value says the ranking persists, which "
        "it also does when the best is merely the least bad, so read it with the p-values). In the tables `p adj` is the Romano-Wolf "
        "step-down p-value (family-wise over every strategy in the matrix) and `DSR` the deflated Sharpe "
        "probability using the variance of the block Sharpes across the matrix. An extra test beside gate 2, "
        "not a replacement for the haircut.",
        "",
        "| window | horizon | strategies | blocks | RC p | SPA p | PBO |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(f"| {r['window'].start} .. {r['window'].end} | {r['horizon']}d | {r['n_strategies']} | "
                     f"{r['n_obs']} | {f(r['rc_p'])} | {f(r['spa_p'])} | {f(r['pbo'], '.2f')} |")
    if not results:
        lines.append("| - | - | 0 | 0 | - | - | - |")
    for r in results:
        w = r["window"]
        lines += ["", f"## {w.start} .. {w.end}, {r['horizon']}d ({w.label})", "",
                  f"{r['n_boot']} resamples; deflated over {r['n_trials']} trials. Top {top} by mean net R per block.", "",
                  "| strategy | mean net R | t | p adj | block Sharpe | DSR |", "|---|---|---|---|---|---|"]
        for row in r["table"].head(top).itertuples():
            lines.append(f"| {row.strategy} | {f(row.mean, '+.3f')} | {f(row.t, '.2f')} | {f(row.p_adj)} | "
                         f"{f(row.sharpe, '+.3f')} | {f(row.dsr)} |")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> list[dict[str, Any]]:
    from swing_engine.core.config import load_settings
    from swing_engine.research.trials import trial_count

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settings", default="config/replay.yaml")
    ap.add_argument("--store", action="append", default=[], help="extra replay store (repeatable)")
    ap.add_argument("--out", default="docs/reality_check.md")
    ap.add_argument("--bootstraps", type=int, default=DEFAULT_BOOTSTRAPS)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = ap.parse_args(argv)
    settings = load_settings.__wrapped__(Path(args.settings))
    store_path = ROOT / settings.data.store_path
    daily = load_daily([store_path, *(ROOT / s for s in args.store)], store_path)
    results = run(daily, n_boot=args.bootstraps, seed=args.seed, n_trials=trial_count(None))
    (ROOT / args.out).write_text(render(results))
    for r in results:
        print(f"{r['window'].start.year} {r['horizon']}d: {r['n_strategies']} strategies, {r['n_obs']} blocks, "
              f"RC p {r['rc_p']:.3f}, SPA p {r['spa_p']:.3f}, PBO {r['pbo']:.2f}")
    print(f"-> {args.out}")
    return results


if __name__ == "__main__":
    main()


__all__ = ["block_matrix", "daily_net", "load_daily", "reality_check", "render", "run", "stationary_bootstrap_counts"]
