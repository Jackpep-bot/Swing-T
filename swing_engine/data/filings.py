"""Every 8-K item list and Schedule 13D filings from EDGAR submissions (owner-approved data builds 2 and 3,
2026-10-09), written by `data.fundamentals.run_edgar_ingest` from the same submissions fetch as the earnings dates.

Tables:
* `eightk_items` (symbol, cik, accession, form, filing_date, acceptance, session, items): every 8-K and 8-K/A.
* `sched13d` (symbol, cik, filer, accession, form, filing_date, acceptance, session): SC 13D / 13D/A (and the
  post-Dec-2024 "SCHEDULE 13D" spelling) listed under the SUBJECT company's CIK. `filer` is the accession prefix,
  i.e. the filer's or its filing agent's CIK (the submissions JSON names no filer).

Point-in-time: `session` is the first session whose close can react to the filing (acceptance time decoded from
UTC, after-close filings roll to the next session, floored at EDGAR's filingDate; no acceptance time -> the session
after the filing date). Never a period or event date.

Panel features (`join_filings`, called from `data.fundamentals.join_edgar`; only original 8-K / 13D count, since an
amendment is not a new event):
* `days_since_8k`: sessions since the latest 8-K reaction session (0 on it), NaN before the first one.
* `days_since_402`: same for 8-Ks carrying Item 4.02 (non-reliance on prior financials, i.e. a restatement).
* `news_8k_flag_1d`: 1.0 when an 8-K's reaction session is this session (the fallback no-news flag), else 0.0.
* `days_since_13d`: sessions since the latest original Schedule 13D reaction session.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import structlog

from .edgar import EIGHTK_COLUMNS, SCHED13D_COLUMNS
from .fundamentals import earnings_calendar_features
from .store import Store

log = structlog.get_logger(__name__)

EIGHTK_TABLE = "eightk_items"
SCHED13D_TABLE = "sched13d"
KEYS: list[str] = ["symbol", "accession"]
EIGHTK_SCHEMA: dict[str, str] = {
    "symbol": "VARCHAR", "cik": "VARCHAR", "accession": "VARCHAR", "form": "VARCHAR", "filing_date": "DATE",
    "acceptance": "TIMESTAMPTZ", "session": "DATE", "items": "VARCHAR",
}
SCHED13D_SCHEMA: dict[str, str] = {
    "symbol": "VARCHAR", "cik": "VARCHAR", "filer": "VARCHAR", "accession": "VARCHAR", "form": "VARCHAR",
    "filing_date": "DATE", "acceptance": "TIMESTAMPTZ", "session": "DATE",
}
assert list(EIGHTK_SCHEMA) == EIGHTK_COLUMNS and list(SCHED13D_SCHEMA) == SCHED13D_COLUMNS

ORIGINAL_8K = "8-K"
ORIGINAL_13D: frozenset[str] = frozenset({"SC 13D", "SCHEDULE 13D"})
ITEM_NON_RELIANCE = "4.02"  # 8-K Item 4.02 "Non-Reliance on Previously Issued Financial Statements"
EIGHTK_FEATURES: list[str] = ["days_since_8k", "days_since_402", "news_8k_flag_1d"]
SCHED13D_FEATURES: list[str] = ["days_since_13d"]
FEATURE_COLUMNS: list[str] = [*EIGHTK_FEATURES, *SCHED13D_FEATURES]


def _days_since(events: pd.DataFrame, index: pd.DataFrame) -> np.ndarray:
    """Sessions since each (symbol, ts) row's latest event session (0 on it); the earnings-calendar clock."""
    return earnings_calendar_features(events[["symbol", "session"]], index)["days_since_earnings"].to_numpy()


def has_item(items: pd.Series, item: str) -> pd.Series:
    return items.fillna("").map(lambda s: item in {t.strip() for t in str(s).split(",")})


def eightk_features(eightk: pd.DataFrame, index: pd.DataFrame) -> pd.DataFrame:
    """EIGHTK_FEATURES per (symbol, ts) row of `index` from `eightk_items` rows."""
    out = index[["symbol", "ts"]].reset_index(drop=True).copy()
    ev = eightk[eightk["form"] == ORIGINAL_8K] if eightk is not None and not eightk.empty else None
    if out.empty or ev is None or ev.empty:
        return out.assign(days_since_8k=np.nan, days_since_402=np.nan, news_8k_flag_1d=0.0)
    out["days_since_8k"] = _days_since(ev, out)
    out["days_since_402"] = _days_since(ev[has_item(ev["items"], ITEM_NON_RELIANCE)], out)
    out["news_8k_flag_1d"] = (out["days_since_8k"] == 0).astype("float64")
    return out


def sched13d_features(sched: pd.DataFrame, index: pd.DataFrame) -> pd.DataFrame:
    """SCHED13D_FEATURES per (symbol, ts) row of `index` from `sched13d` rows (original 13D only)."""
    out = index[["symbol", "ts"]].reset_index(drop=True).copy()
    ev = sched[sched["form"].isin(ORIGINAL_13D)] if sched is not None and not sched.empty else None
    out["days_since_13d"] = np.nan if ev is None or ev.empty or out.empty else _days_since(ev, out)
    return out


def _read(store: Store, table: str, syms: list[str]) -> pd.DataFrame:
    df = store.read_table(table, "symbol IN (SELECT unnest(?))", [syms])
    if not df.empty:
        df["session"] = pd.to_datetime(df["session"]).dt.date
    return df


def join_filings(store: Store, panel: pd.DataFrame) -> pd.DataFrame:
    """``panel`` plus the 8-K columns (when `eightk_items` exists) and `days_since_13d` (when `sched13d` exists).
    Unchanged when neither table is present or the panel already carries the columns."""
    if panel is None or panel.empty:
        return panel
    has = getattr(store, "has_table", None)
    if not callable(has):
        return panel
    syms = sorted(set(panel["symbol"].astype(str)))
    for table, cols, fn in ((EIGHTK_TABLE, EIGHTK_FEATURES, eightk_features),
                            (SCHED13D_TABLE, SCHED13D_FEATURES, sched13d_features)):
        missing = [c for c in cols if c not in panel.columns]
        if not missing or not has(table):
            continue
        feats = fn(_read(store, table, syms), panel)
        log.info("filings_join", table=table, symbols=len(syms), columns=missing)
        panel = panel.assign(**{c: feats[c].to_numpy() for c in missing})
    return panel


__all__ = [
    "EIGHTK_TABLE", "SCHED13D_TABLE", "FEATURE_COLUMNS", "EIGHTK_FEATURES", "SCHED13D_FEATURES", "eightk_features",
    "sched13d_features", "join_filings", "has_item",
]
