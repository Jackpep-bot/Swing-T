"""Grade a pre-registered group exactly as its docs/preregistration/<date>-<group>.md specifies (default: the
three-pick group, docs/preregistration/2026-10-09-three-picks.md).

Inputs: the saved replays (runs/replay/<start>_<end>_<tag-prefix><slug>.json) and the bars of the replay store (for
the per-stock cost top-up, research.costs). Output: a markdown table per strategy and window, the n_trials
haircut and deflated Sharpe, and PASS / FAIL against the pre-registered criteria. Run::

    uv run python -m swing_engine.research.prereg_eval --settings config/prereg3.yaml
    uv run python -m swing_engine.research.prereg_eval --settings config/prereg2.yaml \
        --slugs high_volume_return_premium,momentum_volume_early_stage --tag-prefix prereg2- --n-trials 2 \
        --out docs/preregistration/2026-10-10-two-picks-results.md

``--benchmark SPY`` adds a second table (daily net return minus the benchmark's close-to-close return from the store:
annual excess return, information ratio and its haircut, OLS alpha / beta, exposure); the slugs in
``--benchmark-slugs`` (single-ETF timing strategies) then pass on a positive haircut information ratio in both
windows instead of the haircut Sharpe / net R rule (docs/preregistration/2026-10-10-batch2.md).
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
TAG_PREFIX = "prereg3-"
OUT = "docs/preregistration/2026-10-09-three-picks-results.md"
REPLAY_BPS = 10.0  # already charged per side by the replay's CostModel
BPS = 1e4
TOP_TRADE_SHARE = 0.07
PERIODS = 252


def _cost_lookup(table: pd.DataFrame) -> dict[tuple[str, Any], float]:
    return {(s, d): c for s, d, c in zip(table["symbol"], table["as_of"], table["cost_bps"], strict=True)}


def _vs_benchmark(rets: pd.Series, bench: pd.Series, n_trials: int) -> dict[str, float]:
    """Daily ``rets`` against the benchmark's returns ``bench`` (both indexed by session date)."""
    both = pd.DataFrame({"r": rets, "b": bench.reindex(rets.index)}).dropna()
    if len(both) < 3:
        return {}
    excess, years = both["r"] - both["b"], len(both) / PERIODS
    ir = sharpe(excess, PERIODS)
    beta, alpha = np.polyfit(both["b"], both["r"], 1)
    resid = both["r"] - alpha - beta * both["b"]
    se = float(resid.std(ddof=2)) / math.sqrt(len(both))  # s.e. of the intercept (benchmark mean ~ 0 per day)
    return {
        "excess_ann": float(excess.mean() * PERIODS),
        "ir": float(ir),
        "haircut_ir": float(haircut_sharpe(ir, years, n_trials)[0]) if math.isfinite(ir) and ir > 0 else float(ir),
        "alpha_ann": float(alpha * PERIODS),
        "alpha_t": float(alpha / se) if se > 0 else math.nan,
        "beta": float(beta),
        "bench_sharpe": float(sharpe(both["b"], PERIODS)),
    }


def grade_run(payload: dict[str, Any], costs: dict[tuple[str, Any], float], n_trials: int = N_TRIALS,
              benchmark: pd.Series | None = None) -> dict[str, float]:
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
        haircut_sharpe=float(haircut_sharpe(sr, years, n_trials)[0]) if math.isfinite(sr) and sr > 0 else float(sr),
        dsr=float(deflated_sharpe(sr, n_trials, len(rets), float(rets.skew()), float(rets.kurt()) + 3.0)),
        max_dd=float(max_drawdown(equity)),
        hold_days=float(trades["bars_held"].astype(float).mean()),
        top7_share=float(pnl.iloc[:k].sum() / pnl.sum()) if pnl.sum() != 0 else math.nan,
        total_return=float(equity.iloc[-1] / equity.iloc[0] - 1.0),
    )
    if "exposure" in curve.columns:
        out["exposure"] = float(curve["exposure"].astype(float).mean())
    if benchmark is not None:
        out.update(_vs_benchmark(rets, benchmark.reindex(equity.index).pct_change(), n_trials))
    return out


def build_report(runs: Path, costs: dict[tuple[str, Any], float], slugs: Sequence[str] = SLUGS,
                 tag_prefix: str = TAG_PREFIX, n_trials: int = N_TRIALS, out: str = OUT,
                 benchmark: pd.Series | None = None, benchmark_slugs: Sequence[str] = (),
                 benchmark_name: str = "benchmark") -> list[str]:
    """Markdown lines: one row per strategy and window, then the PASS / FAIL verdicts. With ``benchmark`` (close
    by date) a second table reports every strategy against it, and ``benchmark_slugs`` pass on a positive haircut
    information ratio in both windows instead of the absolute rule."""
    title = "Three-pick group" if tuple(slugs) == SLUGS else f"Pre-registered group of {len(slugs)}"
    lines = [f"# {title}: results", "", f"Graded per {out.replace('-results.md', '.md')} "
             f"(n_trials = {n_trials}). Net of replay costs plus the per-stock spread top-up.", "",
             "| strategy | window | trades | net R/trade | t | net Sharpe | haircut SR | DSR | max DD | hold days | "
             "top-7% P&L share | return |", "|" + "---|" * 12]
    verdicts = {}
    versus: list[str] = []
    for slug in slugs:
        ok = True
        for w in WINDOWS:
            path = runs / f"{w.start.isoformat()}_{w.end.isoformat()}_{tag_prefix}{slug}.json"
            g = (grade_run(json.loads(path.read_text()), costs, n_trials, benchmark) if path.exists()
                 else {"trades": math.nan})
            if benchmark is not None and slug in benchmark_slugs:
                ok = ok and g.get("haircut_ir", -1) > 0
            else:
                ok = ok and g.get("haircut_sharpe", -1) > 0 and g.get("net_r", -1) > 0

            def f(key: str, spec: str = ".2f", g: dict[str, float] = g) -> str:
                v = g.get(key)
                return "-" if v is None or not math.isfinite(v) else format(v, spec)

            lines.append(f"| {slug} | {w.start.year} | {f('trades', '.0f')} | {f('net_r', '+.3f')} | {f('t')} | "
                         f"{f('sharpe')} | {f('haircut_sharpe')} | {f('dsr')} | {f('max_dd', '.1%')} | "
                         f"{f('hold_days', '.0f')} | {f('top7_share', '.0%')} | {f('total_return', '+.1%')} |")
            versus.append(f"| {slug} | {w.start.year} | {f('excess_ann', '+.1%')} | {f('ir')} | {f('haircut_ir')} | "
                          f"{f('alpha_ann', '+.1%')} | {f('alpha_t')} | {f('beta')} | {f('exposure', '.0%')} | "
                          f"{f('sharpe')} | {f('bench_sharpe')} |")
        verdicts[slug] = "PASS" if ok else "FAIL"
    if benchmark is not None:
        lines += ["", f"## Against buy-and-hold {benchmark_name}", "",
                  f"Daily net return minus {benchmark_name} close-to-close return on the same sessions. Pass rule for "
                  f"{', '.join(benchmark_slugs) or 'no strategy'}: positive haircut IR in both windows; the columns "
                  "are information only for the others.", "",
                  "| strategy | window | excess / yr | IR | haircut IR | alpha / yr | alpha t | beta | exposure | "
                  f"net Sharpe | {benchmark_name} Sharpe |", "|" + "---|" * 11, *versus]
    return [*lines, "", "## Verdicts", *[f"- **{s}**: {v}" for s, v in verdicts.items()]]


def _bar_days(ts: pd.Series) -> list[Any]:
    """Session date of each bar (tz-aware stamps are read in New York, like the replay's equity curve)."""
    t = pd.to_datetime(ts)
    return list((t.dt.tz_convert("America/New_York") if t.dt.tz is not None else t).dt.date)


def main(argv: Sequence[str] | None = None) -> None:
    from swing_engine.core.config import load_settings
    from swing_engine.data.store import Store

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settings", default="config/prereg3.yaml")
    ap.add_argument("--slugs", default=",".join(SLUGS), help="comma-separated strategy slugs of the group")
    ap.add_argument("--tag-prefix", default=TAG_PREFIX, help="replay --tag was <tag-prefix><slug>")
    ap.add_argument("--n-trials", type=int, default=N_TRIALS, help="group size for the haircut and deflated Sharpe")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--benchmark", default=None, help="store symbol to report excess returns against (e.g. SPY)")
    ap.add_argument("--benchmark-slugs", default="", help="slugs whose pass rule is the haircut IR vs --benchmark")
    args = ap.parse_args(argv)
    slugs = tuple(s.strip() for s in args.slugs.split(",") if s.strip())
    bench_slugs = tuple(s.strip() for s in args.benchmark_slugs.split(",") if s.strip())
    if bench_slugs and not args.benchmark:
        ap.error("--benchmark-slugs needs --benchmark")
    if set(bench_slugs) - set(slugs):
        ap.error(f"--benchmark-slugs not in --slugs: {sorted(set(bench_slugs) - set(slugs))}")
    settings = load_settings.__wrapped__(Path(args.settings))
    store_path = ROOT / settings.data.store_path
    store = Store(str(store_path), read_only=True)
    try:
        bars = store.read_bars(None, min(w.start for w in WINDOWS), max(w.end for w in WINDOWS))
    finally:
        store.close()
    benchmark = None
    if args.benchmark:
        b = bars.loc[bars["symbol"] == args.benchmark]
        if b.empty:
            raise SystemExit(f"no {args.benchmark} bars in {store_path}")
        benchmark = pd.Series(b["close"].astype(float).to_numpy(), index=_bar_days(b["ts"])).sort_index()
    lines = build_report(store_path.parent / "runs" / "replay", _cost_lookup(cost_table(bars)), slugs,
                         args.tag_prefix, args.n_trials, args.out, benchmark, bench_slugs, args.benchmark or "")
    (ROOT / args.out).write_text("\n".join(lines) + "\n")
    print("\n".join(lines[-(len(slugs) + 1):]))


if __name__ == "__main__":
    main()
