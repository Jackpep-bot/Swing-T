"""Batch 21 (docs/preregistration/2026-10-14-batch21.md is the spec; this module implements it and nothing else):

* `sp500_earnings_disappointment_exclusion` (weights card): batch 19's universe and earnings-surprise signal; the 500
  largest at cap weight minus the 100 lowest surprises (excluded names return only above the 130th lowest; names with
  no eligible surprise stay), each capped at 10%; SPY before the first rebalance.

Run once::

    uv run python -m swing_engine.research.b21_books --settings config/prereg_b9.yaml
"""
from __future__ import annotations

import argparse
import math
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.config import ROOT
from swing_engine.research import b9_books as b9
from swing_engine.research import b11_books as b11
from swing_engine.research import b13_books as b13
from swing_engine.research.b17_books import _load
from swing_engine.research.b19_books import build_universes
from swing_engine.research.costs import cost_table
from swing_engine.research.prereg_eval import alpha_t_critical
from swing_engine.research.trials import DEFAULT_TRIALS_PATH, iter_trials, log_trial

SPEC = "docs/preregistration/2026-10-14-batch21.md"
OUT = "docs/preregistration/2026-10-14-batch21-results.md"
TAG = "prereg-b21"
CARD = "sp500_earnings_disappointment_exclusion"
N_TRIALS = 3  # card: earnings-surprise family count 3; bar alpha_t_critical(3)
MARKET = "SPY"
WORST, BUFFER, MAX_WEIGHT = 100, 130, 0.10  # card


def plan(universes: dict[date, pd.DataFrame], first_day: date
         ) -> tuple[dict[date, pd.Series], dict[date, pd.Series], dict[date, float]]:
    """(book, excluded names cap-weighted, excluded share of the universe's cap) per rebalance session."""
    book: dict[date, pd.Series] = {first_day: pd.Series({MARKET: 1.0})}
    gone_book: dict[date, pd.Series] = {}
    share: dict[date, float] = {}
    excluded: set[str] = set()
    for day in sorted(universes):
        u = universes[day]
        excluded = b13.exclude(-u["surprise"], excluded, WORST, BUFFER)  # b13.exclude: highest score = worst
        keep = u.loc[~u.index.isin(excluded), "mcap_pit"]
        book[day] = b9.capped_weights(keep, pd.Series(MAX_WEIGHT, index=keep.index))
        gone = u.loc[u.index.isin(excluded), "mcap_pit"]
        if len(gone):
            gone_book[day] = gone / gone.sum()
        share[day] = float(gone.sum() / u["mcap_pit"].sum())
    return book, gone_book, share


def run(store_path: str | Path, out: str | Path = OUT, trials_path: str | Path = DEFAULT_TRIALS_PATH,
        counts_only: bool = False, tr_store_path: str | Path | None = None) -> dict[str, Any]:
    bars, closes, opens, delist, sessions, universes = build_universes(store_path)
    orders, gone, share = plan(universes, sessions[0])
    if counts_only:
        books = [w for d, w in orders.items() if d != sessions[0]]
        sizes = [len(w) for w in books]
        out_n = [len(w) for w in gone.values()]
        moved = [len(set(gone[b].index) ^ set(gone[a].index)) // 2 for a, b in zip(sorted(gone), sorted(gone)[1:],
                                                                                   strict=False)]
        print(CARD, "rebalances", len(books), "first", min(d for d in orders if d != sessions[0]), "held min/median/max",
              min(sizes), int(np.median(sizes)), max(sizes), "excluded median", int(np.median(out_n)),
              "excluded names changed per rebalance median", int(np.median(moved)), "excluded cap share median",
              round(float(np.median(list(share.values()))), 3), "largest weight",
              round(max(float(w.max()) for w in books), 3), flush=True)
        return {}
    traded = sorted({s for p in (orders, gone) for w in p.values() for s in w.index} | {MARKET, b11.BILL})
    costs = cost_table(bars.loc[bars["symbol"].isin(traded)]).pivot(index="as_of", columns="symbol", values="cost_bps")
    spy, rf = closes[MARKET].pct_change(fill_method=None), closes[b11.BILL].pct_change(fill_method=None)
    books = {w: b11.book_for(orders, opens, closes, costs, delist, lo, hi) for w, (lo, hi) in b11.WINDOWS.items()}
    res = {w: b9.grade(book, spy, N_TRIALS, rf) for w, book in books.items()}
    tr: dict[str, dict[str, Any]] = {}
    if tr_store_path is not None and Path(tr_store_path).exists():
        _b, tc, to, tdel, _f, _s = _load(tr_store_path)
        tspy, trf = tc[MARKET].pct_change(fill_method=None), tc[b11.BILL].pct_change(fill_method=None)
        tr = {w: b9.grade(b11.book_for(orders, to, tc, costs, tdel, lo, hi), tspy, N_TRIALS, trf)
              for w, (lo, hi) in b11.WINDOWS.items()}
    extra = ["## Descriptive (not part of the verdict)", "",
             f"Average share of the universe's cap excluded: {np.mean(list(share.values())):.1%}.", "",
             "| window | tracking error vs SPY | excluded names cap-weighted: return/yr, alpha/yr (t) | total-return store: "
             "book return/yr, SPY return/yr, alpha/yr (t) |", "|---|---|---|---|"]
    for w, (lo, hi) in b11.WINDOWS.items():
        book = books[w]
        ex = book["ret"] - spy.reindex(book.index)
        g = b9.grade(b11.book_for(gone, opens, closes, costs, delist, lo, hi), spy, N_TRIALS, rf)
        t = tr.get(w)
        tr_text = (f"{b9._pct(t['stats']['cagr'])}, {b9._pct(t['spy_stats']['cagr'])}, "
                   f"{b9._pct(t['vs'].get('alpha_ann', math.nan))} ({t['vs'].get('alpha_t', math.nan):.2f})") if t else "not run"
        extra.append(f"| {w} | {ex.std(ddof=1) * math.sqrt(252):.1%} | {b9._pct(g['stats']['cagr'])}, "
                     f"{b9._pct(g['vs'].get('alpha_ann', math.nan))} ({g['vs'].get('alpha_t', math.nan):.2f}) | {tr_text} |")
    if not any(TAG in (r.get("tags") or []) for r in iter_trials(trials_path)):
        log_trial(CARD, {"windows": {w: [str(lo), str(hi)] for w, (lo, hi) in b11.WINDOWS.items()}, "spec": SPEC,
                         "n_trials": N_TRIALS}, {**res["pooled"]["stats"], **res["pooled"]["vs"]}, trials_path,
                  tags=[TAG], notes=f"pre-registered batch 21 card; verdict {b11.verdict(res, N_TRIALS)[1]}")
    routes, word = b11.verdict(res, N_TRIALS)
    lines = ["# Batch 21 results", "", f"Spec: `{SPEC}`. Generated by `swing_engine.research.b21_books`; net of costs, "
             f"price-only bars; alpha from (book - BIL) on (SPY - BIL). Earnings-surprise family trials {N_TRIALS}, bar "
             f"alpha t >= {alpha_t_critical(N_TRIALS):.3f}.", "",
             f"## `{CARD}`: {word}", "", f"Route 1 (both halves): {'met' if routes[0] else 'not met'}. Route 2 "
             f"(pooled, alpha > 0 in each half): {'met' if routes[1] else 'not met'}.", "",
             "| window | from | book | return/yr | deepest drop | worst month | months up | Sharpe | haircut SR | "
             "alpha/yr | alpha t | beta | turnover/yr | costs/yr |", "|" + "---|" * 14]
    for w, r in res.items():
        for label, st in (("book", r["stats"]), ("SPY", r["spy_stats"])):
            vs = r["vs"] if label == "book" else {}
            tail = (f"{st['haircut_sharpe']:.2f} | {b9._pct(vs.get('alpha_ann', math.nan))} | "
                    f"{vs.get('alpha_t', math.nan):.2f} | {vs.get('beta', math.nan):.2f} | "
                    f"{b9._pct(r['turnover_ann'], '.0%')} | {b9._pct(r['cost_ann'], '.2%')} |") if label == "book" else "| | | | | |"
            lines.append(f"| {w} | {r['start']} | {label} | {b9._pct(st['cagr'])} | {b9._pct(-st['max_dd'])} | "
                         f"{b9._pct(st['worst_month'])} | {b9._pct(st['months_up'], '.0%')} | {st['sharpe']:.2f} | " + tail)
    lines += ["", *extra, "", "## Verdict", f"- **{CARD}**: {word}"]
    path = Path(out) if Path(out).is_absolute() else ROOT / out
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)
    return res


def main(argv: Sequence[str] | None = None) -> None:
    from swing_engine.core.config import load_settings

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settings", default="config/prereg_b9.yaml")
    ap.add_argument("--tr-settings", default="config/prereg_b9_tr.yaml", help="total-return store, descriptive only")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--counts-only", action="store_true", help="harness check: book counts only, no graded simulation")
    args = ap.parse_args(argv)
    store = ROOT / load_settings.__wrapped__(Path(args.settings)).data.store_path
    tr = ROOT / load_settings.__wrapped__(Path(args.tr_settings)).data.store_path
    run(store, args.out, counts_only=args.counts_only, tr_store_path=tr)


if __name__ == "__main__":
    main()
