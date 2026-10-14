"""Batch 12: two weights cards graded with the full-period test and the bill rate (docs/preregistration/
2026-10-14-batch12.md is the spec; this module implements it and nothing else):

* `multi_asset_trend_long_flat`: nine ETFs, each held while its 12-month return is above zero at an inverse-
  volatility weight (a 10% risk budget shared equally, each capped at 30%, total at most 100%); the rest in BIL.
* `industry_neutral_momentum_sp500`: the 100 of the 500 largest names with the best 12-1 return minus their two-digit
  SIC industry's median, 1% each, buffer 150, quarterly; unused weight and everything before the first trade in SPY.

Run once (store: config/prereg_b12.yaml -> data/live/replay_b12.duckdb)::

    uv run python -m swing_engine.research.b12_books --settings config/prereg_b12.yaml
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
from swing_engine.research.costs import cost_table
from swing_engine.research.prereg_eval import _bar_days, alpha_t_critical
from swing_engine.research.trials import DEFAULT_TRIALS_PATH, iter_trials, log_trial

SPEC = "docs/preregistration/2026-10-14-batch12.md"
OUT = "docs/preregistration/2026-10-14-batch12-results.md"
TAG = "prereg-b12"
TREND, INDMOM = "multi_asset_trend_long_flat", "industry_neutral_momentum_sp500"
TRIALS = {TREND: 2, INDMOM: 4}  # cards: a new family in a 2-card batch (bar 2.241); momentum family trial 4 (2.498)
MARKET, BILL = "SPY", "BIL"
# trend card
ASSETS = ["SPY", "EFA", "EEM", "VNQ", "IEF", "TLT", "GLD", "DBC", "UUP"]  # card: fixed list
TREND_SESSIONS, VOL_SESSIONS = 252, 63  # card: 12-month return; 63-session volatility
RISK_BUDGET, MAX_ASSET_WEIGHT = 0.10, 0.30  # card: (0.10 / 9) / sigma, capped at 0.30, total <= 1
# industry-neutral momentum card
REF_MONTHS = (2, 5, 8, 11)  # card: last session of Feb, May, Aug, Nov; trade after the third Friday of the next month
TOP, MIN_CLOSE, MIN_HISTORY = 500, 10.0, 273  # card: 500 largest, as-traded close >= $10, >= 273 sessions
MOM_LONG, MOM_SKIP = 273, 21  # card: close 21 sessions before / close 273 sessions before - 1
MIN_INDUSTRY, OTHER = 5, -1.0  # card: industries under 5 members pooled into "other"
HOLD, STAY, WEIGHT = 100, 150, 0.01  # card: top 100, buffer 150, 1% each


# ------------------------------------------------------------------------------------------------ trend card
def trend_weights(closes: pd.DataFrame, i: int) -> pd.Series:
    """Target weights from the closes up to row ``i`` (the signal day); empty before enough history."""
    if i < TREND_SESSIONS:
        return pd.Series(dtype=float)
    c = closes.iloc[: i + 1][ASSETS]
    on = c.iloc[-1] > c.iloc[-1 - TREND_SESSIONS]
    sigma = c.pct_change(fill_method=None).iloc[-VOL_SESSIONS:].std(ddof=1) * math.sqrt(252)
    w = ((RISK_BUDGET / len(ASSETS)) / sigma).clip(upper=MAX_ASSET_WEIGHT).where(on & sigma.gt(0), 0.0).fillna(0.0)
    if w.sum() > 1.0:
        w = w / w.sum()
    w = w[w > 0]
    rest = 1.0 - float(w.sum())
    return pd.concat([w, pd.Series({BILL: rest})]) if rest > 1e-12 else w


def trend_orders(closes: pd.DataFrame, sessions: Sequence[date]) -> dict[date, pd.Series]:
    """Monthly books: signal on each month's last session, traded at the next session's open."""
    idx = {d: i for i, d in enumerate(closes.index)}
    orders: dict[date, pd.Series] = {}
    for t in [d for m in range(1, 13) for d in b11.last_session_of_month(sessions, m)]:
        k = sessions.index(t)
        if k + 1 < len(sessions):
            w = trend_weights(closes, idx[t])
            if not w.empty:
                orders[sessions[k + 1]] = w
    return dict(sorted(orders.items()))


# ------------------------------------------------------------------------------------------------ industry momentum
def industry_scores(raw: pd.Series, industry: pd.Series) -> pd.Series:
    """raw - the median raw of its industry; industries with fewer than MIN_INDUSTRY names form one 'other' group."""
    ind = industry.reindex(raw.index).fillna(OTHER)
    size = ind.map(ind.value_counts())
    ind = ind.where(size >= MIN_INDUSTRY, OTHER)
    return raw - raw.groupby(ind).transform("median")


def momentum_orders(closes: pd.DataFrame, caps: Any, industry: pd.Series, sessions: Sequence[date]) -> dict[date, pd.Series]:
    """Quarterly books (``caps(day) -> DataFrame[mcap_pit, close_as_traded]``); SPY before the first."""
    idx = {d: i for i, d in enumerate(closes.index)}
    hist = closes.notna().cumsum()
    orders: dict[date, pd.Series] = {sessions[0]: pd.Series({MARKET: 1.0})}
    current: set[str] = set()
    refs = sorted(d for m in REF_MONTHS for d in b11.last_session_of_month(sessions, m))
    for ref in refs:
        i = idx[ref]
        day = _after_third_friday(ref, sessions)
        if i < MOM_LONG or day is None:
            continue
        c = caps(ref)
        ok = (c["close_as_traded"] >= MIN_CLOSE) & (hist.iloc[i].reindex(c.index) >= MIN_HISTORY)
        uni = c.loc[ok, "mcap_pit"].sort_values(ascending=False, kind="mergesort").iloc[:TOP].index
        raw = (closes.iloc[i - MOM_SKIP][uni] / closes.iloc[i - MOM_LONG][uni] - 1.0).dropna()
        score = industry_scores(raw, industry)
        held = b9.select(score, current, hold=HOLD, enter=HOLD, stay=STAY)
        orders[day] = b11.capped_book(held, WEIGHT) if len(held) else pd.Series({MARKET: 1.0})
        current = set(held)
    return orders


def _after_third_friday(ref: date, sessions: Sequence[date]) -> date | None:
    """First session after the third Friday of the month after ``ref``."""
    year, month = (ref.year + 1, 1) if ref.month == 12 else (ref.year, ref.month + 1)
    first = date(year, month, 1)
    third_friday = first + pd.Timedelta(days=(4 - first.weekday()) % 7 + 14)
    later = [d for d in sessions if d > third_friday]
    return later[0] if later else None


# ------------------------------------------------------------------------------------------------ run
def render(results: dict[str, dict[str, dict[str, Any]]], extra: list[str]) -> list[str]:
    lines = ["# Batch 12 results", "", f"Spec: `{SPEC}`. Generated by `swing_engine.research.b12_books`; net of costs, "
             "price-only bars; alpha from (book - BIL) on (SPY - BIL) (docs/gates.md).", ""]
    for card, res in results.items():
        n = TRIALS[card]
        routes, word = b11.verdict(res, n)
        lines += [f"## `{card}`: {word}", "", f"Trials {n}, bar alpha t >= {alpha_t_critical(n):.3f}. Route 1 (both "
                  f"halves): {'met' if routes[0] else 'not met'}. Route 2 (pooled 2017-26, alpha > 0 in each half): "
                  f"{'met' if routes[1] else 'not met'}.", "",
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
    return [*lines, *extra, "", "## Verdicts",
            *[f"- **{c}**: {b11.verdict(r, TRIALS[c])[1]}" for c, r in results.items()]]


def run(store_path: str | Path, out: str | Path = OUT, trials_path: str | Path = DEFAULT_TRIALS_PATH,
        counts_only: bool = False) -> dict[str, Any]:
    """The pre-registered run. ``counts_only``: build the order lists, print their counts, stop (harness check)."""
    from swing_engine.data.delisted import delisting_returns
    from swing_engine.data.fundamentals import EVENTS_TABLE, SPLITS_TABLE, share_issuance_features
    from swing_engine.data.sic import sic2
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
        industry = store.read_table("sic").drop_duplicates("symbol").set_index("symbol")["sic"].map(sic2)
        sessions = [d for d in trading_days(b9.DATA_START, end) if d in closes.index]

        def caps(day: date) -> pd.DataFrame:
            rows = bars.loc[bars["day"] == day, ["symbol", "ts", "close"]]
            f = share_issuance_features(filings, splits, rows)
            got = pd.DataFrame({"mcap_pit": f["mcap_pit"].to_numpy(), "close_as_traded": f["close_as_traded"].to_numpy()},
                               index=rows["symbol"].to_numpy()).astype(float)
            dv = dollar_volume.loc[:day].tail(b9.DV_SESSIONS).median().reindex(got.index)
            return got.loc[got["mcap_pit"] <= b9.MAX_MCAP_TO_DOLLAR_VOLUME * dv].dropna(subset=["mcap_pit"])

        plans = {TREND: trend_orders(closes, sessions), INDMOM: momentum_orders(closes, caps, industry, sessions)}
        replica = b9.momentum_orders(closes, b9.mcap_function(store, bars, closes), sessions)
    if counts_only:
        for card, orders in plans.items():
            sizes = [len(set(w.index) - {MARKET, BILL}) for w in orders.values()]
            parked = [float(w.get(BILL, 0.0) + w.get(MARKET, 0.0) * (card == INDMOM)) for w in orders.values()]
            print(card, "orders", len(orders), "first", min(orders), "names min/median/max", min(sizes),
                  int(np.median(sizes)), max(sizes), "parked weight median", round(float(np.median(parked)), 2), flush=True)
        return {}
    traded = sorted({s for p in [*plans.values(), replica] for w in p.values() for s in w.index})
    costs = cost_table(bars.loc[bars["symbol"].isin(traded)]).pivot(index="as_of", columns="symbol", values="cost_bps")
    spy, rf = closes[MARKET].pct_change(fill_method=None), closes[BILL].pct_change(fill_method=None)
    results, books = {}, {}
    for card, orders in plans.items():
        results[card] = {}
        for w, (lo, hi) in b11.WINDOWS.items():
            book = b11.book_for(orders, opens, closes, costs, delist, lo, hi)
            results[card][w] = b9.grade(book, spy, TRIALS[card], rf)
            books[(card, w)] = book
    extra = ["## Descriptive (not part of the verdicts)", ""]
    pooled_trend = books[(TREND, "pooled")]["ret"]
    monthly = pd.DataFrame({"book": pooled_trend, "spy": spy.reindex(pooled_trend.index)})
    monthly = (1.0 + monthly).groupby([d.strftime("%Y-%m") for d in monthly.index]).prod() - 1.0
    extra.append(f"- `{TREND}`: correlation of monthly returns with SPY over the pooled window: "
                 f"{monthly['book'].corr(monthly['spy']):.2f}.")
    pooled_mom = books[(INDMOM, "pooled")]["ret"]
    te = float((pooled_mom - spy.reindex(pooled_mom.index)).std(ddof=1) * math.sqrt(252))
    rep = b9.grade(b11.book_for(replica, opens, closes, costs, delist, *b11.WINDOWS["pooled"]), spy, TRIALS[INDMOM], rf)
    extra += [f"- `{INDMOM}`: tracking error against SPY over the pooled window {te:.1%} a year.",
              f"- Batch 9's `sp500_momentum_index_replica` on the same pooled window (descriptive, not re-graded): "
              f"{b9._pct(rep['stats']['cagr'])} a year, deepest drop {b9._pct(-rep['stats']['max_dd'])}, alpha "
              f"{b9._pct(rep['vs'].get('alpha_ann', math.nan))} with t {rep['vs'].get('alpha_t', math.nan):.2f}.",
              "- CZ check (docs/gates.md): not run. It needs a file downloaded from openassetpricing.com, which this "
              "session does not do without the owner's word; the card asked for it only if the download was possible."]
    if not any(TAG in (r.get("tags") or []) for r in iter_trials(trials_path)):
        for card, res in results.items():
            log_trial(card, {"windows": {w: [str(lo), str(hi)] for w, (lo, hi) in b11.WINDOWS.items()}, "spec": SPEC,
                             "n_trials": TRIALS[card]}, {**res["pooled"]["stats"], **res["pooled"]["vs"]}, trials_path,
                      tags=[TAG], notes=f"pre-registered batch 12 card; verdict {b11.verdict(res, TRIALS[card])[1]}")
    lines = render(results, extra)
    path = Path(out) if Path(out).is_absolute() else ROOT / out
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)
    return results


def main(argv: Sequence[str] | None = None) -> None:
    from swing_engine.core.config import load_settings

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settings", default="config/prereg_b12.yaml")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--counts-only", action="store_true", help="harness check: order counts only, no simulation")
    args = ap.parse_args(argv)
    run(ROOT / load_settings.__wrapped__(Path(args.settings)).data.store_path, args.out, counts_only=args.counts_only)


if __name__ == "__main__":
    main()
