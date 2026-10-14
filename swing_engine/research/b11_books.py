"""Batch 11: two weights cards graded with the full-period test (docs/preregistration/2026-10-14-batch11.md is the spec;
this module implements it and nothing else):

* `dividend_increase_drift`: equal weight (cap 4%) in the top-1,500 names whose regular dividend rose 10% to 3x, or
  was started, with the ex-date in the last 63 sessions; weekly; the unused weight in SPY.
* `russell_recon_migrant_drift`: equal weight (cap 3%) in the names ranked 1-1,000 by market cap on last year's
  April rank day and 1,001-1,300 on this year's, bought after the last Friday of June and held a year; the unused
  weight, and the whole book before the first cohort, in SPY.

Simulated by research.weights_book; graded by research.b9_books.grade (alpha with the bill rate taken off both sides).
Run once::

    uv run python -m swing_engine.research.b11_books --settings config/prereg_b9.yaml
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
from swing_engine.research.costs import cost_table
from swing_engine.research.prereg_eval import _bar_days, alpha_t_critical
from swing_engine.research.trials import DEFAULT_TRIALS_PATH, iter_trials, log_trial
from swing_engine.research.weights_book import simulate

SPEC = "docs/preregistration/2026-10-14-batch11.md"
OUT = "docs/preregistration/2026-10-14-batch11-results.md"
TAG = "prereg-b11"
DIVIDEND, MIGRANT = "dividend_increase_drift", "russell_recon_migrant_drift"
N_TRIALS = 2  # cards: one trial each, two new families; bar alpha_t_critical(2)
WINDOWS: dict[str, tuple[date, date]] = {**b9.WINDOWS, "pooled": (date(2017, 1, 1), date(2026, 10, 5))}
MARKET, BILL = "SPY", "BIL"
# dividend card
MIN_RISE, MAX_RISE = 1.10, 3.0  # card: rate >= 1.10 x the previous regular rate, <= 3.0 x
PREVIOUS_WITHIN = 400  # card: the previous regular ex-date within 400 sessions; also the initiation look-back
INITIATIONS_FROM = date(2017, 8, 1)  # card: initiations count only from here (the feed starts 2016-01)
DIV_TOP, DIV_MIN_CLOSE, HOLD_SESSIONS, DIV_CAP = 1500, 5.0, 63, 0.04  # card: top 1,500, close >= $5, 63 sessions, 4%
# migrant card
OLD_TOP, NEW_FIRST, NEW_LAST, MIGRANT_MIN_CLOSE, MIGRANT_CAP = 1000, 1001, 1300, 1.0, 0.03  # card


def last_session_of_month(sessions: Sequence[date], month: int) -> list[date]:
    s = pd.Series(sessions, index=pd.to_datetime(sessions))
    last = s.groupby([s.index.year, s.index.month]).last()
    return [d for (_, m), d in last.items() if m == month]


def week_ends(sessions: Sequence[date]) -> list[date]:
    """Last session of each ISO week."""
    return [d for d, nxt in zip(sessions, [*sessions[1:], None], strict=True)
            if nxt is None or nxt.isocalendar()[:2] != d.isocalendar()[:2]]


def recon_day(year: int, sessions: Sequence[date]) -> date | None:
    """The session after the last Friday of June."""
    last_friday = max(date(year, 6, d) for d in range(24, 31) if date(year, 6, d).weekday() == 4)
    later = [d for d in sessions if d > last_friday]
    return later[0] if later else None


def capped_book(names: Sequence[str], cap: float) -> pd.Series:
    """Equal weight capped at ``cap``; the rest of the book in SPY."""
    w = pd.Series(min(1.0 / len(names), cap), index=list(names)) if names else pd.Series(dtype=float)
    rest = 1.0 - float(w.sum())
    return pd.concat([w, pd.Series({MARKET: rest})]) if rest > 1e-12 else w


def dividend_events(div: pd.DataFrame, sessions: Sequence[date], first_bar: dict[str, int]) -> pd.DataFrame:
    """symbol, day (session position), kind (increase | initiation) of the card's events."""
    pos = {d: i for i, d in enumerate(sessions)}
    reg = div.loc[~div["special"].fillna(False).astype(bool) & ~div["foreign"].fillna(False).astype(bool)]
    reg = reg.assign(day=pd.to_datetime(reg["ex_date"]).dt.date.map(pos)).dropna(subset=["day", "rate_adj"])
    reg = reg.loc[reg["rate_adj"] > 0].sort_values(["store_symbol", "day"], kind="mergesort")
    rows: list[dict[str, Any]] = []
    for sym, g in reg.groupby("store_symbol", sort=False):
        days, rates = g["day"].astype(int).to_numpy(), g["rate_adj"].astype(float).to_numpy()
        for k in range(len(days)):
            prev = [j for j in range(k) if 0 < days[k] - days[j] <= PREVIOUS_WITHIN]
            if prev:
                ratio = rates[k] / rates[prev[-1]]
                if MIN_RISE <= ratio <= MAX_RISE:
                    rows.append({"symbol": sym, "day": int(days[k]), "kind": "increase"})
            elif (days[k] - first_bar.get(sym, days[k]) >= PREVIOUS_WITHIN
                  and sessions[days[k]] >= INITIATIONS_FROM and not any(0 < days[k] - d <= PREVIOUS_WITHIN for d in days[:k])):
                rows.append({"symbol": sym, "day": int(days[k]), "kind": "initiation"})
    return pd.DataFrame(rows, columns=["symbol", "day", "kind"]).drop_duplicates(["symbol", "day"])


def dividend_orders(events: pd.DataFrame, eligible: Any, sessions: Sequence[date], kinds: Sequence[str] | None = None
                    ) -> dict[date, pd.Series]:
    """Weekly target books (traded at the next session's open). ``eligible(day) -> set`` on the event's ex-date."""
    ev = events if kinds is None else events.loc[events["kind"].isin(kinds)]
    ok = ev.loc[[r.symbol in eligible(sessions[r.day]) for r in ev.itertuples()]]
    orders: dict[date, pd.Series] = {}
    for t in week_ends(sessions):
        i = sessions.index(t)
        if i + 1 >= len(sessions):
            break
        names = sorted(set(ok.loc[(ok["day"] > i - HOLD_SESSIONS) & (ok["day"] <= i), "symbol"]))
        orders[sessions[i + 1]] = capped_book(names, DIV_CAP)
    return orders


def migrant_orders(ranks_at: Any, sessions: Sequence[date], promoted: bool = False) -> tuple[dict[date, pd.Series], dict[int, int]]:
    """Yearly target books from the reconstitution day of each year with two April rank days; SPY before the first.
    ``promoted`` swaps the sides (ranked 1,001-1,300 last year and 1-1,000 this year; descriptive)."""
    ranks = {d.year: ranks_at(d) for d in last_session_of_month(sessions, 4)}
    orders: dict[date, pd.Series] = {sessions[0]: pd.Series({MARKET: 1.0})}
    counts: dict[int, int] = {}
    for year in sorted(ranks):
        if year - 1 not in ranks:
            continue
        old, new = ranks[year - 1], ranks[year]
        both = old.index.intersection(new.index)
        if promoted:
            pick = both[(old[both] >= NEW_FIRST) & (old[both] <= NEW_LAST) & (new[both] <= OLD_TOP)]
        else:
            pick = both[(old[both] <= OLD_TOP) & (new[both] >= NEW_FIRST) & (new[both] <= NEW_LAST)]
        day = recon_day(year, sessions)
        if day is not None:
            orders[day] = capped_book(sorted(pick), MIGRANT_CAP)
            counts[year] = len(pick)
    return orders, counts


def verdict(res: dict[str, dict[str, Any]]) -> tuple[list[bool], str]:
    """Either route (docs/gates.md, Full-period test): the rule in both halves, or in the pooled window with
    alpha > 0 in each half."""
    crit = alpha_t_critical(N_TRIALS)

    def rule(w: str) -> bool:
        r = res[w]
        return (r["stats"]["haircut_sharpe"] > 0 and r["vs"].get("alpha_ann", -1.0) > 0
                and r["vs"].get("alpha_t", -1.0) >= crit)

    halves = all(rule(w) for w in b9.WINDOWS)
    pooled = rule("pooled") and all(res[w]["vs"].get("alpha_ann", -1.0) > 0 for w in b9.WINDOWS)
    return [halves, pooled], "PASS" if halves or pooled else "FAIL"


def book_for(orders: dict[date, pd.Series], opens: pd.DataFrame, closes: pd.DataFrame, costs: pd.DataFrame,
             delist: dict[str, float], lo: date, hi: date) -> pd.DataFrame:
    span = closes.loc[lo:hi]
    before = [d for d in sorted(orders) if d <= span.index[0]]
    window = {d: o for d, o in orders.items() if span.index[0] < d <= span.index[-1]}
    if before:
        window[span.index[0]] = orders[before[-1]]
    return simulate(opens.loc[lo:hi], span, costs, window, delist)


def render(results: dict[str, dict[str, dict[str, Any]]], extra: list[str]) -> list[str]:
    crit = alpha_t_critical(N_TRIALS)
    lines = ["# Batch 11 results", "", f"Spec: `{SPEC}`. Generated by `swing_engine.research.b11_books`; net of costs, "
             "price-only bars; alpha with BIL's daily return taken off both sides (docs/gates.md, Bill rate).", ""]
    for card, res in results.items():
        routes, word = verdict(res)
        lines += [f"## `{card}`: {word}", "", f"Route 1 (both halves, alpha t >= {crit:.3f}): {'met' if routes[0] else 'not met'}. "
                  f"Route 2 (pooled 2017-26, alpha > 0 in each half): {'met' if routes[1] else 'not met'}.", "",
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
    return [*lines, *extra, "", "## Verdicts", *[f"- **{c}**: {verdict(r)[1]}" for c, r in results.items()]]


def run(store_path: str | Path, out: str | Path = OUT, trials_path: str | Path = DEFAULT_TRIALS_PATH,
        counts_only: bool = False) -> dict[str, Any]:
    """The whole pre-registered run. ``counts_only``: build the order lists and print their counts (the harness
    check: no book is simulated, no return computed), then stop."""
    from swing_engine.data.delisted import delisting_returns
    from swing_engine.data.dividends import mapped
    from swing_engine.data.fundamentals import EVENTS_TABLE, SPLITS_TABLE, share_issuance_features
    from swing_engine.data.store import Store

    end = WINDOWS["pooled"][1]
    with Store(str(store_path), read_only=True) as store:
        bars = store.read_bars(None, b9.DATA_START, end)
        bars = bars.assign(day=_bar_days(bars["ts"]))
        closes = bars.pivot(index="day", columns="symbol", values="close").sort_index()
        opens = bars.pivot(index="day", columns="symbol", values="open").reindex(closes.index)
        dollar_volume = bars.assign(dv=bars["close"] * bars["volume"]).pivot(
            index="day", columns="symbol", values="dv").reindex(closes.index)
        delist = delisting_returns(store)
        div = mapped(store)
        sessions = [d for d in trading_days(b9.DATA_START, end) if d in closes.index]
        cache: dict[date, pd.DataFrame] = {}
        filings, splits = store.read_table(EVENTS_TABLE), store.read_table(SPLITS_TABLE)  # read once, not per day

        def caps(day: date) -> pd.DataFrame:
            """mcap_pit and as-traded close on ``day``, without the share-count unit errors (b9 guard)."""
            if day not in cache:
                rows = bars.loc[bars["day"] == day, ["symbol", "ts", "close"]]
                feats = share_issuance_features(filings, splits, rows)
                got = pd.DataFrame({"mcap_pit": feats["mcap_pit"].to_numpy(), "close_as_traded": feats["close_as_traded"].to_numpy()},
                                   index=rows["symbol"].to_numpy()).astype(float)
                dv = dollar_volume.loc[:day].tail(b9.DV_SESSIONS).median().reindex(got.index)
                cache[day] = got.loc[got["mcap_pit"] <= b9.MAX_MCAP_TO_DOLLAR_VOLUME * dv].dropna(subset=["mcap_pit"])
            return cache[day]

        def div_eligible(day: date) -> set[str]:
            c = caps(day)
            top = c["mcap_pit"].sort_values(ascending=False, kind="mergesort").iloc[:DIV_TOP]
            return set(top.index[c.loc[top.index, "close_as_traded"] >= DIV_MIN_CLOSE])

        def ranks_at(day: date) -> pd.Series:
            c = caps(day)
            c = c.loc[c["close_as_traded"] >= MIGRANT_MIN_CLOSE, "mcap_pit"]
            return c.rank(ascending=False, method="first")

        first_bar = {s: int(np.argmax(closes[s].notna().to_numpy())) for s in closes.columns}
        events = dividend_events(div.loc[pd.to_datetime(div["ex_date"]).dt.date <= end], sessions, first_bar)
        plans = {DIVIDEND: dividend_orders(events, div_eligible, sessions)}
        plans[MIGRANT], counts = migrant_orders(ranks_at, sessions)
        descriptive = {"dividend increases only": dividend_orders(events, div_eligible, sessions, ["increase"]),
                       "dividend initiations only": dividend_orders(events, div_eligible, sessions, ["initiation"]),
                       "promoted (the other side of the line)": migrant_orders(ranks_at, sessions, promoted=True)[0]}
    if counts_only:
        for card, orders in plans.items():
            names = [len(set(w.index) - {MARKET}) for w in orders.values()]
            spy_w = [float(w.get(MARKET, 0.0)) for w in orders.values()]
            print(card, "orders", len(orders), "names min/median/max", min(names), int(np.median(names)), max(names),
                  "SPY weight median", round(float(np.median(spy_w)), 2), flush=True)
        print("events", events["kind"].value_counts().to_dict(), "migrant cohorts", counts, flush=True)
        return {}
    traded = sorted({s for p in [*plans.values(), *descriptive.values()] for w in p.values() for s in w.index})
    costs = cost_table(bars.loc[bars["symbol"].isin(traded)]).pivot(index="as_of", columns="symbol", values="cost_bps")
    spy, rf = closes[MARKET].pct_change(fill_method=None), closes[BILL].pct_change(fill_method=None)
    results = {card: {w: b9.grade(book_for(orders, opens, closes, costs, delist, lo, hi), spy, N_TRIALS, rf)
                      for w, (lo, hi) in WINDOWS.items()} for card, orders in plans.items()}
    extra = ["## Descriptive (not trials)", "",
             f"Events: {int((events['kind'] == 'increase').sum())} increases, {int((events['kind'] == 'initiation').sum())} "
             f"initiations before the eligibility screen. Migrant cohort sizes by year: {counts}.", "",
             "| book | window | return/yr | deepest drop | alpha/yr | alpha t |", "|---|---|---|---|---|---|"]
    for name, orders in descriptive.items():
        for w, (lo, hi) in WINDOWS.items():
            g = b9.grade(book_for(orders, opens, closes, costs, delist, lo, hi), spy, N_TRIALS, rf)
            extra.append(f"| {name} | {w} | {b9._pct(g['stats']['cagr'])} | {b9._pct(-g['stats']['max_dd'])} | "
                         f"{b9._pct(g['vs'].get('alpha_ann', math.nan))} | {g['vs'].get('alpha_t', math.nan):.2f} |")
    if not any(TAG in (r.get("tags") or []) for r in iter_trials(trials_path)):
        for card, res in results.items():
            word = verdict(res)[1]
            log_trial(card, {"windows": {w: [str(lo), str(hi)] for w, (lo, hi) in WINDOWS.items()}, "spec": SPEC,
                             "n_trials": N_TRIALS}, {**res["pooled"]["stats"], **res["pooled"]["vs"]}, trials_path,
                      tags=[TAG], notes=f"pre-registered batch 11 card (one trial, three views); verdict {word}")
    lines = render(results, extra)
    path = Path(out) if Path(out).is_absolute() else ROOT / out
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)
    return results


def main(argv: Sequence[str] | None = None) -> None:
    from swing_engine.core.config import load_settings

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settings", default="config/prereg_b9.yaml")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--counts-only", action="store_true", help="harness check: order counts only, no simulation")
    args = ap.parse_args(argv)
    run(ROOT / load_settings.__wrapped__(Path(args.settings)).data.store_path, args.out, counts_only=args.counts_only)


if __name__ == "__main__":
    main()
