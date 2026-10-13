"""SIC industry codes from the EDGAR submissions JSON (field `sic`), for the batch-6 industry cards
(docs/proposals/swing-methods-2026-10/batch6/: `within_industry_reversal_no_news`, `industry_leader_lag_smallmid`).

Table `sic`: one row per symbol (symbol, cik, sic). `join_sic(store, panel)` adds `sic2`, the two-digit SIC as a
float (NaN when unknown), the same value on every row of a symbol.

Known point-in-time gap, registered with the cards: EDGAR serves only a filer's CURRENT code, so a company that
changed industry carries today's code through its whole history. Changes are rare; nothing here can date them.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd
import structlog

from .store import Store

log = structlog.get_logger(__name__)

TABLE = "sic"
COLUMNS: list[str] = ["symbol", "cik", "sic"]
SIC2 = "sic2"
CIK_META_TABLE = "eightk_ingest_meta"  # (cik, symbols): the CIKs the 8-K ingest already resolved
SIC_DIGITS = 4
WRITE_EVERY = 500  # CIKs per write, so an interrupted ingest keeps what it fetched


def parse_sic(payload: dict[str, Any] | None) -> str | None:
    """The four-digit `sic` of one submissions document, zero-padded; None when absent or not a number."""
    raw = str((payload or {}).get("sic") or "").strip()
    return raw.zfill(SIC_DIGITS) if raw.isdigit() and len(raw) <= SIC_DIGITS else None


def sic2(code: Any) -> float:
    """Two-digit major group of a four-digit SIC string, as a float (NaN when missing)."""
    text = "" if code is None or (isinstance(code, float) and np.isnan(code)) else str(code).strip()
    return float(text.zfill(SIC_DIGITS)[:2]) if text.isdigit() else float("nan")


def run_sic_ingest(store: Store, edgar: Any, *, limit: int | None = None,
                   progress: Callable[[int, int], None] | None = None) -> dict[str, int]:
    """Fetch `sic` for every CIK in `eightk_ingest_meta` not yet in the `sic` table (one request per CIK, the first
    submissions page only) and write one row per symbol. Resumable: rerun to continue."""
    meta = store.read_table(CIK_META_TABLE)
    have = set(store.read_table(TABLE)["cik"]) if store.has_table(TABLE) else set()
    todo = meta.loc[~meta["cik"].isin(have)]
    todo = todo if limit is None else todo.head(limit)
    n_rows = with_sic = 0
    rows: list[dict[str, Any]] = []
    for n, r in enumerate(todo.itertuples(), 1):
        pages = edgar.submissions(r.cik, include_older=False)
        code = parse_sic(pages[0]) if pages else None
        rows += [{"symbol": s.strip().upper(), "cik": r.cik, "sic": code} for s in str(r.symbols).split(",") if s.strip()]
        if rows and (n % WRITE_EVERY == 0 or n == len(todo)):
            store.write_table(TABLE, pd.DataFrame(rows, columns=COLUMNS), ["symbol"])
            n_rows, with_sic, rows = n_rows + len(rows), with_sic + sum(x["sic"] is not None for x in rows), []
        if progress is not None:
            progress(n, len(todo))
    log.info("sic_ingest", ciks=len(todo), rows=n_rows)
    return {"ciks": len(todo), "rows": n_rows, "with_sic": with_sic}


def join_sic(store: Any, panel: pd.DataFrame) -> pd.DataFrame:
    """``panel`` plus `sic2`. Unchanged when the store has no `sic` table or the panel already carries the column."""
    has = getattr(store, "has_table", None)
    if panel is None or panel.empty or SIC2 in panel.columns or not callable(has) or not has(TABLE):
        return panel
    codes = store.read_table(TABLE).drop_duplicates("symbol").set_index("symbol")["sic"].map(sic2)
    return panel.assign(**{SIC2: panel["symbol"].astype(str).map(codes).astype(float).to_numpy()})


__all__ = ["TABLE", "COLUMNS", "SIC2", "parse_sic", "sic2", "run_sic_ingest", "join_sic"]
