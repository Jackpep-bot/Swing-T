"""Grade the pre-registered three-pick group exactly as docs/preregistration/2026-10-09-three-picks.md specifies.

Inputs: the six saved replays (runs/replay/<start>_<end>_prereg3-<slug>.json) and the bars of the replay store (for
the per-stock cost top-up, research.costs). Output: a markdown table per strategy and window, the n_trials = 3
haircut and deflated Sharpe, and PASS / FAIL against the pre-registered criteria. Run::

    uv run python -m swing_engine.research.prereg_eval --settings config/prereg3.yaml
"""
from __future__ import annotations

import argparse
import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.research.cards import ROOT, WINDOWS
from swing_engine.research.costs import cost_table
from swing_engine.research.metrics import deflated_sharpe, haircut_sharpe, max_drawdown, sharpe

SLUGS = ("ath_trend_following_wide_stop", "composite_cost_aware_rank", "earnings_seasonality")
N_TRIALS = 3
REPLAY_BPS = 10.0  # already charged per side by the replay's CostModel
BPS = 1e4
TOP_TRADE_SHARE = 0.07
PERIODS = 252


def _cost_lookup(table: pd.DataFrame) -> dict[tuple[str, Any], float]:
    return {(s, d): c for s, d, c in zip(table["symbol"], table["as_of"], table["cost_bps"], strict=True)}


def grade_run(payload: dict[str, Any], costs: dict[tuple[str, Any], float]) -> dict[str, float]:
    trades = pd.DataFrame(payload.get("trades") or [])
    curve = pd.DataFrame(payload.get("equity_curve") or [])
    out: dict[str, float] = {"trades": float(len(trades))}
    if trades.empty or curve.empty:
        return out
    entry_day = pd.to_datetime(trades["signal_date"]).dt.date
    exit_day = pd.to_datetime(trades["exit_ts"]).dt.date
    top_in = [max(0.0, costs.get((s, d), REPLAY_BPS) - REPLAY_BPS) for s, d in zip(trades["symbol"], entry_day, strict=True)]
    top_out = [max(0.0, costs.get((s, d), REPLAY_BPS) - REPLAY_BPS) for s, d in zip(trades["symbol"], exit_day, strict=True)]
    qty = trades["qty"].astype(float)
    extra = (np.array(top_in) * trades["entry_price"].astype(float) * qty
             + np.array(top_out) * trades["exit_price"].astype(float) * qty) / BPS
    risk = qty * (trades["entry_price"].astype(float) - trades["initial_stop"].astype(float))
    net_r = (trades["pnl"].astype(float) - extra) / risk.where(risk > 0)
    net_r = net_r.dropna()
    eq_col = "equity" if "equity" in curve.columns else curve.columns[-1]
    day = pd.to_datetime(curve[[c for c in curve.columns if c in ("ts", "date", "day")][0]]).dt.date
    equity = pd.Series(curve[eq_col].astype(float).to_numpy(), index=day)
    booked = pd.Series(extra.to_numpy(), index=exit_day).groupby(level=0).sum()
    equity = equity - booked.reindex(equity.index, fill_value=0.0).cumsum()
    rets = equity.pct_change().dropna()
    years = len(rets) / PERIODS
    sr = sharpe(rets, PERIODS)
    pnl = (trades["pnl"].astype(float) - extra).sort_values(ascending=False)
    k = max(1, math.ceil(len(pnl) * TOP_TRADE_SHARE))
    out.update(
        net_r=float(net_r.mean()) if len(net_r) else math.nan,
        t=float(net_r.mean() / (net_r.std(ddof=1) / math.sqrt(len(net_r)))) if len(net_r) > 1 and net_r.std(ddof=1) > 0 else math.nan,
        sharpe=float(sr),
        haircut_sharpe=float(haircut_sharpe(sr, years, N_TRIALS)[0]) if math.isfinite(sr) and sr > 0 else float(sr),
        dsr=float(deflated_sharpe(sr, N_TRIALS, len(rets), float(rets.skew()), float(rets.kurt()) + 3.0)),
        max_dd=float(max_drawdown(equity)),
        hold_days=float(trades["bars_held"].astype(float).mean()),
        top7_share=float(pnl.iloc[:k].sum() / pnl.sum()) if pnl.sum() != 0 else math.nan,
        total_return=float(equity.iloc[-1] / equity.iloc[0] - 1.0),
    )
    if "exposure" in curve.columns:
        out["exposure"] = float(curve["exposure"].astype(float).mean())
    return out


def main(argv: Sequence[str] | None = None) -> None:
    from swing_engine.core.config import load_settings
    from swing_engine.data.store import Store

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settings", default="config/prereg3.yaml")
    ap.add_argument("--out", default="docs/preregistration/2026-10-09-three-picks-results.md")
    args = ap.parse_args(argv)
    settings = load_settings.__wrapped__(Path(args.settings))
    store_path = ROOT / settings.data.store_path
    runs = store_path.parent / "runs" / "replay"
    store = Store(str(store_path), read_only=True)
    try:
        bars = store.read_bars(None, min(w.start for w in WINDOWS), max(w.end for w in WINDOWS))
    finally:
        store.close()
    costs = _cost_lookup(cost_table(bars))
    lines = ["# Three-pick group: results", "", "Graded per docs/preregistration/2026-10-09-three-picks.md "
             f"(n_trials = {N_TRIALS}). Net of replay costs plus the per-stock spread top-up.", "",
             "| strategy | window | trades | net R/trade | t | net Sharpe | haircut SR | DSR | max DD | hold days | "
             "top-7% P&L share | return |", "|" + "---|" * 12]
    verdicts = {}
    for slug in SLUGS:
        ok = True
        for w in WINDOWS:
            path = runs / f"{w.start.isoformat()}_{w.end.isoformat()}_prereg3-{slug}.json"
            g = grade_run(json.loads(path.read_text()), costs) if path.exists() else {"trades": math.nan}
            ok = ok and g.get("haircut_sharpe", -1) > 0 and g.get("net_r", -1) > 0

            def f(key: str, spec: str = ".2f", g: dict[str, float] = g) -> str:
                v = g.get(key)
                return "-" if v is None or not math.isfinite(v) else format(v, spec)

            lines.append(f"| {slug} | {w.start.year} | {f('trades', '.0f')} | {f('net_r', '+.3f')} | {f('t')} | "
                         f"{f('sharpe')} | {f('haircut_sharpe')} | {f('dsr')} | {f('max_dd', '.1%')} | "
                         f"{f('hold_days', '.0f')} | {f('top7_share', '.0%')} | {f('total_return', '+.1%')} |")
        verdicts[slug] = "PASS" if ok else "FAIL"
    lines += ["", "## Verdicts", *[f"- **{s}**: {v}" for s, v in verdicts.items()]]
    (ROOT / args.out).write_text("\n".join(lines) + "\n")
    print("\n".join(lines[-4:]))


if __name__ == "__main__":
    main()
