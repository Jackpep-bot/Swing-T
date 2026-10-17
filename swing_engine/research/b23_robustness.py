"""Batch 23 (docs/preregistration/2026-10-14-batch23.md is the spec): a robustness pass on batch 9's
`sp500_momentum_index_replica` (variant R). Not a trial; nothing here re-grades the replica or touches the shadow book.

Timing variants (six reference-month pairs and the six-tranche book), one-at-a-time neighbouring settings, cost stress,
a stationary block bootstrap of R's daily returns against SPY, and total-return figures; read by the rule fixed in the
pre-registration (robust / mixed / fragile).

    uv run python -m swing_engine.research.b23_robustness --settings config/prereg_b9.yaml
"""
from __future__ import annotations

import argparse
import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.config import ROOT
from swing_engine.data.calendar import trading_days
from swing_engine.research import b9_books as b9
from swing_engine.research import b11_books as b11
from swing_engine.research import b12_books as b12
from swing_engine.research.b17_books import _load
from swing_engine.research.costs import cost_table

SPEC = "docs/preregistration/2026-10-14-batch23.md"
OUT = "docs/preregistration/2026-10-14-batch23-results.md"
MARKET = "SPY"
N_TRIALS = b9.N_GROUP_TRIALS  # the replica's own grading; this pass logs no trial
TIMING = ((1, 7), (2, 8), (3, 9), (4, 10), (5, 11), (6, 12))  # card; (2, 8) is R
COST_MULTS = (2.0, 3.0)  # card
BOOT_DRAWS, BOOT_BLOCK, BOOT_SEED = 10_000, 21, 20261014  # card
ROBUST_ALPHA, FRAGILE_ALPHA, MIN_POSITIVE, FRAGILE_NONPOSITIVE = 0.0245, 0.01, 5, 3  # card's reading rule


@dataclass(frozen=True)
class Variant:
    """The replica's knobs (defaults = R, batch 9 as registered)."""
    ref_months: tuple[int, ...] = b9.REF_MONTHS
    lookback_months: int = b9.LOOKBACK_MONTHS
    vol_scale: bool = True
    tilt: bool = True
    hold: int = b9.HOLD_N
    enter: int = b9.ENTER_RANK
    stay: int = b9.KEEP_RANK


R = Variant()
SETTINGS: dict[str, Variant] = {  # card: one change at a time from R
    "50 names (enter 40, stay 60)": replace(R, hold=50, enter=40, stay=60),
    "150 names (enter 120, stay 180)": replace(R, hold=150, enter=120, stay=180),
    "6-1 month look-back": replace(R, lookback_months=7),
    "no volatility scaling": replace(R, vol_scale=False),
    "no score tilt (mcap weights)": replace(R, tilt=False),
    "quarterly (Feb / May / Aug / Nov)": replace(R, ref_months=(2, 5, 8, 11)),
}


def values(closes: pd.DataFrame, ref: date, v: Variant) -> pd.Series:
    """b9.momentum_values with the variant's look-back and volatility scaling (identical for R)."""
    idx = closes.index
    ref_ts = pd.Timestamp(ref)
    end = idx[idx <= (ref_ts - pd.DateOffset(months=b9.SKIP_MONTHS)).date()]
    start = idx[idx <= (ref_ts - pd.DateOffset(months=v.lookback_months)).date()]
    if not len(end) or not len(start):
        return pd.Series(dtype=float)
    span = closes.loc[start[-1]:end[-1]]
    hist = closes.loc[:ref].notna().sum()
    value = span.iloc[-1] / span.iloc[0] - 1.0
    if v.vol_scale:
        value = value / span.pct_change(fill_method=None).iloc[1:].std(ddof=1)
    return value.where(hist >= b9.MIN_HISTORY).replace([np.inf, -np.inf], np.nan).dropna()


def orders_for(closes: pd.DataFrame, mcap_at: Any, sessions: Sequence[date], v: Variant) -> dict[date, pd.Series]:
    """b9.momentum_orders under the variant; SPY from the first session until the first book."""
    s = pd.Series(sessions, index=pd.to_datetime(sessions))
    refs = [d for (_, m), d in s.groupby([s.index.year, s.index.month]).last().items() if m in v.ref_months]
    orders: dict[date, pd.Series] = {sessions[0]: pd.Series({MARKET: 1.0})}
    current: set[str] = set()
    for ref in refs:
        day = b12._after_third_friday(ref, sessions)
        vals = values(closes, ref, v)
        mcap = mcap_at(ref).reindex(vals.index).dropna()
        if day is None or len(mcap) < b9.UNIVERSE_N:
            continue
        uni = mcap.sort_values(ascending=False, kind="mergesort").iloc[:b9.UNIVERSE_N]
        z, score = b9.scores(vals.reindex(uni.index))
        held = b9.select(z, current, v.hold, v.enter, v.stay)
        caps = b9.caps_for((uni / uni.sum()).reindex(held))
        raw = uni.reindex(held) * (score.reindex(held) if v.tilt else 1.0)
        orders[day] = b9.capped_weights(raw, caps)
        current = set(held)
    return orders


def tranched(books: Sequence[pd.DataFrame]) -> pd.DataFrame:
    """Equal starting capital in each book, never rebalanced between them: the combined book's daily figures."""
    value = pd.concat([(1.0 + b["ret"]).cumprod() for b in books], axis=1)
    prev = value.shift(1).fillna(1.0)
    share = prev.div(prev.sum(axis=1), axis=0)
    total = value.mean(axis=1)
    out = pd.DataFrame({"ret": total / total.shift(1).fillna(1.0) - 1.0}, index=value.index)
    for col in ("cost", "turnover", "n_held"):
        out[col] = (pd.concat([b[col] for b in books], axis=1).to_numpy() * share.to_numpy()).sum(axis=1)
    return out


def bootstrap_alpha(book: pd.Series, spy: pd.Series, bill: pd.Series, draws: int = BOOT_DRAWS,
                    block: int = BOOT_BLOCK, seed: int = BOOT_SEED) -> np.ndarray:
    """Stationary bootstrap (Politis-Romano, mean block ``block``) of the paired daily (book, SPY, BIL) returns; the
    annual alpha of (r - BIL) on (SPY - BIL) per draw."""
    both = pd.DataFrame({"r": book, "b": spy.reindex(book.index), "f": bill.reindex(book.index).fillna(0.0)}).dropna()
    y, x = (both["r"] - both["f"]).to_numpy(), (both["b"] - both["f"]).to_numpy()
    n, rng = len(y), np.random.default_rng(seed)
    out = np.empty(draws)
    for start in range(0, draws, 500):
        k = min(500, draws - start)
        idx = np.empty((k, n), dtype=np.int64)
        idx[:, 0] = rng.integers(0, n, k)
        jump = rng.random((k, n)) < 1.0 / block
        fresh = rng.integers(0, n, (k, n))
        for t in range(1, n):
            idx[:, t] = np.where(jump[:, t], fresh[:, t], (idx[:, t - 1] + 1) % n)
        ys, xs = y[idx], x[idx]
        xm, ym = xs.mean(axis=1, keepdims=True), ys.mean(axis=1, keepdims=True)
        beta = ((xs - xm) * (ys - ym)).sum(axis=1) / ((xs - xm) ** 2).sum(axis=1)
        out[start:start + k] = (ym[:, 0] - beta * xm[:, 0]) * 252.0
    return out


def reading(tranche_alpha: float, timing_alphas: Sequence[float], setting_alphas: Sequence[float]) -> str:
    """The card's rule, fixed before the run."""
    pos_t = sum(a > 0 for a in timing_alphas)
    if tranche_alpha < FRAGILE_ALPHA or len(timing_alphas) - pos_t >= FRAGILE_NONPOSITIVE:
        return "FRAGILE"
    if tranche_alpha >= ROBUST_ALPHA and pos_t >= MIN_POSITIVE and sum(a > 0 for a in setting_alphas) >= MIN_POSITIVE:
        return "ROBUST"
    return "MIXED"


def run(store_path: str | Path, out: str | Path = OUT, counts_only: bool = False,
        tr_store_path: str | Path | None = None) -> dict[str, Any]:
    from swing_engine.data.store import Store

    bars, closes, opens, delist, _f, _s = _load(store_path)
    end = b11.WINDOWS["pooled"][1]
    sessions = [d for d in trading_days(b9.DATA_START, end) if d in closes.index]
    cache: dict[date, pd.Series] = {}
    with Store(str(store_path), read_only=True) as store:
        base = b9.mcap_function(store, bars, closes)

        def mcap_at(ref: date) -> pd.Series:
            if ref not in cache:
                cache[ref] = base(ref)
            return cache[ref]

        plans = {f"timing {a:02d}/{b:02d}": orders_for(closes, mcap_at, sessions, replace(R, ref_months=(a, b)))
                 for a, b in TIMING}
        plans.update({name: orders_for(closes, mcap_at, sessions, v) for name, v in SETTINGS.items()})
        registered = b9.momentum_orders(closes, mcap_at, sessions)
    r_plan = plans["timing 02/08"]
    same = set(registered) == set(r_plan) - {sessions[0]} and all(
        registered[d].sort_index().round(12).equals(r_plan[d].sort_index().round(12)) for d in registered)
    if counts_only:
        print("R reproduces batch 9's registered orders:", same, flush=True)
        for name, o in plans.items():
            books = [w for d, w in o.items() if d != sessions[0]]
            print(name, "rebalances", len(books), "first", min(d for d in o if d != sessions[0]), "names",
                  min(map(len, books)), max(map(len, books)), flush=True)
        return {}
    if not same:
        raise RuntimeError("variant R does not reproduce batch 9's registered orders")
    traded = sorted({s for o in plans.values() for w in o.values() for s in w.index} | {MARKET, b11.BILL})
    costs = cost_table(bars.loc[bars["symbol"].isin(traded)]).pivot(index="as_of", columns="symbol", values="cost_bps")
    spy, rf = closes[MARKET].pct_change(fill_method=None), closes[b11.BILL].pct_change(fill_method=None)

    def grade_all(o: dict[date, pd.Series], c: pd.DataFrame = costs) -> dict[str, Any]:
        books = {w: b11.book_for(o, opens, closes, c, delist, lo, hi) for w, (lo, hi) in b11.WINDOWS.items()}
        return {"books": books, **{w: b9.grade(b, spy, N_TRIALS, rf) for w, b in books.items()}}

    graded = {name: grade_all(o) for name, o in plans.items()}
    timing_names = [f"timing {a:02d}/{b:02d}" for a, b in TIMING]
    tranche = {w: b9.grade(tranched([graded[n]["books"][w] for n in timing_names]), spy, N_TRIALS, rf)
               for w in b11.WINDOWS}
    stress = {m: grade_all(r_plan, costs * m) for m in COST_MULTS}
    boot = bootstrap_alpha(graded["timing 02/08"]["books"]["pooled"]["ret"], spy, rf)
    tr: dict[str, dict[str, Any]] = {}
    if tr_store_path is not None and Path(tr_store_path).exists():
        _b, tc, to, tdel, _f2, _s2 = _load(tr_store_path)
        tspy, trf = tc[MARKET].pct_change(fill_method=None), tc[b11.BILL].pct_change(fill_method=None)
        tbooks = [b11.book_for(plans[n], to, tc, costs, tdel, *b11.WINDOWS["pooled"]) for n in timing_names]
        tr = {"R": b9.grade(tbooks[1], tspy, N_TRIALS, trf), "six-tranche": b9.grade(tranched(tbooks), tspy, N_TRIALS, trf)}

    def a(g: dict[str, Any]) -> float:
        return float(g["vs"].get("alpha_ann", math.nan))

    def row(name: str, g: dict[str, Any]) -> str:
        p = g["pooled"]
        return (f"| {name} | {b9._pct(p['stats']['cagr'])} | {b9._pct(-p['stats']['max_dd'])} | {b9._pct(a(p))} | "
                f"{p['vs'].get('alpha_t', math.nan):.2f} | {b9._pct(a(g['A']))} | {b9._pct(a(g['B']))} | "
                f"{b9._pct(p['turnover_ann'], '.0%')} |")

    t_alphas = [a(graded[n]["pooled"]) for n in timing_names]
    s_alphas = [a(graded[n]["pooled"]) for n in SETTINGS]
    word = reading(a(tranche["pooled"]), t_alphas, s_alphas)
    head = "| book | return/yr | deepest drop | alpha/yr | alpha t | alpha A | alpha B | turnover/yr |"
    lines = ["# Batch 23 results: robustness of the momentum replica", "",
             f"Spec: `{SPEC}`. Generated by `swing_engine.research.b23_robustness`; net of costs, price-only bars, alpha "
             "from (book - BIL) on (SPY - BIL), pooled window 2017-01-01 .. 2026-10-05 unless named. Not a trial; the "
             "replica's verdict and the shadow book are unchanged. Variant R reproduces batch 9's registered orders "
             "exactly (checked in the run).", "",
             f"## Reading: **{word}**", "",
             f"Six-tranche pooled alpha {b9._pct(a(tranche['pooled']))} (robust needs >= {ROBUST_ALPHA:.2%}; fragile under "
             f"{FRAGILE_ALPHA:.0%}); timing variants with alpha > 0: {sum(x > 0 for x in t_alphas)} of 6; neighbouring "
             f"settings with alpha > 0: {sum(x > 0 for x in s_alphas)} of 6.", "",
             "## 1. Timing luck", "", head, "|---|---|---|---|---|---|---|---|",
             *[row(n + (" (= R)" if n == "timing 02/08" else ""), graded[n]) for n in timing_names],
             row("six-tranche book", tranche), "",
             f"Median timing-variant alpha {b9._pct(float(np.median(t_alphas)))}, range {b9._pct(min(t_alphas))} .. "
             f"{b9._pct(max(t_alphas))}.", "",
             "## 2. Neighbouring settings (one change from R)", "", head, "|---|---|---|---|---|---|---|---|",
             *[row(n, graded[n]) for n in SETTINGS], "",
             "## 3. Cost stress (R)", "", head, "|---|---|---|---|---|---|---|---|",
             row("R, costs x1", graded["timing 02/08"]), *[row(f"R, costs x{m:g}", stress[m]) for m in COST_MULTS], "",
             "## 4. Stationary block bootstrap (R, pooled)", "",
             f"{BOOT_DRAWS:,} draws, mean block {BOOT_BLOCK} sessions, seed {BOOT_SEED}, paired (book, SPY, BIL) days: "
             f"annual alpha 5th / 50th / 95th percentile {b9._pct(float(np.percentile(boot, 5)))} / "
             f"{b9._pct(float(np.percentile(boot, 50)))} / {b9._pct(float(np.percentile(boot, 95)))}; share of draws "
             f"with alpha <= 0: {float((boot <= 0).mean()):.1%}.", "",
             "## 5. Total-return store (descriptive)", ""]
    if tr:
        lines += ["| book | return/yr | SPY return/yr | alpha/yr | alpha t |", "|---|---|---|---|---|",
                  *[f"| {k} | {b9._pct(g['stats']['cagr'])} | {b9._pct(g['spy_stats']['cagr'])} | {b9._pct(a(g))} | "
                    f"{g['vs'].get('alpha_t', math.nan):.2f} |" for k, g in tr.items()]]
    else:
        lines.append("Not run (no total-return store).")
    if word == "FRAGILE":
        lines += ["", "Per the card: the weekly report should say the shadow book's backtest likely overstates it."]
    path = Path(out) if Path(out).is_absolute() else ROOT / out
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)
    return {"reading": word}


def main(argv: Sequence[str] | None = None) -> None:
    from swing_engine.core.config import load_settings

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settings", default="config/prereg_b9.yaml")
    ap.add_argument("--tr-settings", default="config/prereg_b9_tr.yaml")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--counts-only", action="store_true", help="harness check: order counts and the R reproduction")
    args = ap.parse_args(argv)
    store = ROOT / load_settings.__wrapped__(Path(args.settings)).data.store_path
    tr = ROOT / load_settings.__wrapped__(Path(args.tr_settings)).data.store_path
    run(store, args.out, counts_only=args.counts_only, tr_store_path=tr)


if __name__ == "__main__":
    main()
