"""Premise evidence from long free factor histories (owner approved 2026-10-14 19:20 UTC: AQR datasets and the
Chen-Zimmermann dataset). Not trials and not pass routes: like batch 14's Ken French check, these say whether an idea
has worked over decades and whether it still worked after 2017, before a card spends a trial on it.

* AQR (data/research/aqr/*.xlsx; decimals; history restated by AQR at each update, so not point-in-time vintages):
  QMJ, BAB, US value and momentum (VME), TSMOM. Each: mean, CAPM alpha on AQR's US market excess return, OLS and
  Newey-West t, by subperiod.
* Chen-Zimmermann v2 (data/research/chen_zimmermann/; percent; long-short returns of 212 published predictors, mostly
  equal-weighted, so small caps dominate): each predictor's mean in its paper's sample, after publication, and from
  2017; the ones still working since 2017 with data our store has (accounting, price, trading).

    uv run python -m swing_engine.research.premise_library
"""
from __future__ import annotations

import math
import re
import zipfile
from collections.abc import Sequence
from pathlib import Path
from xml.etree import ElementTree

import numpy as np
import pandas as pd

from swing_engine.core.config import ROOT
from swing_engine.research.b14_books import capm

AQR_DIR, CZ_DIR = ROOT / "data" / "research" / "aqr", ROOT / "data" / "research" / "chen_zimmermann"
OUT = "docs/premise_library.md"
SUBPERIODS = (("1926-01", "1962-12"), ("1963-01", "1989-12"), ("1990-01", "2016-12"), ("2017-01", "2100-12"))
RECENT = "2017-01"
STORE_DATA = ("Accounting", "Price", "Trading")  # Cat.Data our store can build (EDGAR facts, daily bars)
TOP_N = 25
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
# AQR series: (file, sheet, column, label)
AQR_SERIES = (("Quality-Minus-Junk-Factors-Monthly.xlsx", "QMJ Factors", "USA", "QMJ, US"),
              ("Betting-Against-Beta-Equity-Factors-Monthly.xlsx", "BAB Factors", "USA", "BAB, US"),
              ("Value-and-Momentum-Everywhere-Factors-Monthly.xlsx", "VME Factors", "MOMLS_VME_US90", "momentum, US (VME)"),
              ("Value-and-Momentum-Everywhere-Factors-Monthly.xlsx", "VME Factors", "VALLS_VME_US90", "value, US (VME)"),
              ("Time-Series-Momentum-Factors-Monthly.xlsx", "TSMOM Factors", "TSMOM", "TSMOM, all futures"),
              ("Quality-Minus-Junk-Factors-Monthly.xlsx", "UMD", "USA", "UMD momentum, US"),
              ("Quality-Minus-Junk-Factors-Monthly.xlsx", "HML Devil", "USA", "HML Devil value, US"),
              ("Quality-Minus-Junk-Factors-Monthly.xlsx", "SMB", "USA", "SMB size, US"))


# ------------------------------------------------------------------------------------------------ readers
def xlsx_rows(path: Path, sheet: str) -> list[list[str]]:
    """One sheet's cells as text rows (stdlib only: openpyxl is not a dependency)."""
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ElementTree.fromstring(z.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.iter(f"{{{_NS['m']}}}t")) for si in root.findall("m:si", _NS)]
        book = ElementTree.fromstring(z.read("xl/workbook.xml"))
        rid = next(s.get(_REL) for s in book.iter(f"{{{_NS['m']}}}sheet") if s.get("name") == sheet)
        rels = ElementTree.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = next(r.get("Target") for r in rels if r.get("Id") == rid).lstrip("/")
        data = ElementTree.fromstring(z.read(target if target.startswith("xl/") else f"xl/{target}"))
    rows = []
    for row in data.iter(f"{{{_NS['m']}}}row"):
        cells: dict[int, str] = {}
        for c in row.findall("m:c", _NS):
            col = re.match(r"[A-Z]+", c.get("r", "A")).group(0)
            k = 0
            for ch in col:
                k = k * 26 + ord(ch) - 64
            v = c.find("m:v", _NS)
            text = (v.text or "") if v is not None else "".join(t.text or "" for t in c.iter(f"{{{_NS['m']}}}t"))
            cells[k - 1] = shared[int(text)] if c.get("t") == "s" and text else text
        rows.append([cells.get(i, "") for i in range(max(cells) + 1)] if cells else [])
    return rows


def _month(text: str) -> str | None:
    """yyyy-mm from 'MM/DD/YYYY' or an Excel serial day."""
    text = text.strip()
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}"
    try:
        serial = float(text)
    except ValueError:
        return None
    return (pd.Timestamp("1899-12-30") + pd.Timedelta(days=serial)).strftime("%Y-%m") if serial > 1000 else None


def aqr_sheet(path: Path, sheet: str) -> pd.DataFrame:
    """A factor sheet as a month-indexed frame of decimals (header = the first row whose later cells name columns
    and whose next row starts with a date; blank-date rows dropped)."""
    rows = xlsx_rows(path, sheet)
    head = next(i for i, r in enumerate(rows[:-1]) if len(r) > 1 and r[1].strip() and rows[i + 1] and _month(rows[i + 1][0]))
    cols = [c.strip() for c in rows[head]]
    out = {}
    for r in rows[head + 1:]:
        month = _month(r[0]) if r else None
        if month:
            out[month] = [float(x) if x.strip() not in ("", "NA") else np.nan for x in (r + [""] * len(cols))[1:len(cols)]]
    return pd.DataFrame.from_dict(out, orient="index", columns=cols[1:]).sort_index()


def cz_returns(path: Path) -> pd.DataFrame:
    """PredictorLSretWide: month-indexed decimals (the file is in percent)."""
    df = pd.read_csv(path, na_values=["NA"])
    df.index = pd.to_datetime(df.pop("date")).dt.strftime("%Y-%m")
    return df / 100.0


# ------------------------------------------------------------------------------------------------ stats
def mean_t(r: pd.Series) -> tuple[float, float, int]:
    """(mean per year, t of the monthly mean, months)."""
    r = r.dropna()
    if len(r) < 12:
        return math.nan, math.nan, len(r)
    return float(r.mean() * 12), float(r.mean() / (r.std(ddof=1) / math.sqrt(len(r)))), len(r)


def aqr_lines(directory: Path = AQR_DIR) -> list[str]:
    mkt = aqr_sheet(directory / AQR_SERIES[0][0], "MKT")["USA"]
    lines = ["## AQR factors (long-short, US unless named)", "",
             "CAPM alpha on AQR's US market excess return; Newey-West 6 lags beside OLS. Restated history (AQR rebuilds "
             "the full series each update), so these are not point-in-time vintages.", "",
             "| factor | window | months | mean/yr | t (mean) | CAPM alpha/yr | t (OLS) | t (NW) | beta |", "|" + "---|" * 9]
    for file, sheet, col, label in AQR_SERIES:
        s = aqr_sheet(directory / file, sheet)[col].dropna()
        windows = [(s.index[0], s.index[-1], "full")] + [(lo, hi, f"{lo} ..") for lo, hi in SUBPERIODS
                                                          if s.index[-1] >= lo and s.index[0] <= hi]
        for lo, hi, name in windows:
            part = s.loc[lo:hi]
            if len(part) < 24:
                continue
            m, t, n = mean_t(part)
            c = capm(part, mkt) if mkt.reindex(part.index).notna().sum() >= 24 else {}
            lines.append(f"| {label} | {name if name != 'full' else f'{part.index[0]} .. {part.index[-1]}'} | {n} | "
                         f"{m:+.2%} | {t:.2f} | {c.get('alpha_ann', math.nan):+.2%} | {c.get('t_ols', math.nan):.2f} | "
                         f"{c.get('t_nw', math.nan):.2f} | {c.get('beta', math.nan):.2f} |")
    return lines + [""]


def cz_table(ret: pd.DataFrame, doc: pd.DataFrame) -> pd.DataFrame:
    """Per predictor: in-sample, post-publication and since-2017 mean and t (signed so the paper's side is +)."""
    doc = doc.loc[doc["Cat.Signal"] == "Predictor"].set_index("Acronym")
    rows = []
    for name in ret.columns.intersection(doc.index):
        r, d = ret[name], doc.loc[name]
        ins = r.loc[f"{int(d['SampleStartYear'])}-01":f"{int(d['SampleEndYear'])}-12"]
        post = r.loc[f"{int(d['Year']) + 1}-01":]
        recent = r.loc[RECENT:]
        (mi, ti, _), (mp, tp, _), (mr, tr, nr) = mean_t(ins), mean_t(post), mean_t(recent)
        rows.append({"predictor": name, "data": d["Cat.Data"], "weight": d["Stock Weight"], "published": int(d["Year"]),
                     "in_sample": mi, "t_in": ti, "post_pub": mp, "t_post": tp, "since_2017": mr, "t_2017": tr,
                     "months_2017": nr, "last": r.dropna().index[-1] if r.notna().any() else "-",
                     "description": str(d.get("LongDescription", ""))[:70]})
    return pd.DataFrame(rows).set_index("predictor")


def cz_lines(directory: Path = CZ_DIR) -> list[str]:
    tab = cz_table(cz_returns(directory / "PredictorLSretWide.csv"), pd.read_csv(directory / "SignalDoc.csv"))
    ok = tab.dropna(subset=["in_sample", "post_pub", "since_2017"])
    decay = ok["post_pub"] / ok["in_sample"]
    big = ok.loc[ok["since_2017"].abs() > 0.5]  # > 50% a year: the dataset's known outliers (e.g. IO_ShortInterest)
    lines = ["## Chen-Zimmermann predictors (v2.0.0, long-short, mostly equal-weighted, data to 2024-12)", "",
             f"{len(tab)} predictors with returns; {len(ok)} with all three spans. Median mean a year: in the paper's "
             f"sample {ok['in_sample'].median():+.2%}, after publication {ok['post_pub'].median():+.2%}, since 2017 "
             f"{ok['since_2017'].median():+.2%}. Median post-publication / in-sample ratio {decay.median():.2f}. "
             f"Positive since 2017: {(ok['since_2017'] > 0).mean():.0%}; t >= 2 since 2017: "
             f"{(ok['t_2017'] >= 2).sum()} of {len(ok)} (luck alone gives about {0.023 * len(ok):.0f}).",
             f"Since-2017 means above 50% a year, outliers to check before use: "
             f"{', '.join(big.index) if len(big) else 'none'}.", "",
             "By data source (median mean a year since 2017, share positive):", "", "| data | predictors | since 2017 | "
             "share positive | t >= 2 |", "|---|---|---|---|---|"]
    for data, g in ok.groupby("data"):
        lines.append(f"| {data} | {len(g)} | {g['since_2017'].median():+.2%} | {(g['since_2017'] > 0).mean():.0%} | "
                     f"{(g['t_2017'] >= 2).sum()} |")
    usable = ok.loc[ok["data"].isin(STORE_DATA)].sort_values("t_2017", ascending=False)
    lines += ["", f"Top {TOP_N} since 2017 among predictors our store can build ({', '.join(STORE_DATA)}), by t "
              "(these are candidates for cards, not results; the 2017 split was chosen before looking):", "",
              "| predictor | data | EW/VW | published | in sample/yr (t) | after pub/yr (t) | since 2017/yr (t) | what |",
              "|" + "---|" * 8]
    for name, r in usable.head(TOP_N).iterrows():
        lines.append(f"| {name} | {r['data']} | {r['weight']} | {r['published']} | {r['in_sample']:+.1%} ({r['t_in']:.1f}) | "
                     f"{r['post_pub']:+.1%} ({r['t_post']:.1f}) | {r['since_2017']:+.1%} ({r['t_2017']:.1f}) | "
                     f"{r['description']} |")
    vw = ok.loc[ok["weight"] == "VW"].sort_values("t_2017", ascending=False)
    lines += ["", f"Value-weighted predictors (closest to a large-cap book), {len(vw)}, by t since 2017:", "",
              "| predictor | data | since 2017/yr (t) | after pub/yr (t) |", "|---|---|---|---|",
              *[f"| {n} | {r['data']} | {r['since_2017']:+.1%} ({r['t_2017']:.1f}) | {r['post_pub']:+.1%} ({r['t_post']:.1f}) |"
                for n, r in vw.iterrows()]]
    return lines + [""]


def main(argv: Sequence[str] | None = None) -> None:
    lines = ["# Premise library: long factor histories", "",
             "Generated by `swing_engine.research.premise_library` from the owner-approved AQR and Chen-Zimmermann "
             "downloads (2026-10-14). Evidence on ideas, not trials and not pass routes; nothing here grades a card.", "",
             *aqr_lines(), *cz_lines()]
    (ROOT / OUT).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
