"""Batch 10: batch 9's `sp500_momentum_index_replica` rules, unchanged, on two universes that do not overlap with it
(docs/preregistration/2026-10-14-batch10.md is the spec; this module implements it and nothing else):

* `midcap_momentum_index_replica`: market-cap ranks 501-900, 80 names, buffer 64 / 96;
* `smallcap_momentum_index_replica`: ranks 901-1,500, then close >= $3 and 63-session median dollar volume >= $1M,
  120 names, buffer 96 / 144.

Graded like batch 9 (research.b9_books) over the momentum family's 3 trials. Descriptive beside each: the cap-weighted
book of the same universe, rebalanced on the same sessions. Run once::

    uv run python -m swing_engine.research.b10_books --settings config/prereg_b9.yaml
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from swing_engine.core.config import ROOT
from swing_engine.data.calendar import trading_days
from swing_engine.research import b9_books as b9
from swing_engine.research.costs import cost_table
from swing_engine.research.prereg_eval import _bar_days
from swing_engine.research.trials import DEFAULT_TRIALS_PATH, iter_trials, log_trial
from swing_engine.research.weights_book import simulate

SPEC = "docs/preregistration/2026-10-14-batch10.md"
OUT = "docs/preregistration/2026-10-14-batch10-results.md"
TAG = "prereg-b10"
N_FAMILY_TRIALS = 3  # cards: batch 9's replica plus these two
MID, SMALL = "midcap_momentum_index_replica", "smallcap_momentum_index_replica"
#: card -> (first rank, last rank, names, enter rank, stay rank, screened)
CARDS: dict[str, tuple[int, int, int, int, int, bool]] = {MID: (501, 900, 80, 64, 96, False),
                                                           SMALL: (901, 1500, 120, 96, 144, True)}
MIN_CLOSE, MIN_DOLLAR_VOLUME = 3.0, 1_000_000.0  # small-cap card: close >= $3, med_dv_63 >= $1M


def cap_weight_orders(universes: dict[date, pd.Series]) -> dict[date, pd.Series]:
    """Descriptive: each rebalance session's universe at its own market-cap weights."""
    return {d: u / u.sum() for d, u in universes.items()}


def run(store_path: str | Path, out: str | Path = OUT, trials_path: str | Path = DEFAULT_TRIALS_PATH) -> dict[str, Any]:
    from swing_engine.data.delisted import delisting_returns
    from swing_engine.data.store import Store

    end = max(hi for _, hi in b9.WINDOWS.values())
    with Store(str(store_path), read_only=True) as store:
        bars = store.read_bars(None, b9.DATA_START, end)
        bars = bars.assign(day=_bar_days(bars["ts"]))
        closes = bars.pivot(index="day", columns="symbol", values="close").sort_index()
        opens = bars.pivot(index="day", columns="symbol", values="open").reindex(closes.index)
        dollar_volume = bars.assign(dv=bars["close"] * bars["volume"]).pivot(
            index="day", columns="symbol", values="dv").reindex(closes.index)
        delist = delisting_returns(store)
        mcap_at = b9.mcap_function(store, bars, closes)
        sessions = [d for d in trading_days(b9.DATA_START, end) if d in closes.index]

        def screen(ref: date) -> set[str]:
            dv = dollar_volume.loc[:ref].tail(b9.DV_SESSIONS).median()
            px = closes.loc[ref]
            return set(px.index[(px >= MIN_CLOSE) & (dv.reindex(px.index) >= MIN_DOLLAR_VOLUME)])

        plans: dict[str, tuple[dict[date, pd.Series], dict[date, pd.Series]]] = {}
        for card, (first, last, hold, enter, stay, screened) in CARDS.items():
            universes: dict[date, pd.Series] = {}
            orders = b9.momentum_orders(closes, mcap_at, sessions, first=first, last=last, hold=hold, enter=enter,
                                        stay=stay, screen=screen if screened else None, universes=universes)
            plans[card] = (orders, cap_weight_orders(universes))
    traded = sorted({s for o, c in plans.values() for book in (o, c) for w in book.values() for s in w.index})
    costs = cost_table(bars.loc[bars["symbol"].isin(traded)]).pivot(index="as_of", columns="symbol", values="cost_bps")
    spy = closes[b9.MARKET].pct_change(fill_method=None)
    results: dict[str, dict[str, dict[str, Any]]] = {card: {} for card in CARDS}
    benchmarks: dict[str, dict[str, dict[str, Any]]] = {card: {} for card in CARDS}
    for card, (mom, capw) in plans.items():
        for w, (lo, hi) in b9.WINDOWS.items():
            span = closes.loc[lo:hi]
            for book_orders, into in ((mom, results), (capw, benchmarks)):
                before = [d for d in sorted(book_orders) if d <= span.index[0]]
                orders = {d: o for d, o in book_orders.items() if span.index[0] < d <= span.index[-1]}
                if before:
                    orders[span.index[0]] = book_orders[before[-1]]
                book = simulate(opens.loc[lo:hi], span, costs, orders, delist)
                into[card][w] = b9.grade(book, spy, N_FAMILY_TRIALS)
    if not any(TAG in (r.get("tags") or []) for r in iter_trials(trials_path)):
        for card, res in results.items():
            word = b9.verdict(res, N_FAMILY_TRIALS)[1]
            for w, (lo, hi) in b9.WINDOWS.items():
                log_trial(card, {"window": w, "start": lo, "end": hi, "spec": SPEC, "n_trials": N_FAMILY_TRIALS},
                          {**res[w]["stats"], **res[w]["vs"]}, trials_path, tags=[TAG, f"window-{w}"],
                          notes=f"pre-registered batch 10 card; verdict {word}")
    lines = b9.render(results, N_FAMILY_TRIALS, "Batch 10", SPEC, "b10_books")
    lines += ["", "## Descriptive: the cap-weighted book of each card's own universe (same sessions, not a trial)", "",
              "| card | window | return/yr | deepest drop | Sharpe | alpha/yr vs SPY | alpha t |", "|---|---|---|---|---|---|---|"]
    for card, res in benchmarks.items():
        for w, r in res.items():
            s, vs = r["stats"], r["vs"]
            lines.append(f"| {card} | {w} | {b9._pct(s['cagr'])} | {b9._pct(-s['max_dd'])} | {s['sharpe']:.2f} | "
                         f"{b9._pct(vs.get('alpha_ann', float('nan')))} | {vs.get('alpha_t', float('nan')):.2f} |")
    path = Path(out) if Path(out).is_absolute() else ROOT / out
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)
    return results


def main(argv: Sequence[str] | None = None) -> None:
    from swing_engine.core.config import load_settings

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settings", default="config/prereg_b9.yaml")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args(argv)
    run(ROOT / load_settings.__wrapped__(Path(args.settings)).data.store_path, args.out)


if __name__ == "__main__":
    main()
