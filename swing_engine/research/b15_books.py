"""Batch 15 (docs/preregistration/2026-10-14-batch15.md is the spec; this module implements it and nothing else):

* `sp500_quality_index_replica` (weights card): twice a year (reference end of May / November, trade after the third
  Friday of June / December), the 100 of the 500 largest names with the best quality score (ROE, minus accruals,
  minus assets / equity), weighted mcap x the replica's score map, capped at 5% and 3 x cap weight; rest in SPY.

Run once::

    uv run python -m swing_engine.research.b15_books --settings config/prereg_b9.yaml
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
from swing_engine.research.b14_books import score_map
from swing_engine.research.costs import cost_table
from swing_engine.research.prereg_eval import _bar_days, alpha_t_critical
from swing_engine.research.trials import DEFAULT_TRIALS_PATH, iter_trials, log_trial

SPEC = "docs/preregistration/2026-10-14-batch15.md"
OUT = "docs/preregistration/2026-10-14-batch15-results.md"
TAG = "prereg-b15"
CARD = "sp500_quality_index_replica"
N_TRIALS = 3  # card: profitability/quality family count 3; bar alpha_t_critical(3)
MARKET, ETF = "SPY", "SPHQ"
REF_MONTHS = (5, 11)  # card: last session of May / November; trade after the third Friday of June / December
FIRST_TRADE = date(2017, 6, 1)  # card: SPY before the first rebalance (June 2017)
TOP, MIN_CLOSE, MIN_HISTORY = 500, 10.0, 273  # card
HOLD, ENTER, STAY = 100, 80, 120  # card
MAX_WEIGHT, CAP_MULT, Z_CLIP = 0.05, 3.0, 3.0  # card
#: input -> True when a high value is good quality
INPUTS: dict[str, bool] = {"roe": True, "accruals": False, "leverage": False}


def quality(values: pd.DataFrame) -> pd.Series:
    """Q: each input z-scored (signed so high = good) and winsorised at +/-3, the three averaged, z-scored again."""
    z = pd.DataFrame({c: ((values[c] - values[c].mean()) / values[c].std(ddof=1) * (1 if good else -1)).clip(-Z_CLIP, Z_CLIP)
                      for c, good in INPUTS.items()})
    mean = z.mean(axis=1)
    return (mean - mean.mean()) / mean.std(ddof=1)


def target(mcap: pd.Series, q: pd.Series, held: Sequence[str]) -> pd.Series:
    """mcap x s(Q) over ``held``, each <= 5% and <= 3 x its cap weight in the universe (multiple raised when
    infeasible, b9.caps_for), the rest in SPY."""
    caps = b9.caps_for((mcap / mcap.sum()).reindex(held), MAX_WEIGHT, CAP_MULT)
    w = b9.capped_weights(mcap.reindex(held) * score_map(q.reindex(held)), caps)
    rest = 1.0 - float(w.sum())
    return pd.concat([w, pd.Series({MARKET: rest})]) if rest > 1e-9 else w


def plan(universes: dict[date, pd.DataFrame], first_day: date) -> dict[date, pd.Series]:
    """Orders per rebalance session; ``universes``: per rebalance session, the universe (mcap_pit and the inputs)."""
    orders: dict[date, pd.Series] = {first_day: pd.Series({MARKET: 1.0})}
    current: set[str] = set()
    for day in sorted(universes):
        u = universes[day]
        q = quality(u)
        held = b9.select(q, current, hold=HOLD, enter=ENTER, stay=STAY)
        orders[day] = target(u["mcap_pit"], q, held)
        current = set(held)
    return orders


def run(store_path: str | Path, out: str | Path = OUT, trials_path: str | Path = DEFAULT_TRIALS_PATH,
        counts_only: bool = False) -> dict[str, Any]:
    from swing_engine.data.b5_fundamentals import _read_facts, event_values
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
        sessions = [d for d in trading_days(b9.DATA_START, end) if d in closes.index]
        replica = b9.momentum_orders(closes, b9.mcap_function(store, bars, closes), sessions)
    vals = event_values(facts, filings, splits)
    vals = vals.assign(avail=_norm_ts(vals["avail_ts"]).dt.date).dropna(subset=["avail"]).sort_values("avail", kind="mergesort")
    with np.errstate(divide="ignore", invalid="ignore"):
        vals = vals.assign(roe=vals["roa"] * vals["assets"] / vals["equity"], leverage=vals["assets"] / vals["equity"])
    idx = {d: i for i, d in enumerate(closes.index)}
    hist = closes.notna().cumsum()
    universes: dict[date, pd.DataFrame] = {}
    for ref in sorted(d for m in REF_MONTHS for d in b11.last_session_of_month(sessions, m)):
        day = b12._after_third_friday(ref, sessions)
        if day is None or day < FIRST_TRADE:
            continue
        rows = bars.loc[bars["day"] == ref, ["symbol", "ts", "close"]]
        f = share_issuance_features(filings, splits, rows)
        s = pd.DataFrame({"mcap_pit": f["mcap_pit"].to_numpy(), "close_as_traded": f["close_as_traded"].to_numpy()},
                         index=rows["symbol"].to_numpy())
        dv = dollar_volume.loc[:ref].tail(b9.DV_SESSIONS).median().reindex(s.index)
        latest = vals.loc[vals["avail"] <= ref].drop_duplicates("symbol", keep="last").set_index("symbol")
        s = s.join(latest[["equity", *INPUTS]], how="inner")
        ok = ((s["mcap_pit"] <= b9.MAX_MCAP_TO_DOLLAR_VOLUME * dv.reindex(s.index)) & (s["close_as_traded"] >= MIN_CLOSE)
              & (hist.iloc[idx[ref]].reindex(s.index) >= MIN_HISTORY) & (s["equity"] > 0)
              & np.isfinite(s[list(INPUTS)]).all(axis=1))
        s = s.loc[ok]
        universes[day] = s.loc[s["mcap_pit"].sort_values(ascending=False, kind="mergesort").index[:TOP]]
    orders = plan(universes, sessions[0])
    if counts_only:
        books = [w for d, w in orders.items() if d != sessions[0]]
        names = [len(set(w.index) - {MARKET}) for w in books]
        changes = [len(set(b.index) ^ set(a.index)) // 2 for a, b in zip(books, books[1:])]
        print(CARD, "rebalances", len(books), "first", min(d for d in orders if d != sessions[0]), "names min/median/max",
              min(names), int(np.median(names)), max(names), "universe min", min(len(u) for u in universes.values()),
              "names changed per rebalance median", int(np.median(changes)), "largest weight",
              round(max(float(w.drop(MARKET, errors="ignore").max()) for w in books), 3), "SPY leftover max",
              round(max(float(w.get(MARKET, 0.0)) for w in books), 3), flush=True)
        return {}
    traded = sorted({s for p in (orders, replica) for w in p.values() for s in w.index} | {MARKET, b11.BILL})
    costs = cost_table(bars.loc[bars["symbol"].isin(traded)]).pivot(index="as_of", columns="symbol", values="cost_bps")
    spy, rf = closes[MARKET].pct_change(fill_method=None), closes[b11.BILL].pct_change(fill_method=None)
    books = {w: b11.book_for(orders, opens, closes, costs, delist, lo, hi) for w, (lo, hi) in b11.WINDOWS.items()}
    res = {w: b9.grade(book, spy, N_TRIALS, rf) for w, book in books.items()}
    # descriptive
    rep = b11.book_for(replica, opens, closes, costs, delist, *b11.WINDOWS["pooled"])
    extra = ["## Descriptive (not part of the verdict)", "", "| window | tracking error vs SPY | correlation of daily excess "
             "with batch 9's replica | SPHQ price return/yr |", "|---|---|---|---|"]
    etf = closes[ETF] if ETF in closes else pd.Series(dtype=float)
    for w, book in books.items():
        ex = book["ret"] - spy.reindex(book.index)
        rex = (rep["ret"] - spy.reindex(rep.index)).reindex(book.index)
        e = etf.reindex(book.index)
        full = e.notna().all() and len(e) > 1
        etf_ret = (float(e.iloc[-1] / e.iloc[0]) ** (252.0 / (len(e) - 1)) - 1.0) if full else math.nan
        extra.append(f"| {w} | {ex.std(ddof=1) * math.sqrt(252):.1%} | {ex.corr(rex):.2f} | "
                     f"{b9._pct(etf_ret) if full else 'not in the store for the whole window'} |")
    if not any(TAG in (r.get("tags") or []) for r in iter_trials(trials_path)):
        log_trial(CARD, {"windows": {w: [str(lo), str(hi)] for w, (lo, hi) in b11.WINDOWS.items()}, "spec": SPEC,
                         "n_trials": N_TRIALS}, {**res["pooled"]["stats"], **res["pooled"]["vs"]}, trials_path,
                  tags=[TAG], notes=f"pre-registered batch 15 card; verdict {b11.verdict(res, N_TRIALS)[1]}")
    routes, word = b11.verdict(res, N_TRIALS)
    lines = ["# Batch 15 results", "", f"Spec: `{SPEC}`. Generated by `swing_engine.research.b15_books`; net of costs, "
             f"price-only bars; alpha from (book - BIL) on (SPY - BIL). Profitability/quality family trials {N_TRIALS}, "
             f"bar alpha t >= {alpha_t_critical(N_TRIALS):.3f}.", "",
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
