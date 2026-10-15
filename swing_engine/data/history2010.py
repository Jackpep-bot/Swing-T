"""Stock history 2010-2015 for a research store (docs/plan-store-2010.md): the pieces of the build, each a pure
function or a function of an injected client, so the whole build is testable offline. `scripts/build_store_2010.py`
wires them to EDGAR and Tiingo; it does nothing on the network until TIINGO_API_KEY is in .env.

1. Candidates without prices: EDGAR full-index (`form.idx`, every filer, dead ones included) for 10-K filers, sized by
   the dated cover-page `dei:EntityPublicFloat` in companyfacts; the top TOP_FLOAT in any year 2009-2015.
2. Tickers for CIKs the store lacks (stopped filing before the store's map): the XBRL instance file name of their last
   10-K (`ticker-yyyymmdd.xml`, the EDGAR Filer Manual's prefix), accepted only when Tiingo's supported-tickers file
   has exactly one stock span for it covering the CIK's filing years (a reused ticker goes to the hand-check list).
3. Bars from Tiingo through 2016-06-30. A name already in the store is scaled to the store's split basis on the
   2016-01-04 .. 2016-06-30 overlap (and must agree there); only bars before its first store bar are written. A dead
   name is keyed `TICKER~YYYYMMDD` (its last bar), as the store's delisted names are.
4. Splits and cash dividends from the same Tiingo rows; fundamentals and filing events for dead CIKs from their
   companyfacts (`data.fundamentals.parse_companyfacts` / `fundamental_events`, point-in-time as everywhere else).
"""
from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
import structlog

log = structlog.get_logger(__name__)

FULL_INDEX_URL = "https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/form.idx"
FILING_INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/index.json"
ANNUAL_FORMS = frozenset({"10-K", "10-K/A", "10-K405", "10-KSB"})
FLOAT_YEARS = range(2009, 2016)  # plan: the top TOP_FLOAT by public float in any of these years
TOP_FLOAT = 700
START = date(2010, 1, 4)  # first session wanted
OVERLAP_START, OVERLAP_END = date(2016, 1, 4), date(2016, 6, 30)  # seam check against the store's own bars
SEAM_MIN_DAYS, SEAM_MAX_SPREAD = 20, 0.005  # plan step 6(a): ratios on the overlap within 0.5% of their median
END_BEFORE_FILING_DAYS, END_AFTER_FILING_DAYS = 30, 400  # a dead name's last price vs its last 10-K
_INSTANCE = re.compile(r"^([a-z][a-z.]{0,5})-(\d{8})\.xml$")


# ------------------------------------------------------------------------------------------------ 1. candidates
def parse_form_index(text: str) -> pd.DataFrame:
    """EDGAR `form.idx` rows for the annual forms: form, company, cik (10 digits), filed, path."""
    rows = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0] not in ANNUAL_FORMS or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", parts[-2]):
            continue
        path, filed, cik = parts[-1], parts[-2], parts[-3]
        if not cik.isdigit():
            continue
        head = line[:line.rfind(filed)]
        company = head[len(parts[0]):head.rfind(cik)].strip()
        rows.append({"form": parts[0], "company": company, "cik": cik.zfill(10), "filed": date.fromisoformat(filed),
                     "path": path})
    return pd.DataFrame(rows, columns=["form", "company", "cik", "filed", "path"])


def public_floats(payload: Mapping[str, Any] | None, cik: str) -> pd.DataFrame:
    """Dated `dei:EntityPublicFloat` facts of one companyfacts payload: cik, period_end, filed, value (USD)."""
    cols = ["cik", "period_end", "filed", "value"]
    try:
        facts = payload["facts"]["dei"]["EntityPublicFloat"]["units"]["USD"]  # type: ignore[index]
    except (KeyError, TypeError):
        return pd.DataFrame(columns=cols)
    out = pd.DataFrame([{"cik": str(cik).zfill(10), "period_end": f.get("end"), "filed": f.get("filed"),
                         "value": f.get("val")} for f in facts], columns=cols)
    out["period_end"] = pd.to_datetime(out["period_end"], errors="coerce").dt.date
    out["filed"] = pd.to_datetime(out["filed"], errors="coerce").dt.date
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    return out.dropna(subset=["filed", "value"])


def candidates(floats: pd.DataFrame, top: int = TOP_FLOAT, years: Iterable[int] = FLOAT_YEARS) -> pd.DataFrame:
    """CIKs in the top ``top`` by public float in any year (the latest float filed that calendar year), with their
    best rank: cik, best_rank, best_year."""
    f = floats.assign(year=pd.to_datetime(floats["filed"]).dt.year)
    f = f.loc[f["year"].isin(list(years)) & (f["value"] > 0)].sort_values("filed", kind="mergesort")
    latest = f.drop_duplicates(["cik", "year"], keep="last")
    latest = latest.assign(rank=latest.groupby("year")["value"].rank(ascending=False, method="first"))
    top_rows = latest.loc[latest["rank"] <= top].sort_values("rank", kind="mergesort")
    best = top_rows.drop_duplicates("cik", keep="first")
    return pd.DataFrame({"cik": best["cik"].to_numpy(), "best_rank": best["rank"].astype(int).to_numpy(),
                         "best_year": best["year"].to_numpy()}).reset_index(drop=True)


# ------------------------------------------------------------------------------------------------ 2. tickers
def instance_ticker(file_names: Iterable[str]) -> str | None:
    """The ticker prefix of a filing's XBRL instance document (`aapl-20120929.xml` -> AAPL), or None."""
    hits = {m.group(1).upper() for n in file_names if (m := _INSTANCE.match(str(n).lower()))}
    return hits.pop() if len(hits) == 1 else None


def match_ticker(guess: str | None, first_filed: date, last_filed: date, spans: pd.DataFrame) -> tuple[str | None, str]:
    """(ticker, why) for a CIK the store lacks: one Tiingo stock span for ``guess`` that starts by its first annual
    filing and ends between END_BEFORE_FILING_DAYS before and END_AFTER_FILING_DAYS after its last one."""
    if not guess:
        return None, "no ticker in the instance file name"
    rows = spans.loc[(spans["ticker"] == guess) & (spans["assetType"] == "Stock")]
    if len(rows) != 1:
        return None, f"{len(rows)} Tiingo stock spans for {guess} (reused or unknown ticker: hand check)"
    r = rows.iloc[0]
    if pd.isna(r["startDate"]) or pd.isna(r["endDate"]):
        return None, f"{guess}: Tiingo span without dates"
    if r["startDate"] > first_filed:
        return None, f"{guess}: Tiingo prices start {r['startDate']}, after the first 10-K {first_filed}"
    lo, hi = last_filed - timedelta(days=END_BEFORE_FILING_DAYS), last_filed + timedelta(days=END_AFTER_FILING_DAYS)
    if not lo <= r["endDate"] <= hi:
        return None, f"{guess}: Tiingo prices end {r['endDate']}, not near the last 10-K {last_filed}"
    return guess, "matched"


# ------------------------------------------------------------------------------------------------ 3. bars
def _days(ts: pd.Series) -> pd.Series:
    """Session dates of a ts column: dates, naive timestamps, Tiingo's UTC midnights or the store's New York ones."""
    t = pd.to_datetime(ts)
    if t.dt.tz is not None:
        t = t.dt.tz_localize(None) if str(t.dt.tz) == "UTC" else t.dt.tz_convert("America/New_York")
    return t.dt.date


def seam_scale(tiingo_bars: pd.DataFrame, store_bars: pd.DataFrame) -> tuple[float, float, int]:
    """(scale, spread, days) on the overlap: scale = median of store close / Tiingo close (the later splits Tiingo's
    window does not see); spread = the largest relative deviation of a day's ratio from it."""
    a = pd.Series(tiingo_bars["close"].to_numpy(), index=_days(tiingo_bars["ts"]))
    b = pd.Series(store_bars["close"].to_numpy(), index=_days(store_bars["ts"]))
    ratio = (b / a.reindex(b.index)).replace([np.inf, -np.inf], np.nan).dropna()
    if ratio.empty:
        return float("nan"), float("nan"), 0
    scale = float(ratio.median())
    return scale, float((ratio / scale - 1.0).abs().max()), int(len(ratio))


def scaled(bars: pd.DataFrame, scale: float) -> pd.DataFrame:
    out = bars.copy()
    for c in ("open", "high", "low", "close"):
        out[c] = out[c] * scale
    out["volume"] = out["volume"] / scale
    return out


def corporate_actions(raw: pd.DataFrame, symbol: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(splits, dividends) rows in the store's schemas from Tiingo's ``splitFactor`` and ``divCash``."""
    from swing_engine.data.dividends import SCHEMA as DIV_SCHEMA

    split_cols = ["symbol", "ex_date", "split_from", "split_to", "ratio"]
    if raw.empty:
        return pd.DataFrame(columns=split_cols), pd.DataFrame(columns=list(DIV_SCHEMA))
    day = _days(raw["date"])
    f = pd.to_numeric(raw.get("splitFactor", 1.0), errors="coerce").fillna(1.0)
    s = f != 1.0
    splits = pd.DataFrame({"symbol": symbol, "ex_date": day[s].to_numpy(), "split_from": 1, "split_to": f[s].to_numpy(),
                           "ratio": f[s].to_numpy()}, columns=split_cols)
    cash = pd.to_numeric(raw.get("divCash", 0.0), errors="coerce").fillna(0.0)
    d = cash > 0
    div = pd.DataFrame({"id": [f"tiingo:{symbol}:{x}" for x in day[d]], "symbol": symbol, "ex_date": day[d].to_numpy(),
                        "rate": cash[d].to_numpy(), "special": False, "foreign": False, "process_date": None,
                        "payable_date": None, "record_date": None}, columns=list(DIV_SCHEMA))
    return splits, div


# ------------------------------------------------------------------------------------------------ 4. the build
@dataclass
class Name:
    """One security to extend: ``symbol`` is the store key to write under (a live ticker, or None for a dead one,
    keyed from its last bar); ``ticker`` is what Tiingo knows it by."""
    cik: str
    ticker: str
    symbol: str | None = None


@dataclass
class Report:
    written: dict[str, int] = field(default_factory=dict)  # store key -> bars written
    rejected: dict[str, str] = field(default_factory=dict)  # ticker -> why
    seams: dict[str, tuple[float, float, int]] = field(default_factory=dict)


def extend(store: Any, rows_for: Callable[[str, date, date], pd.DataFrame], names: Iterable[Name],
           facts_for: Callable[[str], Mapping[str, Any] | None] | None = None, start: date = START,
           overlap_end: date = OVERLAP_END) -> Report:
    """Write 2010 .. first-store-bar history for ``names`` into ``store`` (a research copy). ``rows_for(ticker,
    start, end)``: Tiingo's raw rows (TiingoProvider.daily_rows); ``facts_for(cik)``: companyfacts for dead names."""
    from swing_engine.data.delisted import LISTINGS_SCHEMA, LISTINGS_TABLE, entity_key
    from swing_engine.data.dividends import SCHEMA as DIV_SCHEMA
    from swing_engine.data.dividends import TABLE as DIV_TABLE
    from swing_engine.data.fundamentals import (
        EVENTS_KEYS,
        EVENTS_TABLE,
        FUNDAMENTALS_KEYS,
        FUNDAMENTALS_SCHEMA,
        FUNDAMENTALS_TABLE,
        fundamental_events,
        parse_companyfacts,
    )
    from swing_engine.data.tiingo import split_adjust

    rep = Report()
    for n in names:
        raw = rows_for(n.ticker, start, overlap_end)
        if raw.empty:
            rep.rejected[n.ticker] = "no Tiingo rows"
            continue
        bars = split_adjust(raw, n.ticker)
        if n.symbol is not None:  # already in the store from 2016: scale to its basis, keep only earlier bars
            have = store.read_bars([n.symbol], OVERLAP_START, overlap_end)
            if have.empty:
                rep.rejected[n.ticker] = f"{n.symbol} has no store bars on the overlap"
                continue
            scale, spread, days = seam_scale(bars.loc[_days(bars["ts"]) >= OVERLAP_START], have)
            rep.seams[n.symbol] = (scale, spread, days)
            if days < SEAM_MIN_DAYS or not spread <= SEAM_MAX_SPREAD:
                rep.rejected[n.ticker] = f"seam check failed: {days} days, spread {spread:.2%}"
                continue
            first = _days(store.sql("select min(ts) as ts from bars where symbol = ?", [n.symbol])["ts"]).iloc[0]
            bars = scaled(bars, scale)
            key = n.symbol
        else:
            first = None
            key = entity_key(n.ticker, _days(bars["ts"]).max())
        cut = first or overlap_end + timedelta(days=1)
        keep = bars.loc[_days(bars["ts"]) < cut]
        keep = keep.assign(symbol=key)
        if keep.empty:
            rep.rejected[n.ticker] = "nothing before the store's first bar"
            continue
        rep.written[key] = store.write_bars(keep)
        raw_before = raw.loc[_days(raw["date"]) < cut]
        splits, div = corporate_actions(raw_before, key)
        if len(splits):
            store.write_table("splits", splits, ["symbol", "ex_date"])
        if len(div):
            store.write_table(DIV_TABLE, div, ["id"], schema=DIV_SCHEMA)
        if n.symbol is None:
            days = _days(keep["ts"])
            listing = pd.DataFrame([{"key": key, "ticker": n.ticker, "cik": n.cik, "first_bar": days.min(),
                                     "last_bar": days.max(), "source": "tiingo-2010"}]).reindex(columns=list(LISTINGS_SCHEMA))
            store.write_table(LISTINGS_TABLE, listing, ["key"], schema=LISTINGS_SCHEMA)
            store.write_table("symbols", pd.DataFrame([{"symbol": key, "type": "CS", "active": False, "cik": n.cik,
                                                        "listed_at": days.min(), "delisted_at": days.max()}]), ["symbol"])
            if facts_for is not None:
                fund = parse_companyfacts(facts_for(n.cik), [key], n.cik)
                if len(fund):
                    store.write_table(FUNDAMENTALS_TABLE, fund, FUNDAMENTALS_KEYS, schema=FUNDAMENTALS_SCHEMA)
                    store.write_table(EVENTS_TABLE, fundamental_events(fund), EVENTS_KEYS)
    return rep


__all__ = ["Name", "Report", "candidates", "corporate_actions", "extend", "instance_ticker", "match_ticker",
           "parse_form_index", "public_floats", "seam_scale"]
