"""Grade docs/preregistration/2026-10-10-walkforward-ensemble.md: select on 2017-24, test the pooled signals on 2024-26.

    uv run python -m swing_engine.research.walkforward_ensemble --settings config/replay_r2.yaml \
        --store data/live/replay_r1.duckdb --store data/live/replay_news.duckdb
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from swing_engine.research.cards import ROOT, WINDOWS, executable, read_shadow, with_costs
from swing_engine.research.leaderboard import edge_stats

HORIZON = 20
MIN_T = 2.0
EXCLUDED = ("ath_trend_following_wide_stop", "composite_cost_aware_rank", "earnings_seasonality",
            "high_volume_return_premium", "momentum_volume_early_stage")
OUT = "docs/preregistration/2026-10-10-walkforward-ensemble-results.md"
OUT_CELLS = "docs/preregistration/2026-10-10-walkforward-regime-cells-results.md"
CELL_SEP = "|"
CELL_MIN_SIGNALS = 200  # docs/preregistration/2026-10-10-walkforward-regime-cells.md


def _window(frame: pd.DataFrame, i: int) -> tuple[pd.DataFrame, float]:
    w = WINDOWS[i]
    d = pd.to_datetime(frame["as_of"]).dt.date
    return frame.loc[(d >= w.start) & (d <= w.end)], (w.end - w.start).days / 365.25


def by_regime(shadow: pd.DataFrame) -> pd.DataFrame:
    """Relabel each signal's strategy as ``<strategy>|<regime>`` so the same selection works per regime cell."""
    regime = shadow["regime"].fillna("unknown").astype(str)
    return shadow.assign(strategy=shadow["strategy"].astype(str) + CELL_SEP + regime)


def select(shadow: pd.DataFrame, min_signals: int = 0) -> dict[str, dict[str, float]]:
    """Base strategies with net R > 0 and block t >= MIN_T at HORIZON in the selection window (WINDOWS[1])."""
    sel, years = _window(shadow, 1)
    out = {}
    for name, g in sel.groupby("strategy"):
        base_name = str(name).split(CELL_SEP)[0]
        if base_name in EXCLUDED or "@" in base_name or base_name.endswith("_no_news"):
            continue
        s = edge_stats(g, HORIZON, years, 1)
        if s["net_r"] > 0 and s["t"] >= MIN_T and s["n"] >= min_signals:
            out[str(name)] = s
    return out


def main(argv: Sequence[str] | None = None) -> None:
    from swing_engine.core.config import load_settings

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settings", default="config/replay_r2.yaml")
    ap.add_argument("--store", action="append", default=[])
    ap.add_argument("--by-regime", action="store_true", help="select (strategy, regime) cells instead of strategies")
    args = ap.parse_args(argv)
    base = ROOT / load_settings.__wrapped__(Path(args.settings)).data.store_path
    shadow = executable(with_costs(read_shadow([base, *(ROOT / s for s in args.store)]), base))
    if args.by_regime:
        shadow = by_regime(shadow)
    chosen = select(shadow, CELL_MIN_SIGNALS if args.by_regime else 0)
    pooled = shadow.loc[shadow["strategy"].isin(chosen)]
    lines = ["# Walk-forward ensemble: result", "",
             "Graded per docs/preregistration/2026-10-10-walkforward-ensemble.md (20-session horizon, n_trials = 1).", "",
             f"Selected on 2017-24 (net R > 0 and block t >= {MIN_T}): "
             + (", ".join(f"{k} (t {v['t']:.2f}, net {v['net_r']:+.3f}R, n {int(v['n'])})" for k, v in chosen.items()) or "none"),
             "", "| window | signals | net R/signal | block t | Sharpe | haircut SR |", "|---|---|---|---|---|---|"]
    verdict = "FAIL"
    for i, label in ((1, "2017-24 (selection, in-sample)"), (0, "2024-26 (test)")):
        frame, years = _window(pooled, i)
        s = edge_stats(frame, HORIZON, years, 1) if not frame.empty else {"n": 0, "net_r": float("nan"), "t": float("nan"),
                                                                           "sharpe": float("nan"), "haircut_sharpe": float("nan")}
        lines.append(f"| {label} | {int(s['n'])} | {s['net_r']:+.3f} | {s['t']:.2f} | {s['sharpe']:.2f} | {s['haircut_sharpe']:.2f} |")
        if i == 0 and chosen and s["net_r"] > 0 and s["t"] >= MIN_T:
            verdict = "PASS"
    lines += ["", f"## Verdict: {verdict}"]
    (ROOT / (OUT_CELLS if args.by_regime else OUT)).write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
