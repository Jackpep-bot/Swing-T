"""Batch 13: "mispricing short-leg avoidance", two weights cards (docs/preregistration/2026-10-14-batch13.md is the
spec; this module implements it and nothing else). Each cap-weights a universe and leaves out its worst-scored names:

* `mispricing_short_leg_exclusion_large`: the 500 largest by `mcap_pit` (as-traded close >= $5, a total-assets filing
  in the last 400 sessions) minus the worst 100 (stay excluded until past the 130th worst), each name capped at 10%;
* `mispricing_short_leg_exclusion_mid`: ranks 501-1,500 (also median 63-session dollar volume >= $1M) minus the worst
  300 (buffer 360), cap 2%.

Score = mean of the available percentiles (1 = worst; at least 3 of 5) of net share issuance (high is bad), asset
growth (high), accruals (high), gross profit / assets (low) and ROA (low), from filings with `avail_ts` on or before
the reference day (data.b5_fundamentals.event_values). Names with fewer than 3 signals have no score and stay in the
book. Reference days: last session of Feb, May, Aug, Nov; orders at the open after the next month's third Friday;
weights drift between rebalances; SPY before the first rebalance. Run once::

    uv run python -m swing_engine.research.b13_books --settings config/prereg_b9.yaml
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
from swing_engine.research import b12_books as b12
from swing_engine.research.costs import cost_table
from swing_engine.research.prereg_eval import _bar_days, alpha_t_critical
from swing_engine.research.trials import DEFAULT_TRIALS_PATH, iter_trials, log_trial

SPEC = "docs/preregistration/2026-10-14-batch13.md"
OUT = "docs/preregistration/2026-10-14-batch13-results.md"
TAG = "prereg-b13"
LARGE, MID = "mispricing_short_leg_exclusion_large", "mispricing_short_leg_exclusion_mid"
N_TRIALS = 2  # cards: the family's 2 trials; bar alpha_t_critical(2)
#: card -> (first rank, last rank, excluded, buffer, name cap, dollar-volume floor)
CARDS: dict[str, tuple[int, int, int, int, float, float]] = {LARGE: (1, 500, 100, 130, 0.10, 0.0),
                                                              MID: (501, 1500, 300, 360, 0.02, 1_000_000.0)}
MIN_CLOSE, ASSETS_WITHIN, MIN_SIGNALS = 5.0, 400, 3  # cards
# signal -> True when a high value is bad
SIGNALS: dict[str, bool] = {"net_share_issuance": True, "asset_growth": True, "accruals": True, "gp_assets": False,
                            "roa": False}
MARKET = "SPY"
FIRST_REBALANCE = date(2017, 3, 1)  # cards: SPY before the first rebalance, in March 2017


def mispricing_score(values: pd.DataFrame) -> pd.Series:
    """Mean of the available worst-is-1 percentiles within ``values`` (one row per name); NaN under MIN_SIGNALS."""
    pct = pd.DataFrame({s: values[s].rank(pct=True, ascending=high_bad) for s, high_bad in SIGNALS.items()},
                       index=values.index)
    return pct.mean(axis=1).where(pct.notna().sum(axis=1) >= MIN_SIGNALS)


def exclude(score: pd.Series, previous: set[str], worst: int, buffer: int) -> set[str]:
    """The ``worst`` highest scores, plus previously excluded names still within the worst ``buffer``."""
    rank = score.dropna().rank(ascending=False, method="first")
    return set(rank.index[rank <= worst]) | {s for s in previous if s in rank.index and rank[s] <= buffer}


def plan(universes: dict[date, pd.DataFrame], first_day: date, worst: int, buffer: int, cap: float
         ) -> tuple[dict[date, pd.Series], dict[date, pd.Series], dict[date, pd.Series]]:
    """(book, excluded names cap-weighted, whole universe cap-weighted) per rebalance session. ``universes``: per
    rebalance session, the universe's rows (mcap_pit and the five signals)."""
    book, out, whole = {first_day: pd.Series({MARKET: 1.0})}, {}, {first_day: pd.Series({MARKET: 1.0})}
    excluded: set[str] = set()
    for day in sorted(universes):
        u = universes[day]
        excluded = exclude(mispricing_score(u), excluded, worst, buffer)
        keep = u.loc[~u.index.isin(excluded), "mcap_pit"]
        book[day] = b9.capped_weights(keep, pd.Series(cap, index=keep.index))
        gone = u.loc[u.index.isin(excluded), "mcap_pit"]
        if len(gone):
            out[day] = gone / gone.sum()
        whole[day] = u["mcap_pit"] / u["mcap_pit"].sum()
    return book, out, whole


def run(store_path: str | Path, out: str | Path = OUT, trials_path: str | Path = DEFAULT_TRIALS_PATH,
        counts_only: bool = False) -> dict[str, Any]:
    """The pre-registered run. ``counts_only``: build the books, print their counts, stop (harness check)."""
    from swing_engine.data.b5_fundamentals import MISPRICING_COLUMNS, _read_facts, event_values
    from swing_engine.data.delisted import delisting_returns
    from swing_engine.data.fundamentals import EVENTS_TABLE, SPLITS_TABLE, _norm_ts, share_issuance_features
    from swing_engine.data.store import Store

    end = b11.WINDOWS["pooled"][1]
    with Store(str(store_path), read_only=True) as store:
        bars = store.read_bars(None, b9.DATA_START, end)
        bars = bars.assign(day=_bar_days(bars["ts"]))
        closes = bars.pivot(index="day", columns="symbol", values="close").sort_index()
        opens = bars.pivot(index="day", columns="symbol", values="open").reindex(closes.index)
        dollar_volume = bars.assign(dv=bars["close"] * bars["volume"]).pivot(
            index="day", columns="symbol", values="dv").reindex(closes.index)
        delist = delisting_returns(store)
        filings, splits = store.read_table(EVENTS_TABLE), store.read_table(SPLITS_TABLE)
        facts = _read_facts(store, sorted(set(filings["symbol"].astype(str).str.upper())))
    vals = event_values(facts, filings, splits)
    vals = vals.assign(avail=_norm_ts(vals["avail_ts"]).dt.date)  # New York session date the filing is usable from
    vals = vals.dropna(subset=["avail"]).sort_values("avail", kind="mergesort")
    sessions = [d for d in trading_days(b9.DATA_START, end) if d in closes.index]
    pos = {d: i for i, d in enumerate(sessions)}
    refs = sorted(d for m in b12.REF_MONTHS for d in b11.last_session_of_month(sessions, m))
    universes: dict[str, dict[date, pd.DataFrame]] = {c: {} for c in CARDS}
    for ref in refs:
        day = b12._after_third_friday(ref, sessions)
        if day is None or day < FIRST_REBALANCE:
            continue
        rows = bars.loc[bars["day"] == ref, ["symbol", "ts", "close"]]
        f = share_issuance_features(filings, splits, rows)
        snap = pd.DataFrame({"mcap_pit": f["mcap_pit"].to_numpy(), "close_as_traded": f["close_as_traded"].to_numpy(),
                             "net_share_issuance": f["net_share_issuance"].to_numpy()}, index=rows["symbol"].to_numpy())
        dv = dollar_volume.loc[:ref].tail(b9.DV_SESSIONS).median().reindex(snap.index)
        snap = snap.loc[(snap["mcap_pit"] <= b9.MAX_MCAP_TO_DOLLAR_VOLUME * dv) & (snap["close_as_traded"] >= MIN_CLOSE)]
        latest = vals.loc[vals["avail"] <= ref].drop_duplicates("symbol", keep="last").set_index("symbol")
        fresh = latest["avail"].map(lambda d: pos.get(d, -10**9)) >= pos[ref] - ASSETS_WITHIN
        latest = latest.loc[fresh & latest["assets"].notna(), [c for c in MISPRICING_COLUMNS if c != "assets"]]
        snap = snap.join(latest, how="inner")
        ranked = snap["mcap_pit"].rank(ascending=False, method="first")
        for card, (first, last, _w, _b, _cap, min_dv) in CARDS.items():
            u = snap.loc[(ranked >= first) & (ranked <= last)]
            u = u.loc[dv.reindex(u.index) >= min_dv] if min_dv > 0 else u
            if len(u):
                universes[card][day] = u
    plans = {card: plan(universes[card], sessions[0], w, b, cap) for card, (_f, _l, w, b, cap, _d) in CARDS.items()}
    if counts_only:
        for card, (book, gone, _whole) in plans.items():
            sizes = [len(w) for d, w in book.items() if d != sessions[0]]
            print(card, "rebalances", len(sizes), "first", min(d for d in book if d != sessions[0]),
                  "held min/median/max", min(sizes), int(np.median(sizes)), max(sizes), "excluded median",
                  int(np.median([len(w) for w in gone.values()])), "largest weight", round(max(float(w.max()) for d, w in
                                                                                             book.items() if d != sessions[0]), 3),
                  flush=True)
        return {}
    traded = sorted({s for p in plans.values() for orders in p for w in orders.values() for s in w.index})
    costs = cost_table(bars.loc[bars["symbol"].isin(traded)]).pivot(index="as_of", columns="symbol", values="cost_bps")
    spy, rf = closes[MARKET].pct_change(fill_method=None), closes[b11.BILL].pct_change(fill_method=None)
    results, extra = {}, ["## Descriptive (not part of the verdicts)", "",
                          "| book | window | return/yr | deepest drop | alpha/yr | alpha t | tracking error vs SPY |",
                          "|---|---|---|---|---|---|---|"]
    for card, (book_orders, gone, whole) in plans.items():
        results[card] = {}
        for w, (lo, hi) in b11.WINDOWS.items():
            book = b11.book_for(book_orders, opens, closes, costs, delist, lo, hi)
            results[card][w] = b9.grade(book, spy, N_TRIALS, rf)
            te = float((book["ret"] - spy.reindex(book.index)).std(ddof=1) * math.sqrt(252))
            extra.append(f"| {card} | {w} | {b9._pct(results[card][w]['stats']['cagr'])} | "
                         f"{b9._pct(-results[card][w]['stats']['max_dd'])} | {b9._pct(results[card][w]['vs'].get('alpha_ann', math.nan))} | "
                         f"{results[card][w]['vs'].get('alpha_t', math.nan):.2f} | {te:.1%} |")
        for label, orders in ((f"{card}: the excluded names, cap-weighted", gone),
                              (f"{card}: the whole universe, cap-weighted (no exclusion)", whole)):
            for w, (lo, hi) in b11.WINDOWS.items():
                g = b9.grade(b11.book_for(orders, opens, closes, costs, delist, lo, hi), spy, N_TRIALS, rf)
                extra.append(f"| {label} | {w} | {b9._pct(g['stats']['cagr'])} | {b9._pct(-g['stats']['max_dd'])} | "
                             f"{b9._pct(g['vs'].get('alpha_ann', math.nan))} | {g['vs'].get('alpha_t', math.nan):.2f} | |")
    if not any(TAG in (r.get("tags") or []) for r in iter_trials(trials_path)):
        for card, res in results.items():
            log_trial(card, {"windows": {w: [str(lo), str(hi)] for w, (lo, hi) in b11.WINDOWS.items()}, "spec": SPEC,
                             "n_trials": N_TRIALS}, {**res["pooled"]["stats"], **res["pooled"]["vs"]}, trials_path,
                      tags=[TAG], notes=f"pre-registered batch 13 card; verdict {b11.verdict(res, N_TRIALS)[1]}")
    lines = ["# Batch 13 results", "", f"Spec: `{SPEC}`. Generated by `swing_engine.research.b13_books`; net of costs, "
             f"price-only bars; alpha from (book - BIL) on (SPY - BIL). Bar alpha t >= {alpha_t_critical(N_TRIALS):.3f}.", ""]
    for card, res in results.items():
        routes, word = b11.verdict(res, N_TRIALS)
        lines += [f"## `{card}`: {word}", "", f"Route 1 (both halves): {'met' if routes[0] else 'not met'}. Route 2 "
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
        lines.append("")
    lines += [*extra, "", "## Verdicts", *[f"- **{c}**: {b11.verdict(r, N_TRIALS)[1]}" for c, r in results.items()]]
    path = Path(out) if Path(out).is_absolute() else ROOT / out
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)
    return results


def main(argv: Sequence[str] | None = None) -> None:
    from swing_engine.core.config import load_settings

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settings", default="config/prereg_b9.yaml")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--counts-only", action="store_true", help="harness check: book counts only, no simulation")
    args = ap.parse_args(argv)
    run(ROOT / load_settings.__wrapped__(Path(args.settings)).data.store_path, args.out, counts_only=args.counts_only)


if __name__ == "__main__":
    main()
