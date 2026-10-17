"""Batch-7 event columns (docs/proposals/swing-methods-2026-10/batch7/) from EDGAR form types in the submissions JSON
(the same pages data.filings reads for 8-K items). No new data source.

`run_form_ingest(store, edgar)` writes table `form_events`: one row per (symbol, accession) for the forms in FORMS,
with `session` = the first session whose close can react (data.edgar.parse_filings: the session after an
after-hours acceptance). Resumable through `form_ingest_meta`.

`join_b7(store, panel)` does nothing unless the store has `form_events` (only the batch-7 research store does). With
it, on the row of a symbol's reaction session:
* `deal_event` = 1: a DEFM14A, or a third-party tender offer (SC TO-T) naming the company, with no such filing in
  the 365 calendar days before it (card merger_target_spread_capture);
* `offer_event` = 1: a 424B4 or 424B5 prospectus with no 424B of any kind in the 90 calendar days before it (card
  seo_marketed_offer_rebound; repeat supplements of at-the-market programs drop out);
0 on every other row. Known limit, registered with the cards: a DEFM14A is also filed by an acquirer whose own
holders vote on a large stock deal, and the form type cannot tell the two apart.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
import structlog

from ._common import TZ
from .edgar import EIGHTK_COLUMNS, parse_filings
from .store import Store

log = structlog.get_logger(__name__)

TABLE, META_TABLE = "form_events", "form_ingest_meta"
CIK_META_TABLE = "eightk_ingest_meta"  # (cik, symbols): the CIKs the 8-K ingest already resolved
DEAL_FORMS = frozenset({"DEFM14A", "SC TO-T", "SCHEDULE TO-T"})  # EDGAR renamed some SC forms in 2024
OFFER_FORMS = frozenset({"424B4", "424B5"})
ANY_424B = frozenset({"424B1", "424B2", "424B3", "424B4", "424B5", "424B7", "424B8"})
FORMS = DEAL_FORMS | ANY_424B
DEAL_QUIET_DAYS, OFFER_QUIET_DAYS = 365, 90  # cards: first such filing in 365 days; no 424B in the prior 90
SINCE = date(2015, 1, 1)  # older submissions pages are skipped: the store's bars start in 2016
WRITE_EVERY = 200  # CIKs per write, so an interrupted ingest keeps what it fetched
FEATURE_COLUMNS: list[str] = ["deal_event", "offer_event"]


def run_form_ingest(store: Store, edgar: Any, *, limit: int | None = None,
                    progress: Callable[[int, int], None] | None = None) -> dict[str, int]:
    """Fetch every submissions page of each CIK in `eightk_ingest_meta` not yet in `form_ingest_meta` and write the
    FORMS rows. Resumable: rerun to continue."""
    meta = store.read_table(CIK_META_TABLE)
    have = set(store.read_table(META_TABLE)["cik"]) if store.has_table(META_TABLE) else set()
    todo = meta.loc[~meta["cik"].isin(have)]
    todo = todo if limit is None else todo.head(limit)
    rows: list[pd.DataFrame] = []
    done: list[dict[str, Any]] = []
    n_rows = 0
    for n, r in enumerate(todo.itertuples(), 1):
        syms = [s.strip().upper() for s in str(r.symbols).split(",") if s.strip()]
        frames = [parse_filings(p, syms, r.cik, FORMS, EIGHTK_COLUMNS) for p in edgar.submissions(r.cik, since=SINCE)]
        rows += [f for f in frames if not f.empty]
        done.append({"cik": r.cik, "fetched_on": date.today(), "rows": int(sum(len(f) for f in frames))})
        if n % WRITE_EVERY == 0 or n == len(todo):
            if rows:
                batch = pd.concat(rows, ignore_index=True).drop_duplicates(["symbol", "accession"])
                store.write_table(TABLE, batch, ["symbol", "accession"])
                n_rows += len(batch)
            store.write_table(META_TABLE, pd.DataFrame(done), ["cik"])
            rows, done = [], []
        if progress is not None:
            progress(n, len(todo))
    log.info("form_ingest", ciks=len(todo), rows=n_rows)
    return {"ciks": len(todo), "rows": n_rows}


def _first_in(events: pd.DataFrame, forms: frozenset[str], quiet_forms: frozenset[str], quiet_days: int) -> pd.DataFrame:
    """(symbol, session) of the `forms` filings with no `quiet_forms` filing of the same symbol in the `quiet_days`
    calendar days before them (by filing date)."""
    ev = events.loc[events["form"].isin(quiet_forms)].sort_values(["symbol", "filing_date"], kind="mergesort")
    prev = ev.groupby("symbol")["filing_date"].shift(1)
    fresh = prev.isna() | ((ev["filing_date"] - prev) > pd.Timedelta(days=quiet_days))
    hit = ev.loc[fresh & ev["form"].isin(forms)]
    return hit[["symbol", "session"]].drop_duplicates()


def event_features(events: pd.DataFrame, index: pd.DataFrame) -> pd.DataFrame:
    """FEATURE_COLUMNS per (symbol, ts) row of ``index`` from `form_events` rows."""
    out = index[["symbol", "ts"]].reset_index(drop=True)
    if events is None or events.empty or out.empty:
        return out.assign(**dict.fromkeys(FEATURE_COLUMNS, 0.0))
    ev = events.assign(filing_date=pd.to_datetime(events["filing_date"]), session=pd.to_datetime(events["session"]).dt.date)
    ts = pd.to_datetime(out["ts"])
    day = (ts.dt.tz_convert(TZ) if ts.dt.tz is not None else ts).dt.date
    key = pd.MultiIndex.from_arrays([out["symbol"].astype(str), day])
    for col, forms, quiet, days in (("deal_event", DEAL_FORMS, DEAL_FORMS, DEAL_QUIET_DAYS),
                                    ("offer_event", OFFER_FORMS, ANY_424B, OFFER_QUIET_DAYS)):
        hits = _first_in(ev, forms, quiet, days)
        out[col] = key.isin(pd.MultiIndex.from_frame(hits)).astype(float) if not hits.empty else 0.0
    return out


def join_b7(store: Any, panel: pd.DataFrame) -> pd.DataFrame:
    """``panel`` plus FEATURE_COLUMNS when the store has `form_events`. Unchanged otherwise, or when the panel
    already carries the columns."""
    has = getattr(store, "has_table", None)
    if panel is None or panel.empty or all(c in panel.columns for c in FEATURE_COLUMNS) or not callable(has) \
            or not has(TABLE):
        return panel
    ts = pd.to_datetime(panel["ts"])
    first = (ts.min() - timedelta(days=DEAL_QUIET_DAYS + 7)).date()
    events = store.read_table(TABLE, "filing_date >= ?", [first])
    feats = event_features(events, panel)
    log.info("b7_join", deals=int(feats["deal_event"].sum()), offers=int(feats["offer_event"].sum()))
    return panel.assign(**{c: feats[c].to_numpy(dtype=np.float64) for c in FEATURE_COLUMNS})


__all__ = ["TABLE", "FORMS", "FEATURE_COLUMNS", "run_form_ingest", "event_features", "join_b7"]
