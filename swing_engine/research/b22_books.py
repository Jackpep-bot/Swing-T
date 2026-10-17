"""Batch 22 (docs/preregistration/2026-10-14-batch22.md is the spec; this module implements it and nothing else):

* `large_cap_opportunistic_insider_buys` (weights card): each month-end, 2% in every top-500 company with an
  opportunistic (Cohen-Malloy-Pomorski) officer / director open-market purchase of $50k or more filed in the last 63
  sessions, at most 50 companies; the rest in SPY. Descriptive placebo: the same book on routine purchases.

Run once::

    uv run python -m swing_engine.research.b22_books --settings config/prereg_b9.yaml
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
from swing_engine.research.b17_books import _load
from swing_engine.research.costs import cost_table
from swing_engine.research.prereg_eval import alpha_t_critical
from swing_engine.research.trials import DEFAULT_TRIALS_PATH, iter_trials, log_trial

SPEC = "docs/preregistration/2026-10-14-batch22.md"
OUT = "docs/preregistration/2026-10-14-batch22-results.md"
TAG = "prereg-b22"
CARD = "large_cap_opportunistic_insider_buys"
N_TRIALS = 5  # card: insider family count 5; bar alpha_t_critical(5)
MARKET = "SPY"
TOP, MIN_CLOSE = 500, 5.0  # card
MIN_VALUE, WINDOW_SESSIONS = 50_000.0, 63  # card
SLOT, MAX_NAMES = 0.02, 50  # card
FIRST_REF = date(2016, 12, 1)  # month-end universes from December 2016 (events filed in January 2017 need one)


def events(trades: pd.DataFrame) -> pd.DataFrame:
    """Officer / director code-P purchases of MIN_VALUE or more, each with its CMP label (classified on all P and S
    trades filed before the label year, data.insiders.label_trades)."""
    from swing_engine.data.insiders import label_trades

    history = trades.loc[trades["code"].isin(["P", "S"])]
    p = trades.loc[(trades["code"] == "P") & (trades["is_officer"].fillna(False) | trades["is_director"].fillna(False))
                   & (trades["value"] >= MIN_VALUE)].copy()
    p["cmp_class"] = label_trades(p, history)
    p["filed"] = pd.to_datetime(p["filing_date"]).dt.date
    return p


def plan(ev: pd.DataFrame, universes: dict[date, pd.DataFrame], sessions: Sequence[date], label: str
         ) -> tuple[dict[date, pd.Series], dict[date, int]]:
    """Monthly orders (SPY first); ``ev`` must carry ``member`` (in the universe at the last month-end on or before
    filing). Returns (orders, names held per order)."""
    pos = {d: i for i, d in enumerate(sessions)}
    ev = ev.loc[(ev["cmp_class"] == label) & ev["member"]]
    orders: dict[date, pd.Series] = {sessions[0]: pd.Series({MARKET: 1.0})}
    names: dict[date, int] = {}
    for t in sorted(d for m in range(1, 13) for d in b11.last_session_of_month(sessions, m)):
        k = pos[t]
        if t < date(2017, 1, 1) or k + 1 >= len(sessions):
            continue
        lo = sessions[max(0, k - WINDOW_SESSIONS + 1)]
        hit = ev.loc[(ev["filed"] >= lo) & (ev["filed"] <= t)]
        mcap = universes[t]["mcap_pit"] if t in universes else pd.Series(dtype=float)
        size = (hit.groupby("symbol")["value"].sum() / mcap.reindex(hit["symbol"].unique())).dropna()
        held = list(size.sort_values(ascending=False, kind="mergesort").index[:MAX_NAMES])
        w = pd.Series(SLOT, index=held)
        orders[sessions[k + 1]] = pd.concat([w, pd.Series({MARKET: 1.0 - float(w.sum())})])
        names[sessions[k + 1]] = len(held)
    return orders, names


def run(store_path: str | Path, out: str | Path = OUT, trials_path: str | Path = DEFAULT_TRIALS_PATH,
        counts_only: bool = False, tr_store_path: str | Path | None = None) -> dict[str, Any]:
    from swing_engine.data.fundamentals import share_issuance_features
    from swing_engine.data.insiders import OPPORTUNISTIC, ROUTINE, TRADES_TABLE
    from swing_engine.data.store import Store

    bars, closes, opens, delist, filings, splits = _load(store_path)
    with Store(str(store_path), read_only=True) as store:
        trades = store.read_table(TRADES_TABLE)
    end = b11.WINDOWS["pooled"][1]
    sessions = [d for d in trading_days(b9.DATA_START, end) if d in closes.index]
    dollar_volume = bars.assign(dv=bars["close"] * bars["volume"]).pivot(
        index="day", columns="symbol", values="dv").reindex(closes.index)
    month_ends = sorted(d for m in range(1, 13) for d in b11.last_session_of_month(sessions, m) if d >= FIRST_REF)
    universes: dict[date, pd.DataFrame] = {}
    for t in month_ends:
        rows = bars.loc[bars["day"] == t, ["symbol", "ts", "close"]]
        f = share_issuance_features(filings, splits, rows)
        s = pd.DataFrame({"mcap_pit": f["mcap_pit"].to_numpy(), "close_as_traded": f["close_as_traded"].to_numpy()},
                         index=rows["symbol"].to_numpy())
        dv = dollar_volume.loc[:t].tail(b9.DV_SESSIONS).median().reindex(s.index)
        s = s.loc[(s["mcap_pit"] <= b9.MAX_MCAP_TO_DOLLAR_VOLUME * dv) & (s["close_as_traded"] >= MIN_CLOSE)]
        universes[t] = s.loc[s["mcap_pit"].sort_values(ascending=False, kind="mergesort").index[:TOP]]
    ev = events(trades)
    ev = ev.loc[(ev["filed"] >= month_ends[0]) & (ev["filed"] <= end)]
    me = pd.Series(month_ends)
    last_me = me.iloc[np.searchsorted(me.to_numpy(), ev["filed"].to_numpy(), side="right") - 1].to_numpy()
    ev["member"] = [s in universes[m].index for s, m in zip(ev["symbol"], last_me, strict=True)]
    orders, names = plan(ev, universes, sessions, OPPORTUNISTIC)
    placebo, pnames = plan(ev, universes, sessions, ROUTINE)
    if counts_only:
        n = pd.Series(names)
        print(CARD, "orders", len(orders), "events in the universe by label",
              ev.loc[ev["member"], "cmp_class"].value_counts().to_dict(), "names per month min/median/max",
              int(n.min()), int(n.median()), int(n.max()), "months at the 50 cap", int((n >= MAX_NAMES).sum()),
              "placebo names median", int(pd.Series(pnames).median()), flush=True)
        return {}
    traded = sorted({s for p in (orders, placebo) for w in p.values() for s in w.index} | {MARKET, b11.BILL})
    costs = cost_table(bars.loc[bars["symbol"].isin(traded)]).pivot(index="as_of", columns="symbol", values="cost_bps")
    spy, rf = closes[MARKET].pct_change(fill_method=None), closes[b11.BILL].pct_change(fill_method=None)
    books = {w: b11.book_for(orders, opens, closes, costs, delist, lo, hi) for w, (lo, hi) in b11.WINDOWS.items()}
    res = {w: b9.grade(book, spy, N_TRIALS, rf) for w, book in books.items()}
    satellite = {d: (w.drop(MARKET) / w.drop(MARKET).sum()) if len(w) > 1 else pd.Series({MARKET: 1.0})
                 for d, w in orders.items()}
    tr: dict[str, dict[str, Any]] = {}
    if tr_store_path is not None and Path(tr_store_path).exists():
        _b, tc, to, tdel, _f, _s = _load(tr_store_path)
        tspy, trf = tc[MARKET].pct_change(fill_method=None), tc[b11.BILL].pct_change(fill_method=None)
        tr = {w: b9.grade(b11.book_for(orders, to, tc, costs, tdel, lo, hi), tspy, N_TRIALS, trf)
              for w, (lo, hi) in b11.WINDOWS.items()}
    n = pd.Series(names)
    extra = ["## Descriptive (not part of the verdict)", "",
             f"Names per month: mean {n.mean():.1f}, median {int(n.median())}, max {int(n.max())}; satellite weight mean "
             f"{(n * SLOT).mean():.0%}. Placebo (routine buys) names per month: mean {pd.Series(pnames).mean():.1f}.", "",
             "| window | tracking error vs SPY | satellite alone (equal weight): return/yr, alpha/yr (t) | routine-buy "
             "placebo book: return/yr, alpha/yr (t) | total-return store: book, SPY, alpha/yr (t) |", "|---|---|---|---|---|"]
    for w, (lo, hi) in b11.WINDOWS.items():
        book = books[w]
        ex = book["ret"] - spy.reindex(book.index)
        sat = b9.grade(b11.book_for(satellite, opens, closes, costs, delist, lo, hi), spy, N_TRIALS, rf)
        pla = b9.grade(b11.book_for(placebo, opens, closes, costs, delist, lo, hi), spy, N_TRIALS, rf)
        t = tr.get(w)

        def fmt(g: dict[str, Any]) -> str:
            return f"{b9._pct(g['stats']['cagr'])}, {b9._pct(g['vs'].get('alpha_ann', math.nan))} ({g['vs'].get('alpha_t', math.nan):.2f})"

        tr_text = (f"{b9._pct(t['stats']['cagr'])}, {b9._pct(t['spy_stats']['cagr'])}, "
                   f"{b9._pct(t['vs'].get('alpha_ann', math.nan))} ({t['vs'].get('alpha_t', math.nan):.2f})") if t else "not run"
        extra.append(f"| {w} | {ex.std(ddof=1) * math.sqrt(252):.1%} | {fmt(sat)} | {fmt(pla)} | {tr_text} |")
    if not any(TAG in (r.get("tags") or []) for r in iter_trials(trials_path)):
        log_trial(CARD, {"windows": {w: [str(lo), str(hi)] for w, (lo, hi) in b11.WINDOWS.items()}, "spec": SPEC,
                         "n_trials": N_TRIALS}, {**res["pooled"]["stats"], **res["pooled"]["vs"]}, trials_path,
                  tags=[TAG], notes=f"pre-registered batch 22 card; verdict {b11.verdict(res, N_TRIALS)[1]}")
    routes, word = b11.verdict(res, N_TRIALS)
    lines = ["# Batch 22 results", "", f"Spec: `{SPEC}`. Generated by `swing_engine.research.b22_books`; net of costs, "
             f"price-only bars; alpha from (book - BIL) on (SPY - BIL). Insider family trials {N_TRIALS}, bar alpha t >= "
             f"{alpha_t_critical(N_TRIALS):.3f}.", "",
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
    ap.add_argument("--counts-only", action="store_true", help="harness check: counts only, no graded simulation")
    args = ap.parse_args(argv)
    store = ROOT / load_settings.__wrapped__(Path(args.settings)).data.store_path
    tr = ROOT / load_settings.__wrapped__(Path(args.tr_settings)).data.store_path
    run(store, args.out, counts_only=args.counts_only, tr_store_path=tr)


if __name__ == "__main__":
    main()
