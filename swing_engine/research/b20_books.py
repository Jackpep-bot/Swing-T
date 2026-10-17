"""Batch 20 (docs/preregistration/2026-10-14-batch20.md is the spec; this module implements it and nothing else):

* `global_equities_dual_momentum` (weights card, Antonacci): each month-end, if SPY's 12-month return beats BIL's,
  hold 100% of the better of SPY and EFA; otherwise 100% IEF (standing in for AGG). Orders at the next open.

Run once::

    uv run python -m swing_engine.research.b20_books --settings config/prereg_b12.yaml
"""
from __future__ import annotations

import argparse
import math
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from swing_engine.core.config import ROOT
from swing_engine.data.calendar import trading_days
from swing_engine.research import b9_books as b9
from swing_engine.research import b11_books as b11
from swing_engine.research.b17_books import _monthly
from swing_engine.research.costs import cost_table
from swing_engine.research.prereg_eval import _bar_days, alpha_t_critical
from swing_engine.research.trials import DEFAULT_TRIALS_PATH, iter_trials, log_trial

SPEC = "docs/preregistration/2026-10-14-batch20.md"
OUT = "docs/preregistration/2026-10-14-batch20-results.md"
TAG = "prereg-b20"
CARD = "global_equities_dual_momentum"
N_TRIALS = 2  # card: cross-asset trend family count 2; bar alpha_t_critical(2)
US, INTL, BONDS, BILL = "SPY", "EFA", "IEF", "BIL"  # card: IEF stands in for AGG
LOOKBACK = 252  # card: 12-month return = close / close 252 sessions earlier - 1


def holding(closes: pd.DataFrame, i: int) -> str | None:
    """The card's pick on session index ``i`` (None without LOOKBACK sessions of history)."""
    if i < LOOKBACK:
        return None
    r = closes.iloc[i] / closes.iloc[i - LOOKBACK] - 1.0
    if not r[US] > r[BILL]:
        return BONDS
    return US if r[US] >= r[INTL] else INTL


def orders_for(closes: pd.DataFrame, sessions: Sequence[date]) -> dict[date, pd.Series]:
    """SPY from the first session; then, at the open after each month-end, the card's pick when it changes."""
    idx = {d: i for i, d in enumerate(closes.index)}
    orders: dict[date, pd.Series] = {sessions[0]: pd.Series({US: 1.0})}
    held = US
    for t in sorted(d for m in range(1, 13) for d in b11.last_session_of_month(sessions, m)):
        k = sessions.index(t)
        pick = holding(closes, idx[t])
        if pick is None or k + 1 >= len(sessions) or pick == held:
            continue
        orders[sessions[k + 1]] = pd.Series({pick: 1.0})
        held = pick
    return orders


def _etf_bars(store_path: str | Path, end: date) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    from swing_engine.data.store import Store

    with Store(str(store_path), read_only=True) as store:
        bars = store.read_bars([US, INTL, BONDS, BILL], b9.DATA_START, end)
    bars = bars.assign(day=_bar_days(bars["ts"]))
    closes = bars.pivot(index="day", columns="symbol", values="close").sort_index()
    opens = bars.pivot(index="day", columns="symbol", values="open").reindex(closes.index)
    return bars, closes, opens


def run(store_path: str | Path, out: str | Path = OUT, trials_path: str | Path = DEFAULT_TRIALS_PATH,
        counts_only: bool = False, tr_store_path: str | Path | None = None,
        replica_store_path: str | Path | None = None) -> dict[str, Any]:
    end = b11.WINDOWS["pooled"][1]
    bars, closes, opens = _etf_bars(store_path, end)
    sessions = [d for d in trading_days(b9.DATA_START, end) if d in closes.index]
    orders = orders_for(closes, sessions)
    months = pd.Series({t: holding(closes, closes.index.get_loc(t)) for t in
                        sorted(d for m in range(1, 13) for d in b11.last_session_of_month(sessions, m))}).dropna()
    switches = len(orders) - 1
    if counts_only:
        print(CARD, "first signal", months.index[0],
              "switches", switches, "first switch", min((d for d in orders if d != sessions[0]), default=None),
              "months in each", months.value_counts().to_dict(), "history from", closes.index[0], flush=True)
        return {}
    costs = cost_table(bars).pivot(index="as_of", columns="symbol", values="cost_bps")
    spy, rf = closes[US].pct_change(fill_method=None), closes[BILL].pct_change(fill_method=None)
    books = {w: b11.book_for(orders, opens, closes, costs, {}, lo, hi) for w, (lo, hi) in b11.WINDOWS.items()}
    res = {w: b9.grade(book, spy, N_TRIALS, rf) for w, book in books.items()}
    tr: dict[str, dict[str, Any]] = {}
    if tr_store_path is not None and Path(tr_store_path).exists():
        _tb, tc, to = _etf_bars(tr_store_path, end)
        tspy, trf = tc[US].pct_change(fill_method=None), tc[BILL].pct_change(fill_method=None)
        tr = {w: b9.grade(b11.book_for(orders, to, tc, costs, {}, lo, hi), tspy, N_TRIALS, trf)
              for w, (lo, hi) in b11.WINDOWS.items()}
    rep_m = None
    if replica_store_path is not None:
        from swing_engine.data.delisted import delisting_returns
        from swing_engine.data.store import Store

        with Store(str(replica_store_path), read_only=True) as store:
            rb = store.read_bars(None, b9.DATA_START, end)
            rb = rb.assign(day=_bar_days(rb["ts"]))
            rc = rb.pivot(index="day", columns="symbol", values="close").sort_index()
            ro = rb.pivot(index="day", columns="symbol", values="open").reindex(rc.index)
            rs = [d for d in trading_days(b9.DATA_START, end) if d in rc.index]
            replica = {rs[0]: pd.Series({US: 1.0}), **b9.momentum_orders(rc, b9.mcap_function(store, rb, rc), rs)}
            delist = delisting_returns(store)
        names = sorted({s for w in replica.values() for s in w.index})
        rcost = cost_table(rb.loc[rb["symbol"].isin(names)]).pivot(index="as_of", columns="symbol", values="cost_bps")
        rep = b11.book_for(replica, ro, rc, rcost, delist, *b11.WINDOWS["pooled"])
        rep_m = _monthly(rep["ret"]) - _monthly(rc[US].pct_change(fill_method=None).reindex(rep.index))
    extra = ["## Descriptive (not part of the verdict)", "",
             f"Switches {months.index[0]} .. {sessions[-1]}: {switches}. Month-end signals ({len(months)}): {', '.join(f'{k} {v}' for k, v in months.value_counts().items())}.", "",
             "| window | total-return store: book return/yr, SPY return/yr, alpha/yr (t) | monthly excess correlation with "
             "batch 9's replica |", "|---|---|---|"]
    for w, book in books.items():
        t = tr.get(w)
        tr_text = (f"{b9._pct(t['stats']['cagr'])}, {b9._pct(t['spy_stats']['cagr'])}, "
                   f"{b9._pct(t['vs'].get('alpha_ann', math.nan))} ({t['vs'].get('alpha_t', math.nan):.2f})") if t else "not run"
        ours = _monthly(book["ret"]) - _monthly(spy.reindex(book.index))
        corr = f"{ours.corr(rep_m.reindex(ours.index)):.2f}" if rep_m is not None else "not run"
        extra.append(f"| {w} | {tr_text} | {corr} |")
    if not any(TAG in (r.get("tags") or []) for r in iter_trials(trials_path)):
        log_trial(CARD, {"windows": {w: [str(lo), str(hi)] for w, (lo, hi) in b11.WINDOWS.items()}, "spec": SPEC,
                         "n_trials": N_TRIALS}, {**res["pooled"]["stats"], **res["pooled"]["vs"]}, trials_path,
                  tags=[TAG], notes=f"pre-registered batch 20 card; verdict {b11.verdict(res, N_TRIALS)[1]}")
    routes, word = b11.verdict(res, N_TRIALS)
    lines = ["# Batch 20 results", "", f"Spec: `{SPEC}`. Generated by `swing_engine.research.b20_books`; net of costs, "
             f"price-only bars; alpha from (book - BIL) on (SPY - BIL). Cross-asset trend family trials {N_TRIALS}, bar "
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
    ap.add_argument("--settings", default="config/prereg_b12.yaml")
    ap.add_argument("--tr-store", default="data/live/replay_b12_tr.duckdb", help="total-return store, descriptive")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--counts-only", action="store_true", help="harness check: signal counts only, no graded simulation")
    args = ap.parse_args(argv)
    store = ROOT / load_settings.__wrapped__(Path(args.settings)).data.store_path
    run(store, args.out, counts_only=args.counts_only, tr_store_path=ROOT / args.tr_store, replica_store_path=store)


if __name__ == "__main__":
    main()
