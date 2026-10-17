"""Batch 26 premise check (docs/proposals/swing-methods-2026-10/batch26/premise_check_french_early_read_2011_2016.md is
the spec; this module implements it and nothing else). Not a trial and not a pass route: it cannot grade or change
batches 24 / 25 (docs/preregistration/2026-10-15-batch24-25.md).

* Calibration, 2017-01 .. latest month: monthly (French cell - market) against our books' monthly (return - SPY), the
  batch 9 replica (price-only store and, beside it, the total-return store) and the batch 16 book.
* Read, 2011-01 .. 2016-12: CAPM of (cell - RF) on Mkt-RF for ME5 PRIOR5, a 0.5 / 0.5 blend with ME5 OP5, and ME5 OP5.
* Labels fixed in the card: Points toward / Points against / Uninformative.

A 5x5 file that is not on the Mac is skipped, as the card says; the 2x3 cells are then reported beside it as a
descriptive substitute, never as the registered read.

Run once::

    uv run python -m swing_engine.research.b26_premise --settings config/prereg_b9.yaml
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from swing_engine.core.config import ROOT
from swing_engine.data.calendar import trading_days
from swing_engine.research import b9_books as b9
from swing_engine.research import b11_books as b11
from swing_engine.research import b14_books as b14
from swing_engine.research import b16_books as b16
from swing_engine.research import b17_books as b17
from swing_engine.research.costs import cost_table

SPEC = "docs/proposals/swing-methods-2026-10/batch26/premise_check_french_early_read_2011_2016.md"
OUT = "docs/preregistration/2026-10-17-batch26-results.md"
FILES = {"prior25": "25_Portfolios_ME_Prior_12_2_CSV.zip", "op25": "25_Portfolios_ME_OP_5x5_CSV.zip",
         "prior6": b14.FRENCH_FILES["prior"], "op6": b14.FRENCH_FILES["op"], "ff3": b14.FRENCH_FILES["ff3"]}
CALIB = ("2017-01", "2100-12")  # card rule 1: 2017-01 .. latest month
READ = ("2011-01", "2016-12")  # card rule 2: 72 months
MIN_CORR, MIN_T = 0.6, 1.0  # card labels
TOWARD, AGAINST, NONE = "Points toward confirmation", "Points against", "Uninformative"


def label(corr: float, alpha: float, t_ols: float) -> str:
    """The card's labels: corr >= 0.6 and alpha > 0 with t >= 1 -> toward; corr >= 0.6 and alpha <= 0 -> against."""
    if not (corr >= MIN_CORR):
        return NONE
    if alpha > 0 and t_ols >= MIN_T:
        return TOWARD
    return AGAINST if alpha <= 0 else NONE


def cells(texts: dict[str, str]) -> tuple[dict[str, pd.Series], pd.DataFrame, list[str]]:
    """French series by name (monthly decimal returns), the FF3 frame, and the files that were missing."""
    ff = b14.french_monthly(texts["ff3"])
    out: dict[str, pd.Series] = {}
    missing = [FILES[k] for k in ("prior25", "op25") if k not in texts]
    if "prior25" in texts:
        p = b14.french_monthly(texts["prior25"])
        out["ME5 PRIOR5"], out["ME5 PRIOR1"] = p["BIG HiPRIOR"], p["BIG LoPRIOR"]
    if "op25" in texts:
        out["ME5 OP5"] = b14.french_monthly(texts["op25"])["BIG HiOP"]
    out["2x3 BIG HiPRIOR"] = b14.french_monthly(texts["prior6"])["BIG HiPRIOR"]
    out["2x3 BIG HiOP"] = b14.french_monthly(texts["op6"])["BIG HiOP"]
    return out, ff, missing


def read_rows(series: dict[str, pd.Series], ff: pd.DataFrame, ours: dict[str, pd.Series],
              ours_capm: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    """One row per portfolio: (registered?, French cell(s), our book it is calibrated on)."""
    mkt = ff["Mkt-RF"] + ff["RF"]
    plan: list[tuple[str, bool, pd.Series | None, str]] = []

    def add(name: str, registered: bool, legs: Sequence[str], book: str) -> None:
        s = 0.5 * (series[legs[0]] + series[legs[1]]) if len(legs) == 2 and all(x in series for x in legs) else (
            series.get(legs[0]) if len(legs) == 1 else None)
        plan.append((name, registered, s, book))

    add("ME5 PRIOR5", True, ["ME5 PRIOR5"], "replica")
    add("0.5 ME5 PRIOR5 + 0.5 ME5 OP5", True, ["ME5 PRIOR5", "ME5 OP5"], "b16")
    add("ME5 OP5", True, ["ME5 OP5"], "b16")
    add("2x3 BIG HiPRIOR (descriptive)", False, ["2x3 BIG HiPRIOR"], "replica")
    add("0.5 2x3 BIG HiPRIOR + 0.5 2x3 BIG HiOP (descriptive)", False, ["2x3 BIG HiPRIOR", "2x3 BIG HiOP"], "b16")
    add("2x3 BIG HiOP (descriptive)", False, ["2x3 BIG HiOP"], "b16")
    rows = []
    for name, registered, s, book in plan:
        if s is None:
            rows.append({"name": name, "registered": registered, "missing": True})
            continue
        ex = (s - mkt).loc[CALIB[0]:CALIB[1]]
        both = pd.DataFrame({"french": ex, "ours": ours[book]}).dropna()
        corr = float(both["french"].corr(both["ours"]))
        cal = b14.capm((s - ff["RF"]).loc[CALIB[0]:CALIB[1]], ff["Mkt-RF"].loc[CALIB[0]:CALIB[1]])
        rd = b14.capm((s - ff["RF"]).loc[READ[0]:READ[1]], ff["Mkt-RF"].loc[READ[0]:READ[1]])
        rows.append({"name": name, "registered": registered, "missing": False, "book": book, "corr": corr,
                     "calib_months": len(both), "calib_end": both.index[-1], "calib": cal, "ours": ours_capm[book],
                     "read": rd, "label": label(corr, rd["alpha_ann"], rd["t_ols"])})
    return rows


def _fmt(c: dict[str, float]) -> str:
    return f"{c['alpha_ann']:+.2%} | {c['t_ols']:.2f} | {c['t_nw']:.2f} | {c['beta']:.2f}"


def report(rows: list[dict[str, Any]], series: dict[str, pd.Series], ff: pd.DataFrame, missing: list[str],
           tr_corr: tuple[str, float] | None) -> list[str]:
    books = {"replica": "batch 9 replica", "b16": "batch 16 book"}
    lines = ["# Batch 26 results: French early read on batches 24 and 25 (premise check, no trials)", "",
             f"Spec: `{SPEC}`. Generated by `swing_engine.research.b26_premise`. Not a trial and not a pass route; "
             "it cannot grade, replace or change batch 24 or 25. Monthly, value-weighted, no costs; CAPM on Mkt-RF; "
             f"Newey-West t with {b14.NW_LAGS} lags. Labels: correlation >= {MIN_CORR}, read-window alpha > 0 and OLS t "
             f">= {MIN_T} -> {TOWARD}; correlation >= {MIN_CORR} and alpha <= 0 -> {AGAINST}; anything else "
             f"{NONE}.", "",
             "Files (Ken French library, value-weighted monthly, built from the 202608 CRSP database): "
             f"{', '.join(f'`{FILES[k]}`' for k in ('prior6', 'op6', 'ff3'))} (downloaded 2026-10-14)"
             + ("" if missing else f"; {FILES['prior25']} and {FILES['op25']} (downloaded 2026-10-17 20:35Z on Jack's "
                "\"Download\" answer to the project-chat card, relayed by the coordinator; the approval covers these "
                "two files only)") + "."]
    if missing:
        lines += ["", f"**Skipped, not on the Mac:** {', '.join(f'`{m}`' for m in missing)}. The fetch was refused "
                  "on this Mac as a new download, so, as the card says, the registered 5x5 rows are not run. The 2x3 "
                  "rows below use the same rules on French's 2x3 cells (big = above the NYSE median, top 30% by prior "
                  "return or profitability): a descriptive substitute, not the registered read."]
    lines += ["", "## Read, 2011-01 .. 2016-12", "",
              "| portfolio | calibrated on | calibration corr | read alpha/yr | t (OLS) | t (NW) | beta | label |",
              "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["missing"]:
            lines.append(f"| {r['name']} | - | - | - | - | - | - | not run (file missing) |")
            continue
        lab = f"**{r['label']}**" if r["registered"] else f"({r['label']}, descriptive)"
        lines.append(f"| {r['name']} | {books[r['book']]} | {r['corr']:.2f} | {_fmt(r['read'])} | {lab} |")
    lines += ["", "## Calibration, 2017-01 .. latest month", "",
              "| portfolio | months | corr with our book's (return - SPY) | French alpha/yr | t (OLS) | t (NW) | beta | "
              "our book alpha/yr | t (OLS) | t (NW) | beta |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if not r["missing"]:
            lines.append(f"| {r['name']} | {r['calib_months']} (to {r['calib_end']}) | {r['corr']:.2f} | "
                         f"{_fmt(r['calib'])} | {_fmt(r['ours'])} |")
    if tr_corr is not None:
        lines += ["", f"Total-return store, beside it: the replica's monthly (return - SPY) on data/live/replay_b9_tr.duckdb "
                  f"correlates {tr_corr[1]:.2f} with {tr_corr[0]} minus the market (price-only: see its row above)."]
    lines += ["", "## Descriptive (rule 3)", "", "| series | window | months | alpha/yr | t (OLS) | t (NW) | beta |",
              "|---|---|---|---|---|---|---|"]
    desc: list[tuple[str, pd.Series]] = [("2x3 BIG HiPRIOR - RF", series["2x3 BIG HiPRIOR"] - ff["RF"])]
    if "ME5 PRIOR5" in series:
        desc.append(("ME5 PRIOR5 - ME5 PRIOR1", series["ME5 PRIOR5"] - series["ME5 PRIOR1"]))
    for name, y in desc:
        for wname, (lo, hi) in (("read 2011-16", READ), ("calibration 2017-", CALIB)):
            c = b14.capm(y.loc[lo:hi], ff["Mkt-RF"].loc[lo:hi])
            lines.append(f"| {name} | {wname} | {c['months']} | {_fmt(c)} |")
    if "ME5 PRIOR5" not in series:
        lines += ["", "ME5 PRIOR5 - ME5 PRIOR1: not run (file missing)."]
    return lines + [""]


def run(store_path: str | Path, tr_store_path: str | Path | None, out: str | Path = OUT) -> list[dict[str, Any]]:
    from swing_engine.data.b5_fundamentals import _read_facts, event_values
    from swing_engine.data.fundamentals import _norm_ts
    from swing_engine.data.market_series import unzip_text
    from swing_engine.data.store import Store

    texts = {k: unzip_text((b14.FRENCH_DIR / v).read_bytes()) for k, v in FILES.items() if (b14.FRENCH_DIR / v).exists()}
    series, ff, missing = cells(texts)
    bars, closes, opens, delist, filings, splits = b17._load(store_path)
    end = b11.WINDOWS["pooled"][1]
    sessions = [d for d in trading_days(b9.DATA_START, end) if d in closes.index]
    with Store(str(store_path), read_only=True) as store:
        facts = _read_facts(store, sorted(set(filings["symbol"].astype(str).str.upper())))
        vals = event_values(facts, filings, splits)
        vals = vals.assign(avail=_norm_ts(vals["avail_ts"]).dt.date).dropna(subset=["avail"]).sort_values(
            "avail", kind="mergesort")

        def combine(ref: Any, uni: pd.Series, z: pd.Series) -> pd.Series:  # batch 16's blend, as registered
            latest = vals.loc[vals["avail"] <= ref].drop_duplicates("symbol", keep="last").set_index("symbol")
            return b16.blend(z, latest["gp_assets"])

        mcap_at = b9.mcap_function(store, bars, closes)
        opening = {sessions[0]: pd.Series({"SPY": 1.0})}
        orders = {"replica": {**opening, **b9.momentum_orders(closes, mcap_at, sessions)},
                  "b16": {**opening, **b9.momentum_orders(closes, mcap_at, sessions, combine=combine)}}
    traded = sorted({s for p in orders.values() for w in p.values() for s in w.index} | {"SPY", b11.BILL})
    costs = cost_table(bars.loc[bars["symbol"].isin(traded)]).pivot(index="as_of", columns="symbol", values="cost_bps")
    pooled = b11.WINDOWS["pooled"]

    def monthly_excess(o: dict, op: pd.DataFrame, cl: pd.DataFrame, dl: dict) -> tuple[pd.Series, dict[str, float]]:
        book = b11.book_for(o, op, cl, costs, dl, *pooled)
        m, spy_m = b17._monthly(book["ret"]), b17._monthly(cl["SPY"].pct_change(fill_method=None).reindex(book.index))
        bil_m = b17._monthly(cl[b11.BILL].pct_change(fill_method=None).reindex(book.index))
        return m - spy_m, b14.capm(m - bil_m, spy_m - bil_m)

    ours, ours_capm = {}, {}
    for k, o in orders.items():
        ours[k], ours_capm[k] = monthly_excess(o, opens, closes, delist)
    tr_corr = None
    if tr_store_path is not None:
        _b, tc, to, tdel, _f, _s = b17._load(tr_store_path)
        tr_ex, _ = monthly_excess(orders["replica"], to, tc, tdel)
        tr_cell = "ME5 PRIOR5" if "ME5 PRIOR5" in series else "2x3 BIG HiPRIOR"
        fr = (series[tr_cell] - (ff["Mkt-RF"] + ff["RF"])).loc[CALIB[0]:]
        both = pd.DataFrame({"f": fr, "o": tr_ex}).dropna()
        tr_corr = (tr_cell, float(both["f"].corr(both["o"])))
    rows = read_rows(series, ff, ours, ours_capm)
    lines = report(rows, series, ff, missing, tr_corr)
    path = Path(out) if Path(out).is_absolute() else ROOT / out
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)
    return rows


def main(argv: Sequence[str] | None = None) -> None:
    from swing_engine.core.config import load_settings

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settings", default="config/prereg_b9.yaml")
    ap.add_argument("--tr-settings", default="config/prereg_b9_tr.yaml")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args(argv)
    store = ROOT / load_settings.__wrapped__(Path(args.settings)).data.store_path
    tr = ROOT / load_settings.__wrapped__(Path(args.tr_settings)).data.store_path if args.tr_settings else None
    run(store, tr, args.out)


if __name__ == "__main__":
    main()

