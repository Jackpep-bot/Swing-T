"""Rank every replayed strategy by net edge with a multiple-testing haircut (docs/gates.md gate 2).

Input: the replay shadow ledger (every signal graded at 5/10/20 sessions, ``research.cards.read_shadow``). Per
strategy, window and horizon ``h``:

* net R per traded signal = gross ``result_r_<h>d`` minus round-trip slippage (``research.cards.cost_r``);
* the yardstick (default since 2026-10-13) is net R minus the market component: what SPY returned over the same
  holding span on the same dollars (``research.cards.market_r``, beta 1). Every strategy here is long-only, and
  docs/attribution.md showed most positive gross R was the index going up. ``--absolute`` grades plain net R;
* signals are pooled into blocks of ``h`` sessions (by signal date), so overlapping holds do not count as
  independent bets; ``t`` = mean / sd x sqrt(blocks) over the block means, annual Sharpe = t / sqrt(years);
* Harvey-Liu Bonferroni haircut over ``n_trials`` = max(logged trials, strategies x horizons x windows).

A survivor has a positive haircut Sharpe on the yardstick at the same horizon in BOTH windows. Run::

    uv run python -m swing_engine.research.leaderboard --settings config/replay.yaml --store ... > docs/leaderboard.md
"""
from __future__ import annotations

import argparse
import math
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.research.cards import (
    MARKET_SYMBOL,
    ROOT,
    WINDOWS,
    Window,
    cost_r,
    executable,
    read_shadow,
    relative_r,
    with_costs,
)
from swing_engine.research.metrics import haircut_sharpe
from swing_engine.research.shadow import DEFAULT_HORIZONS, TRADE_HITS, horizon_column
from swing_engine.research.trials import iter_trials, log_trial, trial_count

SESSIONS_PER_YEAR = 252
MIN_BLOCKS = 8  # fewer independent blocks than this: no t-stat (too few to say anything)


def _sessions(dates: pd.Series) -> np.ndarray:
    """Business-day ordinal of each date (NYSE holidays ignored: only block boundaries depend on it)."""
    d = pd.to_datetime(dates).values.astype("datetime64[D]")
    return np.busday_count(np.datetime64("2000-01-03"), d)


def edge_stats(frame: pd.DataFrame, horizon: int, years: float, n_trials: int, relative: bool = False) -> dict[str, float]:
    """Net edge of one strategy in one window at one horizon (see the module docstring). ``relative``: t, Sharpe
    and haircut are taken on net R minus the market component (``rel_r``) instead of on net R."""
    hit, r = horizon_column("hit", horizon), horizon_column("result_r", horizon)
    traded = frame.loc[frame[hit].astype(str).isin(TRADE_HITS)] if hit in frame.columns else frame.iloc[0:0]
    out = {"n": float(len(traded)), "gross_r": math.nan, "net_r": math.nan, "mkt_r": math.nan, "rel_r": math.nan,
           "win": math.nan, "blocks": 0.0, "t": math.nan, "sharpe": math.nan, "haircut_sharpe": math.nan}
    if traded.empty:
        return out
    net = traded[r].astype(float) - cost_r(traded).fillna(0.0)
    mkt = relative_r(traded, horizon)
    block = _sessions(traded["as_of"]) // horizon
    means = (net - mkt if relative else net).groupby(block).mean()
    out.update(gross_r=float(traded[r].astype(float).mean()), net_r=float(net.mean()), mkt_r=float(mkt.mean()),
               rel_r=float((net - mkt).mean()), win=float((net > 0).mean()), blocks=float(len(means)))
    if len(means) >= MIN_BLOCKS and means.std(ddof=1) > 0:
        t = float(means.mean() / means.std(ddof=1) * math.sqrt(len(means)))
        sr = t / math.sqrt(years)
        out.update(t=t, sharpe=sr, haircut_sharpe=haircut_sharpe(sr, years, n_trials)[0] if sr > 0 else sr)
    return out


def leaderboard(
    shadow: pd.DataFrame,
    windows: Iterable[Window] = WINDOWS,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    logged_trials: int = 0,
    relative: bool = True,
) -> tuple[pd.DataFrame, int]:
    """One row per (strategy, window, horizon) and the trial count used for the haircut. ``relative``: grade
    against SPY (``edge_stats``); a ledger without ``mkt_r_<h>d`` columns grades the same either way."""
    windows = list(windows)
    shadow = executable(shadow)
    strategies = sorted(set(shadow["strategy"].astype(str))) if not shadow.empty else []
    n_trials = max(int(logged_trials), len(strategies) * len(horizons) * len(windows), 1)
    as_of = pd.to_datetime(shadow["as_of"]).dt.date if not shadow.empty else pd.Series(dtype=object)
    rows = []
    for w in windows:
        in_w = shadow.loc[(as_of >= w.start) & (as_of <= w.end)] if not shadow.empty else shadow
        years = max((w.end - w.start).days / 365.25, 1e-9)
        for strat, g in in_w.groupby("strategy", sort=True) if not in_w.empty else []:
            for h in horizons:
                rows.append({"strategy": strat, "window": w.start.year, "horizon": h,
                             **edge_stats(g, h, years, n_trials, relative)})
    board = pd.DataFrame(rows)
    board.attrs["relative"] = relative
    return board, n_trials


def survivors(board: pd.DataFrame) -> pd.DataFrame:
    """(strategy, horizon) pairs with a positive haircut Sharpe in every window present."""
    if board.empty:
        return board
    n_windows = board["window"].nunique()
    ok = board.loc[board["haircut_sharpe"] > 0]
    counts = ok.groupby(["strategy", "horizon"]).size()
    keep = counts[counts == n_windows].index
    return board.set_index(["strategy", "horizon"]).loc[keep].reset_index() if len(keep) else board.iloc[0:0]


def render(board: pd.DataFrame, n_trials: int, windows: Sequence[Window] = WINDOWS) -> str:
    def f(x: float, spec: str = "+.3f") -> str:
        return "-" if x is None or not math.isfinite(x) else format(x, spec)

    relative = bool(board.attrs.get("relative", False))
    yard = (f"Yardstick: net R minus what {MARKET_SYMBOL} returned over the same days on the same dollars (`vs "
            f"{MARKET_SYMBOL}`; beta 1, dividends ignored), so a long-only strategy gets no credit for the index "
            "going up. " if relative else "Yardstick: plain net R (`--absolute`). ")
    lines = [
        "# Strategy leaderboard",
        "",
        f"Generated by `swing_engine.research.leaderboard`. Net R per signal after a per-stock round-trip cost (half the estimated spread a side, floored at 10/20 bp). "
        f"{yard}t-stats on non-overlapping blocks of the horizon; Harvey-Liu haircut over {n_trials} trials. "
        "A survivor needs a positive haircut Sharpe at the same horizon in both windows. Signals doubled under "
        "renamed tickers are counted once (`research.cards.drop_renamed`).",
        "",
        "## Survivors",
    ]
    surv = survivors(board)
    edge = "rel_r" if relative else "net_r"
    if surv.empty:
        lines.append("None. No strategy keeps a positive net edge after the multiple-testing haircut in both windows.")
    else:
        for (strat, h), g in surv.groupby(["strategy", "horizon"]):
            parts = "; ".join(f"{int(r.window)}: net {f(getattr(r, edge))}R, haircut SR {f(r.haircut_sharpe, '.2f')}"
                              for r in g.itertuples())
            lines.append(f"- **{strat}** at {h}d: {parts}")
    for w in windows:
        sub = board.loc[board["window"] == w.start.year]
        if sub.empty:
            continue
        best = sub.sort_values("t", ascending=False).drop_duplicates("strategy")
        lines += ["", f"## {w.start} .. {w.end} ({w.label})", "",
                  "Best horizon per strategy by t (picking it is itself a look, already counted in the trials).", "",
                  f"| strategy | horizon | signals | win | gross R | net R | {MARKET_SYMBOL} R | vs {MARKET_SYMBOL} | t | Sharpe | haircut SR |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in best.itertuples():
            lines.append(f"| {r.strategy} | {r.horizon}d | {int(r.n)} | {f(r.win * 100, '.0f')}% | {f(r.gross_r)} | "
                         f"{f(r.net_r)} | {f(r.mkt_r)} | {f(r.rel_r)} | {f(r.t, '.2f')} | {f(r.sharpe, '.2f')} | "
                         f"{f(r.haircut_sharpe, '.2f')} |")
    return "\n".join(lines) + "\n"


LEADERBOARD_TAG = "leaderboard"


def liquid_variant(shadow: pd.DataFrame, min_dollar_volume: float) -> pd.DataFrame:
    """Signals on names trading at least ``min_dollar_volume`` a day (20-day mean, as of the signal day), under the
    strategy name ``<slug>@liq<$M>`` so every variant is logged and haircut as its own trial."""
    keep = shadow.loc[shadow["dollar_volume"].astype(float) >= min_dollar_volume].copy()
    keep["strategy"] = keep["strategy"].astype(str) + f"@liq{min_dollar_volume / 1e6:g}"
    return keep


YARDSTICK_RELATIVE = "vs_spy"


def log_board_trials(board: pd.DataFrame) -> int:
    """Log each (strategy, window, horizon) look as a trial once, so research.metrics.multiple_testing and
    `swing backtest` deflate by every look the leaderboard took, not only the runs logged elsewhere. A look
    under the SPY yardstick is a trial of its own (``params.yardstick``): it is a second look at the same data."""
    yard = YARDSTICK_RELATIVE if board.attrs.get("relative") else None

    def key_of(name: Any, params: dict[str, Any]) -> tuple[Any, ...]:
        return (name, params.get("window"), params.get("horizon"), params.get("yardstick"))

    seen = {key_of(r.get("name"), r.get("params") or {}) for r in iter_trials()
            if LEADERBOARD_TAG in (r.get("tags") or [])}
    n = 0
    for r in board.itertuples():
        params = {"window": int(r.window), "horizon": int(r.horizon), **({"yardstick": yard} if yard else {})}
        if key_of(str(r.strategy), params) in seen:
            continue
        log_trial(str(r.strategy), params,
                  {"n": float(r.n), "net_r": float(r.net_r), "rel_r": float(r.rel_r), "t": float(r.t)},
                  tags=[LEADERBOARD_TAG], notes="research.leaderboard look (replay shadow ledger)")
        n += 1
    return n


def main(argv: Sequence[str] | None = None) -> tuple[pd.DataFrame, int]:
    from swing_engine.core.config import load_settings

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settings", default="config/replay.yaml")
    ap.add_argument("--store", action="append", default=[], help="extra replay store (repeatable)")
    ap.add_argument("--out", default="docs/leaderboard.md")
    ap.add_argument("--min-dollar-volume", type=float, default=None,
                    help="variant: only signals whose 20-day dollar volume is at least this (counted as new trials)")
    ap.add_argument("--absolute", action="store_true", help="grade plain net R instead of net R against SPY")
    args = ap.parse_args(argv)
    settings = load_settings.__wrapped__(Path(args.settings))
    shadow = with_costs(read_shadow([ROOT / settings.data.store_path, *(ROOT / s for s in args.store)]),
                        ROOT / settings.data.store_path)
    if args.min_dollar_volume is not None:
        shadow = liquid_variant(shadow, args.min_dollar_volume)
    relative = not args.absolute
    # the looks this board is about to log count in its own haircut
    board, _ = leaderboard(shadow, relative=relative)
    log_board_trials(board)
    board, n_trials = leaderboard(shadow, logged_trials=trial_count(None), relative=relative)
    (ROOT / args.out).write_text(render(board, n_trials))
    print(f"{len(board)} rows, {n_trials} trials, {len(survivors(board))} survivor rows -> {args.out}")
    return board, n_trials


if __name__ == "__main__":
    main()


__all__ = ["edge_stats", "leaderboard", "render", "survivors"]
