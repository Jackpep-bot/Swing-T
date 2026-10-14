"""Batch 19 (docs/preregistration/2026-10-14-batch19.md is the spec; this module implements it and nothing else):

* `sp500_earnings_surprise_drift` (weights card): at the end of March, May, August and November, the 100 of the 500
  largest names with the highest (this quarter's diluted EPS - the same quarter a year earlier) / close, from the
  latest 10-Q / 10-K filed within 100 sessions; holders kept within the top 150; mcap weights capped at 5%; rest SPY.

Run once::

    uv run python -m swing_engine.research.b19_books --settings config/prereg_b9.yaml
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
from swing_engine.research.b17_books import _load, _monthly
from swing_engine.research.b18_cz import cap_weights
from swing_engine.research.costs import cost_table
from swing_engine.research.prereg_eval import alpha_t_critical
from swing_engine.research.trials import DEFAULT_TRIALS_PATH, iter_trials, log_trial

SPEC = "docs/preregistration/2026-10-14-batch19.md"
OUT = "docs/preregistration/2026-10-14-batch19-results.md"
TAG = "prereg-b19"
CARD = "sp500_earnings_surprise_drift"
N_TRIALS = 2  # card: earnings-surprise family count 2; bar alpha_t_critical(2)
MARKET = "SPY"
REF_MONTHS = (3, 5, 8, 11)  # card: last session of Mar / May / Aug / Nov; orders at the next open
FIRST_REF = date(2017, 3, 1)  # card: SPY before the first rebalance (March 2017)
TOP, MIN_CLOSE, FRESH_SESSIONS = 500, 5.0, 100  # card
HOLD, STAY = 100, 150  # card (the 5% cap: b18_cz.cap_weights)


def plan(universes: dict[date, pd.DataFrame], first_day: date, sign: float = 1.0) -> dict[date, pd.Series]:
    """Orders per rebalance session; ``universes``: mcap_pit and ``surprise`` (NaN: not eligible). ``sign`` -1: the
    bottom-100 book (descriptive)."""
    orders: dict[date, pd.Series] = {first_day: pd.Series({MARKET: 1.0})}
    current: set[str] = set()
    for day in sorted(universes):
        u = universes[day]
        score = (sign * u["surprise"]).dropna()
        held = b9.select(score, current, hold=HOLD, enter=len(score), stay=STAY)
        orders[day] = cap_weights(u["mcap_pit"], held)
        current = set(held)
    return orders


def run(store_path: str | Path, out: str | Path = OUT, trials_path: str | Path = DEFAULT_TRIALS_PATH,
        counts_only: bool = False) -> dict[str, Any]:
    from swing_engine.data.b5_fundamentals import _read_facts, event_values
    from swing_engine.data.fundamentals import _norm_ts, share_issuance_features
    from swing_engine.data.store import Store

    bars, closes, opens, delist, filings, splits = _load(store_path)
    with Store(str(store_path), read_only=True) as store:
        facts = _read_facts(store, sorted(set(filings["symbol"].astype(str).str.upper())))
    end = b11.WINDOWS["pooled"][1]
    sessions = [d for d in trading_days(b9.DATA_START, end) if d in closes.index]
    pos = {d: i for i, d in enumerate(sessions)}
    vals = event_values(facts, filings, splits)
    vals = vals.assign(avail=_norm_ts(vals["avail_ts"]).dt.date).dropna(subset=["avail"]).sort_values("avail", kind="mergesort")
    dollar_volume = bars.assign(dv=bars["close"] * bars["volume"]).pivot(
        index="day", columns="symbol", values="dv").reindex(closes.index)
    universes: dict[date, pd.DataFrame] = {}
    for ref in sorted(d for m in REF_MONTHS for d in b11.last_session_of_month(sessions, m)):
        k = pos[ref]
        if ref < FIRST_REF or k + 1 >= len(sessions):
            continue
        rows = bars.loc[bars["day"] == ref, ["symbol", "ts", "close"]]
        f = share_issuance_features(filings, splits, rows)
        s = pd.DataFrame({"mcap_pit": f["mcap_pit"].to_numpy(), "close_as_traded": f["close_as_traded"].to_numpy()},
                         index=rows["symbol"].to_numpy())
        dv = dollar_volume.loc[:ref].tail(b9.DV_SESSIONS).median().reindex(s.index)
        s = s.loc[(s["mcap_pit"] <= b9.MAX_MCAP_TO_DOLLAR_VOLUME * dv) & (s["close_as_traded"] >= MIN_CLOSE)]
        s = s.loc[s["mcap_pit"].sort_values(ascending=False, kind="mergesort").index[:TOP]]
        latest = vals.loc[vals["avail"] <= ref].drop_duplicates("symbol", keep="last").set_index("symbol")
        fresh = latest["avail"].map(lambda d: pos.get(d, -10**9)) > k - FRESH_SESSIONS
        latest = latest.loc[fresh]
        # EPS on today's split basis over the split-adjusted close: the same ratio as as-traded EPS / as-traded close
        surprise = (latest["eps_q"] - latest["eps_q_year_ago"]).reindex(s.index) / closes.loc[ref].reindex(s.index)
        universes[sessions[k + 1]] = s.assign(surprise=surprise.replace([np.inf, -np.inf], np.nan))
    orders = plan(universes, sessions[0])
    if counts_only:
        books = [w for d, w in orders.items() if d != sessions[0]]
        names = [len(set(w.index) - {MARKET}) for w in books]
        changes = [len((set(b.index) ^ set(a.index)) - {MARKET}) // 2 for a, b in zip(books, books[1:], strict=False)]
        elig = [int(u["surprise"].notna().sum()) for u in universes.values()]
        print(CARD, "rebalances", len(books), "first", min(d for d in orders if d != sessions[0]), "names min/max",
              min(names), max(names), "eligible min/median/max", min(elig), int(np.median(elig)), max(elig),
              "changed per rebalance median", int(np.median(changes)), "largest weight",
              round(max(float(w.drop(MARKET, errors="ignore").max()) for w in books), 3), "SPY max",
              round(max(float(w.get(MARKET, 0.0)) for w in books), 3), flush=True)
        return {}
    bottom = plan(universes, sessions[0], sign=-1.0)
    with Store(str(store_path), read_only=True) as store:
        replica = {sessions[0]: pd.Series({MARKET: 1.0}),
                   **b9.momentum_orders(closes, b9.mcap_function(store, bars, closes), sessions)}
    traded = sorted({s for p in (orders, bottom, replica) for w in p.values() for s in w.index} | {MARKET, b11.BILL})
    costs = cost_table(bars.loc[bars["symbol"].isin(traded)]).pivot(index="as_of", columns="symbol", values="cost_bps")
    spy, rf = closes[MARKET].pct_change(fill_method=None), closes[b11.BILL].pct_change(fill_method=None)
    books = {w: b11.book_for(orders, opens, closes, costs, delist, lo, hi) for w, (lo, hi) in b11.WINDOWS.items()}
    res = {w: b9.grade(book, spy, N_TRIALS, rf) for w, book in books.items()}
    rep = b11.book_for(replica, opens, closes, costs, delist, *b11.WINDOWS["pooled"])
    rep_m = _monthly(rep["ret"]) - _monthly(spy.reindex(rep.index))
    extra = ["## Descriptive (not part of the verdict)", "", "| window | tracking error vs SPY | monthly excess correlation "
             "with batch 9's replica | bottom-100 book: return/yr, alpha/yr (t) |", "|---|---|---|---|"]
    for w, (lo, hi) in b11.WINDOWS.items():
        book = books[w]
        ex = book["ret"] - spy.reindex(book.index)
        ours = _monthly(book["ret"]) - _monthly(spy.reindex(book.index))
        g = b9.grade(b11.book_for(bottom, opens, closes, costs, delist, lo, hi), spy, N_TRIALS, rf)
        extra.append(f"| {w} | {ex.std(ddof=1) * math.sqrt(252):.1%} | {ours.corr(rep_m.reindex(ours.index)):.2f} | "
                     f"{b9._pct(g['stats']['cagr'])}, {b9._pct(g['vs'].get('alpha_ann', math.nan))} "
                     f"({g['vs'].get('alpha_t', math.nan):.2f}) |")
    if not any(TAG in (r.get("tags") or []) for r in iter_trials(trials_path)):
        log_trial(CARD, {"windows": {w: [str(lo), str(hi)] for w, (lo, hi) in b11.WINDOWS.items()}, "spec": SPEC,
                         "n_trials": N_TRIALS}, {**res["pooled"]["stats"], **res["pooled"]["vs"]}, trials_path,
                  tags=[TAG], notes=f"pre-registered batch 19 card; verdict {b11.verdict(res, N_TRIALS)[1]}")
    routes, word = b11.verdict(res, N_TRIALS)
    lines = ["# Batch 19 results", "", f"Spec: `{SPEC}`. Generated by `swing_engine.research.b19_books`; net of costs, "
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
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--counts-only", action="store_true", help="harness check: order counts only, no graded simulation")
    args = ap.parse_args(argv)
    run(ROOT / load_settings.__wrapped__(Path(args.settings)).data.store_path, args.out, counts_only=args.counts_only)


if __name__ == "__main__":
    main()
