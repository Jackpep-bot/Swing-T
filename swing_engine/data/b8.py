"""Batch-8 deal flag (docs/proposals/swing-methods-2026-10/batch8/merger_target_spread_capture_v2.md) from EDGAR: the
`form_events` table of the batch-7 store, 8-K items, and each deal filing's header (no new data source: the
header is the same filing on sec.gov).

Why headers: a filing appears in the submissions list of every company it names, so a bidder's own list carries
its SC TO-T and `form_events` cannot tell the target from the bidder (in 2025 the first SC TO-T rows were
Stryker, QXO, United Rentals, Emerson: bidders). The header's SUBJECT-COMPANY and FILED-BY / FILER blocks can.

`run_header_ingest(store, get_text)` writes table `form_parties` (accession, role, cik) for every DEFM14A and
SC TO-T accession in `form_events`; resumable.

`join_b8(store, panel)` does nothing unless the store has `form_parties`. With it, a symbol has a deal candidate
at session s when either
* (a) an SC TO-T names its CIK as the subject and another CIK as the filer (anchor a = s), or
* (b) its own DEFM14A (its CIK is the filer) follows an original 8-K with Item 1.01 in the 120 sessions before
  s, inclusive (anchor a = the earliest such 8-K's session);
and no earlier candidate of the symbol came within 365 calendar days (by filing date). On the candidate session
and the 20 sessions after it, rows carry `deal_v2_days` (sessions since s) and `deal_v2_anchor` (sessions from a to
s); NaN elsewhere. Sessions are NYSE sessions (published calendar).
"""
from __future__ import annotations

import re
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd
import structlog

from ._common import TZ
from .b7 import TABLE as FORM_TABLE
from .calendar import trading_days
from .filings import EIGHTK_TABLE, ORIGINAL_8K, has_item
from .store import Store

log = structlog.get_logger(__name__)

TABLE = "form_parties"
TENDER_FORMS, PROXY_FORM = ("SC TO-T", "SCHEDULE TO-T"), "DEFM14A"
SUBJECT, FILER = "subject", "filer"
HEADER_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{nodash}/{accession}.hdr.sgml"
AGREEMENT_ITEM = "1.01"  # card: 8-K Item 1.01, material definitive agreement
AGREEMENT_SESSIONS = 120  # card: the 8-K 1.01 in the 120 sessions before the DEFM14A
WINDOW_SESSIONS = 20  # card: the pinned check is re-tried for up to 20 sessions
QUIET_DAYS = 365  # card: one signal per CIK per 365 days
WRITE_EVERY = 100
FEATURE_COLUMNS: list[str] = ["deal_v2_days", "deal_v2_anchor"]
_BLOCK = re.compile(r"<(SUBJECT-COMPANY|FILED-BY|FILER)>(.*?)(?=<(?:SUBJECT-COMPANY|FILED-BY|FILER)>|\Z)", re.S)
_CIK = re.compile(r"<CIK>\s*(\d+)")


def parse_header(text: str) -> list[tuple[str, str]]:
    """(role, 10-digit CIK) pairs of an EDGAR .hdr.sgml: role `subject` for SUBJECT-COMPANY, `filer` otherwise."""
    out: list[tuple[str, str]] = []
    for tag, body in _BLOCK.findall(text or ""):
        m = _CIK.search(body)
        if m:
            out.append((SUBJECT if tag == "SUBJECT-COMPANY" else FILER, m.group(1).zfill(10)))
    return out


def run_header_ingest(store: Store, get_text: Callable[[str], str], *,
                      progress: Callable[[int, int], None] | None = None) -> dict[str, int]:
    """Fetch the header of every DEFM14A / SC TO-T accession in `form_events` not yet in `form_parties`."""
    forms = (PROXY_FORM, *TENDER_FORMS)
    ev = store.read_table(FORM_TABLE, "form IN (SELECT unnest(?))", [list(forms)]).drop_duplicates("accession")
    have = set(store.read_table(TABLE)["accession"]) if store.has_table(TABLE) else set()
    todo = ev.loc[~ev["accession"].isin(have)]
    rows: list[dict[str, str]] = []
    for n, r in enumerate(todo.itertuples(), 1):
        url = HEADER_URL.format(cik=int(r.cik), nodash=r.accession.replace("-", ""), accession=r.accession)
        rows += [{"accession": r.accession, "role": role, "cik": cik} for role, cik in parse_header(get_text(url))]
        if rows and (n % WRITE_EVERY == 0 or n == len(todo)):
            store.write_table(TABLE, pd.DataFrame(rows), ["accession", "role", "cik"])
            rows = []
        if progress is not None:
            progress(n, len(todo))
    return {"accessions": len(todo)}


def candidates(events: pd.DataFrame, parties: pd.DataFrame, eightk: pd.DataFrame, sessions: list[Any]) -> pd.DataFrame:
    """symbol, s (session position), a (anchor position) of the deal candidates (module docstring)."""
    pos = {d: i for i, d in enumerate(sessions)}
    ev = events.assign(session=pd.to_datetime(events["session"]).dt.date, filing_date=pd.to_datetime(events["filing_date"]))
    ev = ev.loc[ev["session"].isin(pos.keys())]
    subj = set(zip(parties.loc[parties["role"] == SUBJECT, "accession"], parties.loc[parties["role"] == SUBJECT, "cik"],
                   strict=True))
    filers = parties.loc[parties["role"] == FILER].groupby("accession")["cik"].agg(set)
    rows: list[dict[str, Any]] = []
    tender = ev.loc[ev["form"].isin(TENDER_FORMS)]
    for r in tender.itertuples():
        if (r.accession, r.cik) in subj and filers.get(r.accession, set()) - {r.cik}:
            rows.append({"symbol": r.symbol, "s": pos[r.session], "a": pos[r.session], "filing_date": r.filing_date})
    agree = eightk.loc[(eightk["form"] == ORIGINAL_8K) & has_item(eightk["items"], AGREEMENT_ITEM)]
    agree = agree.assign(p=pd.to_datetime(agree["session"]).dt.date.map(pos)).dropna(subset=["p"])
    by_sym = {sym: np.sort(g.to_numpy(dtype=int)) for sym, g in agree.groupby("symbol")["p"]}
    for r in ev.loc[ev["form"] == PROXY_FORM].itertuples():
        if r.cik not in filers.get(r.accession, set()):
            continue
        s, ps = pos[r.session], by_sym.get(r.symbol)
        hit = ps[(ps >= s - AGREEMENT_SESSIONS) & (ps <= s)] if ps is not None else np.array([], dtype=int)
        if hit.size:
            rows.append({"symbol": r.symbol, "s": s, "a": int(hit.min()), "filing_date": r.filing_date})
    out = pd.DataFrame(rows, columns=["symbol", "s", "a", "filing_date"]).sort_values(["symbol", "filing_date", "s"])
    keep, last = [], {}
    for r in out.itertuples():
        prev = last.get(r.symbol)
        ok = prev is None or (r.filing_date - prev) > pd.Timedelta(days=QUIET_DAYS)
        keep.append(ok)
        if ok:
            last[r.symbol] = r.filing_date
    return out.loc[keep, ["symbol", "s", "a"]].reset_index(drop=True)


def deal_features(cands: pd.DataFrame, index: pd.DataFrame, sessions: list[Any]) -> pd.DataFrame:
    """FEATURE_COLUMNS per (symbol, ts) row of ``index``."""
    out = index[["symbol", "ts"]].reset_index(drop=True)
    days = np.full(len(out), np.nan)
    anchor = np.full(len(out), np.nan)
    if not cands.empty and not out.empty:
        ts = pd.to_datetime(out["ts"])
        day = (ts.dt.tz_convert(TZ) if ts.dt.tz is not None else ts).dt.date
        p = day.map({d: i for i, d in enumerate(sessions)}).to_numpy(dtype=float)
        sym = out["symbol"].astype(str).to_numpy()
        for c in cands.itertuples():  # ponytail: one pass per candidate (a few hundred); vectorise if that grows
            m = (sym == c.symbol) & (p >= c.s) & (p <= c.s + WINDOW_SESSIONS)
            days[m], anchor[m] = p[m] - c.s, c.s - c.a
    return out.assign(deal_v2_days=days, deal_v2_anchor=anchor)


def join_b8(store: Any, panel: pd.DataFrame) -> pd.DataFrame:
    """``panel`` plus FEATURE_COLUMNS when the store has `form_parties`; unchanged otherwise."""
    has = getattr(store, "has_table", None)
    if panel is None or panel.empty or all(c in panel.columns for c in FEATURE_COLUMNS) or not callable(has) \
            or not has(TABLE):
        return panel
    ts = pd.to_datetime(panel["ts"])
    lo = (ts.min() - timedelta(days=QUIET_DAYS + 200)).date()
    hi = (ts.max() + timedelta(days=7)).date()
    sessions = trading_days(lo, hi)
    events = store.read_table(FORM_TABLE, "form IN (SELECT unnest(?)) AND filing_date >= ?",
                              [[PROXY_FORM, *TENDER_FORMS], lo])
    eightk = store.read_table(EIGHTK_TABLE, "form = ? AND session >= ?", [ORIGINAL_8K, lo])
    cands = candidates(events, store.read_table(TABLE), eightk, sessions)
    feats = deal_features(cands, panel, sessions)
    log.info("b8_join", candidates=len(cands))
    return panel.assign(**{c: feats[c].to_numpy(dtype=np.float64) for c in FEATURE_COLUMNS})


__all__ = ["TABLE", "FEATURE_COLUMNS", "parse_header", "run_header_ingest", "candidates", "deal_features", "join_b8"]
