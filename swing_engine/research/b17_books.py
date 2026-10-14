"""Batch 17 (docs/preregistration/2026-10-14-batch17.md is the spec; this module implements it and nothing else):

* `sp500_low_volatility_replica` (weights card): quarterly (reference end of Jan / Apr / Jul / Oct, trade after the
  third Friday of the next month), the 100 lowest 252-day-volatility names of the 500 largest (holders kept within the
  lowest 130), weighted 1 / volatility capped at 3%; SPY before February 2017.
* `premise_check_french_low_variance`: not a trial; CAPM on French's value-weighted lowest-variance quintile, 1963-.

Run once::

    uv run python -m swing_engine.research.b17_books --settings config/prereg_b9.yaml
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
from swing_engine.research import b14_books as b14
from swing_engine.research.costs import cost_table
from swing_engine.research.prereg_eval import _bar_days, alpha_t_critical
from swing_engine.research.trials import DEFAULT_TRIALS_PATH, iter_trials, log_trial

SPEC = "docs/preregistration/2026-10-14-batch17.md"
OUT = "docs/preregistration/2026-10-14-batch17-results.md"
TAG = "prereg-b17"
CARD, PREMISE = "sp500_low_volatility_replica", "premise_check_french_low_variance"
N_TRIALS = 2  # card: low-risk family trial 1, bar raised one step: alpha_t_critical(2)
MARKET = "SPY"
REF_MONTHS = (1, 4, 7, 10)  # card: last session of Jan / Apr / Jul / Oct
FIRST_TRADE = date(2017, 2, 1)  # card: SPY before the first rebalance (February 2017)
TOP, MIN_CLOSE, MIN_HISTORY, VOL_SESSIONS = 500, 5.0, 253, 252  # card
HOLD, STAY, MAX_WEIGHT = 100, 130, 0.03  # card
VAR_FILE = "Portfolios_Formed_on_VAR_CSV.zip"
SUBPERIODS = (("1963-07", "1989-12"), ("1990-01", "2016-12"), ("2017-01", "2100-12"))


def target(vol: pd.Series, held: Sequence[str]) -> pd.Series:
    """1 / vol over ``held``, each <= 3%; with fewer than HOLD names the missing share goes to SPY."""
    if not held:
        return pd.Series({MARKET: 1.0})
    inv = 1.0 / vol.reindex(held)
    w = b9.capped_weights(inv, pd.Series(MAX_WEIGHT, index=inv.index)) * min(1.0, len(held) / HOLD)
    rest = 1.0 - float(w.sum())
    return pd.concat([w, pd.Series({MARKET: rest})]) if rest > 1e-9 else w


def plan(vols: dict[date, pd.Series], first_day: date) -> dict[date, pd.Series]:
    """``vols``: per rebalance session, the universe's annualised volatility. Holders stay within the lowest STAY;
    new names fill from the lowest up (b9.select on -vol with no entry limit)."""
    orders: dict[date, pd.Series] = {first_day: pd.Series({MARKET: 1.0})}
    current: set[str] = set()
    for day in sorted(vols):
        v = vols[day].dropna()
        held = b9.select(-v, current, hold=HOLD, enter=len(v), stay=STAY)
        orders[day] = target(v, held)
        current = set(held)
    return orders


def premise(text: str, ff_text: str, ours: pd.Series | None) -> list[str]:
    var, ff = b14.french_monthly(text), b14.french_monthly(ff_text)
    data = pd.DataFrame({"lo": var["Lo 20"], "hi": var["Hi 20"], "mkt": ff["Mkt-RF"], "rf": ff["RF"]}).dropna()
    full = b14.capm(data["lo"] - data["rf"], data["mkt"])
    subs = {f"{lo} .. {min(hi, data.index[-1])}": b14.capm((data["lo"] - data["rf"]).loc[lo:hi], data["mkt"].loc[lo:hi])
            for lo, hi in SUBPERIODS}
    supported = full["t_ols"] >= b14.SUPPORT_T and all(r["alpha_ann"] > 0 for r in subs.values())
    rows = [("Lo 20, full window", full), *((f"Lo 20, {k}", v) for k, v in subs.items()),
            ("Hi 20, full window", b14.capm(data["hi"] - data["rf"], data["mkt"])),
            ("Lo 20 - Hi 20, full window", b14.capm(data["lo"] - data["hi"], data["mkt"]))]
    lines = [f"## `{PREMISE}`: premise {'SUPPORTED' if supported else 'NOT SUPPORTED'}", "",
             f"Ken French library `{VAR_FILE}` (downloaded 2026-10-14 from the approved library; value-weighted monthly, "
             f"60-day return variance) and `{b14.FRENCH_FILES['ff3']}`, {data.index[0]} .. {data.index[-1]}. Not a trial and "
             f"not a pass route. Support needs Lo 20 CAPM alpha t (OLS) >= {b14.SUPPORT_T:.1f} over the full window and "
             "alpha > 0 in each subperiod.", "",
             "| series | months | alpha/yr | t (OLS) | t (Newey-West 6) | beta |", "|---|---|---|---|---|---|",
             *[f"| {k} | {v['months']} | {v['alpha_ann']:+.2%} | {v['t_ols']:.2f} | {v['t_nw']:.2f} | {v['beta']:.2f} |"
               for k, v in rows]]
    if ours is not None:
        french = (data["lo"] - (data["mkt"] + data["rf"])).loc["2017-01":]
        both = pd.DataFrame({"french": french, "ours": ours}).dropna()
        corr = float(both["french"].corr(both["ours"]))
        same = bool(np.sign(both["french"].mean()) == np.sign(both["ours"].mean()))
        lines += ["", f"Link to the card ({both.index[0]} .. {both.index[-1]}, {len(both)} months): correlation of Lo 20 "
                  f"minus the market with the card minus SPY {corr:.2f}; means {both['french'].mean():+.2%} and "
                  f"{both['ours'].mean():+.2%} a month. {'Consistent' if corr >= b14.CONSISTENT_CORR and same else 'Not consistent'}"
                  f" with the premise (needs >= {b14.CONSISTENT_CORR} and same-sign means)."]
    return lines + [""]


def _monthly(r: pd.Series) -> pd.Series:
    return (1.0 + r).groupby([d.strftime("%Y-%m") for d in r.index]).prod() - 1.0


def _load(store_path: str | Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, float], Any, Any]:
    from swing_engine.data.delisted import delisting_returns
    from swing_engine.data.fundamentals import EVENTS_TABLE, SPLITS_TABLE
    from swing_engine.data.store import Store

    with Store(str(store_path), read_only=True) as store:
        bars = store.read_bars(None, b9.DATA_START, b11.WINDOWS["pooled"][1])
        bars = bars.assign(day=_bar_days(bars["ts"]))
        delist = delisting_returns(store)
        filings, splits = store.read_table(EVENTS_TABLE), store.read_table(SPLITS_TABLE)
    closes = bars.pivot(index="day", columns="symbol", values="close").sort_index()
    opens = bars.pivot(index="day", columns="symbol", values="open").reindex(closes.index)
    return bars, closes, opens, delist, filings, splits


def run(store_path: str | Path, out: str | Path = OUT, trials_path: str | Path = DEFAULT_TRIALS_PATH,
        counts_only: bool = False, tr_store_path: str | Path | None = None) -> dict[str, Any]:
    from swing_engine.data.fundamentals import share_issuance_features
    from swing_engine.data.market_series import unzip_text
    from swing_engine.data.store import Store

    bars, closes, opens, delist, filings, splits = _load(store_path)
    end = b11.WINDOWS["pooled"][1]
    sessions = [d for d in trading_days(b9.DATA_START, end) if d in closes.index]
    dollar_volume = bars.assign(dv=bars["close"] * bars["volume"]).pivot(
        index="day", columns="symbol", values="dv").reindex(closes.index)
    idx = {d: i for i, d in enumerate(closes.index)}
    hist = closes.notna().cumsum()
    rets = closes.pct_change(fill_method=None)
    vols: dict[date, pd.Series] = {}
    for ref in sorted(d for m in REF_MONTHS for d in b11.last_session_of_month(sessions, m)):
        day = b12._after_third_friday(ref, sessions)
        if day is None or day < FIRST_TRADE:
            continue
        i = idx[ref]
        rows = bars.loc[bars["day"] == ref, ["symbol", "ts", "close"]]
        f = share_issuance_features(filings, splits, rows)
        s = pd.DataFrame({"mcap_pit": f["mcap_pit"].to_numpy(), "close_as_traded": f["close_as_traded"].to_numpy()},
                         index=rows["symbol"].to_numpy())
        dv = dollar_volume.loc[:ref].tail(b9.DV_SESSIONS).median().reindex(s.index)
        s = s.loc[(s["mcap_pit"] <= b9.MAX_MCAP_TO_DOLLAR_VOLUME * dv) & (s["close_as_traded"] >= MIN_CLOSE)
                  & (hist.iloc[i].reindex(s.index) >= MIN_HISTORY)]
        names = s["mcap_pit"].sort_values(ascending=False, kind="mergesort").index[:TOP]
        vols[day] = rets.iloc[i - VOL_SESSIONS + 1:i + 1][names].std(ddof=1) * math.sqrt(252)
    orders = plan(vols, sessions[0])
    if counts_only:
        books = [w for d, w in orders.items() if d != sessions[0]]
        names_n = [len(set(w.index) - {MARKET}) for w in books]
        changes = [len((set(b.index) ^ set(a.index)) - {MARKET}) // 2 for a, b in zip(books, books[1:], strict=False)]
        print(CARD, "rebalances", len(books), "first", min(d for d in orders if d != sessions[0]), "names min/max",
              min(names_n), max(names_n), "universe min", min(len(v.dropna()) for v in vols.values()),
              "names changed per rebalance median", int(np.median(changes)), "largest weight",
              round(max(float(w.drop(MARKET, errors="ignore").max()) for w in books), 4), flush=True)
        return {}
    with Store(str(store_path), read_only=True) as store:
        replica = {sessions[0]: pd.Series({MARKET: 1.0}),
                   **b9.momentum_orders(closes, b9.mcap_function(store, bars, closes), sessions)}
    traded = sorted({s for p in (orders, replica) for w in p.values() for s in w.index} | {MARKET, b11.BILL})
    costs = cost_table(bars.loc[bars["symbol"].isin(traded)]).pivot(index="as_of", columns="symbol", values="cost_bps")
    spy, rf = closes[MARKET].pct_change(fill_method=None), closes[b11.BILL].pct_change(fill_method=None)
    books = {w: b11.book_for(orders, opens, closes, costs, delist, lo, hi) for w, (lo, hi) in b11.WINDOWS.items()}
    res = {w: b9.grade(book, spy, N_TRIALS, rf) for w, book in books.items()}
    # descriptive
    rep = b11.book_for(replica, opens, closes, costs, delist, *b11.WINDOWS["pooled"])
    rep_m = _monthly(rep["ret"]) - _monthly(spy.reindex(rep.index))
    extra = ["## Descriptive (not part of the verdict)", "", "| window | tracking error vs SPY | monthly excess correlation "
             "with batch 9's replica | total-return store: return/yr, alpha/yr (t) |", "|---|---|---|---|"]
    tr: dict[str, dict[str, Any]] = {}
    if tr_store_path is not None:
        _b, tc, to, tdel, _f, _s = _load(tr_store_path)
        tspy, trf = tc[MARKET].pct_change(fill_method=None), tc[b11.BILL].pct_change(fill_method=None)
        tr = {w: b9.grade(b11.book_for(orders, to, tc, costs, tdel, lo, hi), tspy, N_TRIALS, trf)
              for w, (lo, hi) in b11.WINDOWS.items()}
    for w, book in books.items():
        ex = book["ret"] - spy.reindex(book.index)
        ours = _monthly(book["ret"]) - _monthly(spy.reindex(book.index))
        t = tr.get(w)
        tr_text = (f"{b9._pct(t['stats']['cagr'])}, {b9._pct(t['vs'].get('alpha_ann', math.nan))} "
                   f"({t['vs'].get('alpha_t', math.nan):.2f})") if t else "not run"
        extra.append(f"| {w} | {ex.std(ddof=1) * math.sqrt(252):.1%} | {ours.corr(rep_m.reindex(ours.index)):.2f} | {tr_text} |")
    ours = _monthly(books["pooled"]["ret"]) - _monthly(spy.reindex(books["pooled"].index))
    texts = {k: unzip_text((b14.FRENCH_DIR / v).read_bytes()) for k, v in (("var", VAR_FILE), ("ff3", b14.FRENCH_FILES["ff3"]))}
    premise_lines = premise(texts["var"], texts["ff3"], ours)
    if not any(TAG in (r.get("tags") or []) for r in iter_trials(trials_path)):
        log_trial(CARD, {"windows": {w: [str(lo), str(hi)] for w, (lo, hi) in b11.WINDOWS.items()}, "spec": SPEC,
                         "n_trials": N_TRIALS}, {**res["pooled"]["stats"], **res["pooled"]["vs"]}, trials_path,
                  tags=[TAG], notes=f"pre-registered batch 17 card; verdict {b11.verdict(res, N_TRIALS)[1]}")
    routes, word = b11.verdict(res, N_TRIALS)
    lines = ["# Batch 17 results", "", f"Spec: `{SPEC}`. Generated by `swing_engine.research.b17_books`; net of costs, "
             f"price-only bars; alpha from (book - BIL) on (SPY - BIL). Low-risk family, bar alpha t >= "
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
    lines += ["", *premise_lines, *extra, "", "## Verdict", f"- **{CARD}**: {word}"]
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
    ap.add_argument("--counts-only", action="store_true", help="harness check: order counts only, no graded simulation")
    args = ap.parse_args(argv)
    store = ROOT / load_settings.__wrapped__(Path(args.settings)).data.store_path
    tr = ROOT / load_settings.__wrapped__(Path(args.tr_settings)).data.store_path if args.tr_settings else None
    run(store, args.out, counts_only=args.counts_only, tr_store_path=tr)


if __name__ == "__main__":
    main()
