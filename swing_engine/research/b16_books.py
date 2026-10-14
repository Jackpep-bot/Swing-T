"""Batch 16 (docs/preregistration/2026-10-14-batch16.md is the spec; this module implements it and nothing else):

* `sp500_momentum_profitability_replica` (weights card): batch 9's replica with one change, the score: z of
  (momentum z + gross profitability z) / 2; names without gross profit get g = 0. SPY before March 2017.

Run once::

    uv run python -m swing_engine.research.b16_books --settings config/prereg_b9.yaml
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
from swing_engine.data.calendar import trading_days
from swing_engine.research import b9_books as b9
from swing_engine.research import b11_books as b11
from swing_engine.research import b14_books as b14
from swing_engine.research.costs import cost_table
from swing_engine.research.prereg_eval import _bar_days, alpha_t_critical
from swing_engine.research.trials import DEFAULT_TRIALS_PATH, iter_trials, log_trial

SPEC = "docs/preregistration/2026-10-14-batch16.md"
OUT = "docs/preregistration/2026-10-14-batch16-results.md"
TAG = "prereg-b16"
CARD = "sp500_momentum_profitability_replica"
N_TRIALS = 7  # card: momentum family count 7; bar alpha_t_critical(7)
MARKET = "SPY"


def blend(m: pd.Series, gp_assets: pd.Series) -> pd.Series:
    """z of (m + g) / 2: g = gp_assets z-scored across ``m``'s names and winsorised at +/-3, 0 where missing."""
    gp = gp_assets.reindex(m.index)
    g = ((gp - gp.mean()) / gp.std(ddof=1)).clip(-b9.Z_CLIP, b9.Z_CLIP).fillna(0.0)
    x = (m + g) / 2.0
    return (x - x.mean()) / x.std(ddof=1)


def run(store_path: str | Path, out: str | Path = OUT, trials_path: str | Path = DEFAULT_TRIALS_PATH,
        counts_only: bool = False) -> dict[str, Any]:
    from swing_engine.data.b5_fundamentals import _read_facts, event_values
    from swing_engine.data.delisted import delisting_returns
    from swing_engine.data.fundamentals import EVENTS_TABLE, SPLITS_TABLE, _norm_ts
    from swing_engine.data.market_series import unzip_text
    from swing_engine.data.store import Store

    end = b11.WINDOWS["pooled"][1]
    with Store(str(store_path), read_only=True) as store:
        bars = store.read_bars(None, b9.DATA_START, end)
        bars = bars.assign(day=_bar_days(bars["ts"]))
        closes = bars.pivot(index="day", columns="symbol", values="close").sort_index()
        opens = bars.pivot(index="day", columns="symbol", values="open").reindex(closes.index)
        delist = delisting_returns(store)
        filings, splits = store.read_table(EVENTS_TABLE), store.read_table(SPLITS_TABLE)
        facts = _read_facts(store, sorted(set(filings["symbol"].astype(str).str.upper())))
        vals = event_values(facts, filings, splits)
        vals = vals.assign(avail=_norm_ts(vals["avail_ts"]).dt.date).dropna(subset=["avail"]).sort_values(
            "avail", kind="mergesort")

        def combine(ref: date, uni: pd.Series, z: pd.Series) -> pd.Series:
            latest = vals.loc[vals["avail"] <= ref].drop_duplicates("symbol", keep="last").set_index("symbol")
            return blend(z, latest["gp_assets"])

        sessions = [d for d in trading_days(b9.DATA_START, end) if d in closes.index]
        mcap_at = b9.mcap_function(store, bars, closes)
        opening = {sessions[0]: pd.Series({MARKET: 1.0})}
        orders = {**opening, **b9.momentum_orders(closes, mcap_at, sessions, combine=combine)}
        replica = {**opening, **b9.momentum_orders(closes, mcap_at, sessions)}
    if counts_only:
        books = [w for d, w in orders.items() if d != sessions[0]]
        rep = [w for d, w in replica.items() if d != sessions[0]]
        changes = [len(set(b.index) ^ set(a.index)) // 2 for a, b in zip(books, books[1:], strict=False)]
        print(CARD, "rebalances", len(books), "first", min(d for d in orders if d != sessions[0]), "names min/max",
              min(map(len, books)), max(map(len, books)), "names changed per rebalance median", int(np.median(changes)),
              "overlap with the replica median", int(np.median([len(set(a.index) & set(b.index)) for a, b in
                                                               zip(books, rep, strict=True)])),
              "weight sum min", round(min(float(w.sum()) for w in books), 6), flush=True)
        return {}
    traded = sorted({s for p in (orders, replica) for w in p.values() for s in w.index} | {MARKET, b11.BILL})
    costs = cost_table(bars.loc[bars["symbol"].isin(traded)]).pivot(index="as_of", columns="symbol", values="cost_bps")
    spy, rf = closes[MARKET].pct_change(fill_method=None), closes[b11.BILL].pct_change(fill_method=None)
    books = {w: b11.book_for(orders, opens, closes, costs, delist, lo, hi) for w, (lo, hi) in b11.WINDOWS.items()}
    res = {w: b9.grade(book, spy, N_TRIALS, rf) for w, book in books.items()}
    # descriptive
    rep = b11.book_for(replica, opens, closes, costs, delist, *b11.WINDOWS["pooled"])
    extra = ["## Descriptive (not part of the verdict)", "", "| window | tracking error vs SPY | correlation of daily excess "
             "with batch 9's replica | the replica's return/yr |", "|---|---|---|---|"]
    for w, book in books.items():
        ex = book["ret"] - spy.reindex(book.index)
        rex = (rep["ret"] - spy.reindex(rep.index)).reindex(book.index)
        rep_w = rep["ret"].reindex(book.index)
        extra.append(f"| {w} | {ex.std(ddof=1) * math.sqrt(252):.1%} | {ex.corr(rex):.2f} | "
                     f"{b9._pct(float((1 + rep_w).prod()) ** (252.0 / len(rep_w)) - 1.0)} |")
    pooled = books["pooled"]

    def monthly(r: pd.Series) -> pd.Series:
        return (1.0 + r).groupby([d.strftime("%Y-%m") for d in r.index]).prod() - 1.0

    ours = monthly(pooled["ret"]) - monthly(spy.reindex(pooled.index))
    texts = {k: unzip_text((b14.FRENCH_DIR / v).read_bytes()) for k, v in b14.FRENCH_FILES.items()}
    prior, op, ff = (b14.french_monthly(texts[k]) for k in ("prior", "op", "ff3"))
    french = (0.5 * (prior["BIG HiPRIOR"] + op["BIG HiOP"]) - ff["Mkt-RF"] - ff["RF"]).loc["2017-01":]
    both = pd.DataFrame({"french": french, "ours": ours}).dropna()
    extra += ["", f"Monthly correlation, {both.index[0]} .. {both.index[-1]} ({len(both)} months), of the French BIG "
              f"HiPRIOR + BIG HiOP blend minus the market with this book minus SPY: {both['french'].corr(both['ours']):.2f}."]
    if not any(TAG in (r.get("tags") or []) for r in iter_trials(trials_path)):
        log_trial(CARD, {"windows": {w: [str(lo), str(hi)] for w, (lo, hi) in b11.WINDOWS.items()}, "spec": SPEC,
                         "n_trials": N_TRIALS}, {**res["pooled"]["stats"], **res["pooled"]["vs"]}, trials_path,
                  tags=[TAG], notes=f"pre-registered batch 16 card; verdict {b11.verdict(res, N_TRIALS)[1]}")
    routes, word = b11.verdict(res, N_TRIALS)
    lines = ["# Batch 16 results", "", f"Spec: `{SPEC}`. Generated by `swing_engine.research.b16_books`; net of costs, "
             f"price-only bars; alpha from (book - BIL) on (SPY - BIL). Momentum family trials {N_TRIALS}, bar alpha t >= "
             f"{alpha_t_critical(N_TRIALS):.3f}.", "",
             f"## `{CARD}`: {word}", "", f"Route 1 (both halves): {'met' if routes[0] else 'not met'}. Route 2 "
             f"(pooled, alpha > 0 in each half): {'met' if routes[1] else 'not met'}.", "",
             "| window | from | book | return/yr | deepest drop | worst month | months up | Sharpe | haircut SR | "
             "alpha/yr | alpha t | beta | turnover/yr | costs/yr |", "|" + "---|" * 14]
    for w, r in res.items():
        for label, s in (("book", r["stats"]), ("SPY", r["spy_stats"])):
            vs = r["vs"] if label == "book" else {}
            tail = (f"{s['haircut_sharpe']:.2f} | {b9._pct(vs.get('alpha_ann', math.nan))} | "
                    f"{vs.get('alpha_t', math.nan):.2f} | {vs.get('beta', math.nan):.2f} | "
                    f"{b9._pct(r['turnover_ann'], '.0%')} | {b9._pct(r['cost_ann'], '.2%')} |") if label == "book" else "| | | | | |"
            lines.append(f"| {w} | {r['start']} | {label} | {b9._pct(s['cagr'])} | {b9._pct(-s['max_dd'])} | "
                         f"{b9._pct(s['worst_month'])} | {b9._pct(s['months_up'], '.0%')} | {s['sharpe']:.2f} | " + tail)
    lines += ["", *extra, "", "## Verdict", f"- **{CARD}**: {word}"]
    path = Path(out) if Path(out).is_absolute() else ROOT / out
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)
    return res


def main(argv: Sequence[str] | None = None) -> None:
    from swing_engine.core.config import load_settings

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settings", default="config/prereg_b9.yaml")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--counts-only", action="store_true", help="harness check: order counts only, no graded simulation")
    args = ap.parse_args(argv)
    run(ROOT / load_settings.__wrapped__(Path(args.settings)).data.store_path, args.out, counts_only=args.counts_only)


if __name__ == "__main__":
    main()
