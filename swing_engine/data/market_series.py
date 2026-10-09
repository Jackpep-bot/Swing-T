"""Market-wide daily series: Cboe VIX / VIX9D / VIX3M and Kenneth French daily factors (FF3 + momentum).

docs/proposals/free-data-sources-2026-10.md sections 6 and 8 (approved). No API key for either source.

Store tables (written by `swing ingest-vix` / `swing ingest-french`):

* `vix` (date, vix_open, vix_high, vix_low, vix_close, vix9d_close, vix3m_close). Cboe index levels are final at
  the close and never revised, so the value for session D is usable at D's close (a next-open entry). The ingest
  drops rows dated on or after its run day: Cboe's CSVs carry the current session's partial row intraday.
* `ff_factors` (date, mkt_rf, smb, hml, rf, mom, known_from). Daily returns as decimals (the file's percent / 100);
  -99.99 / -999 are NaN. French publishes with a lag (the October 2026 file holds data through August 2026) and
  rewrites history each month. Rule: a factor value for date D is treated as known from the first calendar day of
  month(D) + FF_PUBLICATION_LAG_MONTHS (`known_from`). The only consumer is the residual-momentum regression
  (`features.extra` `ff3_resid_mom_*`), which for a row in month M uses factor days through the end of month M-2
  only, so it never reads a value before its `known_from`. The panel's `ff_*` columns hold the factor return OF
  that row's date, which is NOT known on that date: no rule may read them same-day.
* `market_series_meta` (source, url, downloaded_on, vintage, rows, first_date, last_date): one row per source file
  per ingest; `vintage` is the CRSP month named in the French file header ("created by using the 202608 CRSP
  database"), so a replay records which revision of the history it used.

`join_market_series(store, panel)` adds the VIX columns (same value on every symbol's row for a date) and the
`ff_*` columns to a panel when the tables exist; it is a no-op otherwise.
"""
from __future__ import annotations

import io
import re
import zipfile
from collections.abc import Callable
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
import structlog

from ._common import TZ
from .store import Store

log = structlog.get_logger(__name__)

# ---- sources (fetched once per ingest; no key) -----------------------------------------------------------------
CBOE_BASE = "https://cdn.cboe.com/api/global/us_indices/daily_prices"
VIX_URLS: dict[str, str] = {
    "vix": f"{CBOE_BASE}/VIX_History.csv",
    "vix9d": f"{CBOE_BASE}/VIX9D_History.csv",
    "vix3m": f"{CBOE_BASE}/VIX3M_History.csv",
}
FRENCH_BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp"
FF3_URL = f"{FRENCH_BASE}/F-F_Research_Data_Factors_daily_CSV.zip"
MOM_URL = f"{FRENCH_BASE}/F-F_Momentum_Factor_daily_CSV.zip"

# ---- tables -----------------------------------------------------------------------------------------------------
VIX_TABLE = "vix"
FF_TABLE = "ff_factors"
META_TABLE = "market_series_meta"
VIX_SCHEMA: dict[str, str] = {
    "date": "DATE", "vix_open": "DOUBLE", "vix_high": "DOUBLE", "vix_low": "DOUBLE", "vix_close": "DOUBLE",
    "vix9d_close": "DOUBLE", "vix3m_close": "DOUBLE",
}
FF_SCHEMA: dict[str, str] = {
    "date": "DATE", "mkt_rf": "DOUBLE", "smb": "DOUBLE", "hml": "DOUBLE", "rf": "DOUBLE", "mom": "DOUBLE",
    "known_from": "DATE",
}
META_SCHEMA: dict[str, str] = {
    "source": "VARCHAR", "url": "VARCHAR", "downloaded_on": "DATE", "vintage": "VARCHAR", "rows": "INTEGER",
    "first_date": "DATE", "last_date": "DATE",
}
DATE_KEYS = ["date"]
META_KEYS = ["source", "downloaded_on"]

VIX_COLUMNS = [c for c in VIX_SCHEMA if c != "date"]
FF_COLUMNS = ["mkt_rf", "smb", "hml", "rf", "mom"]
FF_PANEL_PREFIX = "ff_"  # panel columns ff_mkt_rf, ff_smb, ff_hml, ff_rf, ff_mom
FF_PUBLICATION_LAG_MONTHS = 2  # Aug 2026 data appeared 2026-09-24; known from the 1st of month + 2
FRENCH_MISSING = (-99.99, -999.0)
FRENCH_PCT = 100.0
_FRENCH_HEADER = {"Mkt-RF": "mkt_rf", "SMB": "smb", "HML": "hml", "RF": "rf", "Mom": "mom"}
_VINTAGE = re.compile(r"created by using the (\d{6}) CRSP database")

Fetch = Callable[[str], bytes]


def _default_fetch() -> Fetch:
    from ._http import Http

    return Http().get_bytes


# ================================================================================================= parsing
def parse_cboe_csv(text: str, name: str) -> pd.DataFrame:
    """Cboe `<NAME>_History.csv` (DATE mm/dd/yyyy, OPEN, HIGH, LOW, CLOSE) -> date + `<name>_open/high/low/close`."""
    df = pd.read_csv(io.StringIO(text))
    df.columns = [c.strip().lower() for c in df.columns]
    out = pd.DataFrame({"date": pd.to_datetime(df["date"], format="%m/%d/%Y").dt.date})
    for c in ("open", "high", "low", "close"):
        out[f"{name}_{c}"] = pd.to_numeric(df[c], errors="coerce")
    return out.dropna(subset=[f"{name}_close"]).drop_duplicates("date", keep="last")


def vix_frame(texts: dict[str, str], today: date) -> pd.DataFrame:
    """The `vix` table rows from the three Cboe CSVs; rows dated >= ``today`` are dropped (intraday partials)."""
    vix = parse_cboe_csv(texts["vix"], "vix")
    for name in ("vix9d", "vix3m"):
        if name in texts:
            vix = vix.merge(parse_cboe_csv(texts[name], name)[["date", f"{name}_close"]], on="date", how="left")
    vix = vix.reindex(columns=list(VIX_SCHEMA))
    return vix.loc[vix["date"] < today].reset_index(drop=True)


def french_vintage(text: str) -> str | None:
    m = _VINTAGE.search(text)
    return m.group(1) if m else None


def parse_french_daily(text: str) -> pd.DataFrame:
    """A French daily CSV (preamble, `,Mkt-RF,...` header, yyyymmdd rows, copyright footer) -> date + decimals."""
    lines = text.splitlines()
    head = next(i for i, ln in enumerate(lines) if ln.startswith(",") and any(k in ln for k in _FRENCH_HEADER))
    cols = [_FRENCH_HEADER[c.strip()] for c in lines[head].split(",")[1:]]
    rows = [ln.split(",") for ln in lines[head + 1:] if ln[:8].isdigit()]
    df = pd.DataFrame([[r[0].strip(), *r[1:]] for r in rows], columns=["date", *cols])
    out = pd.DataFrame({"date": pd.to_datetime(df["date"], format="%Y%m%d").dt.date})
    for c in cols:
        v = pd.to_numeric(df[c], errors="coerce")
        out[c] = v.where(~v.isin(FRENCH_MISSING)) / FRENCH_PCT
    return out


def unzip_text(blob: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        return z.read(z.namelist()[0]).decode("latin-1")


def known_from(days: pd.Series) -> pd.Series:
    """First calendar day of month(D) + FF_PUBLICATION_LAG_MONTHS for each date D."""
    p = pd.to_datetime(days).dt.to_period("M") + FF_PUBLICATION_LAG_MONTHS
    return p.dt.start_time.dt.date


def ff_frame(ff3_text: str, mom_text: str | None) -> pd.DataFrame:
    ff = parse_french_daily(ff3_text)
    if mom_text is not None:
        ff = ff.merge(parse_french_daily(mom_text), on="date", how="left")
    ff = ff.reindex(columns=[c for c in FF_SCHEMA if c != "known_from"])
    return ff.assign(known_from=known_from(ff["date"]))


# ================================================================================================= ingest
def _meta(source: str, url: str, today: date, frame: pd.DataFrame, vintage: str | None = None) -> dict[str, Any]:
    return {"source": source, "url": url, "downloaded_on": today, "vintage": vintage, "rows": len(frame),
            "first_date": frame["date"].min() if len(frame) else None,
            "last_date": frame["date"].max() if len(frame) else None}


def _write_meta(store: Store, metas: list[dict[str, Any]]) -> None:
    store.write_table(META_TABLE, pd.DataFrame(metas, columns=list(META_SCHEMA)), META_KEYS, schema=META_SCHEMA)


def run_vix_ingest(store: Store, fetch: Fetch | None = None, *, today: date | None = None) -> dict[str, Any]:
    """Fetch the three Cboe CSVs and upsert `vix` (full history each run; the files are ~0.5 MB)."""
    day = today or pd.Timestamp.now(tz=TZ).date()
    get = fetch or _default_fetch()
    texts = {name: get(url).decode("utf-8") for name, url in VIX_URLS.items()}
    frame = vix_frame(texts, day)
    rows = store.write_table(VIX_TABLE, frame, DATE_KEYS, schema=VIX_SCHEMA)
    _write_meta(store, [_meta(f"cboe_{n}", VIX_URLS[n], day, parse_cboe_csv(t, n)) for n, t in texts.items()])
    result = {"rows": rows, "first_date": str(frame["date"].min()), "last_date": str(frame["date"].max()),
              "vix9d_rows": int(frame["vix9d_close"].notna().sum()),
              "vix3m_rows": int(frame["vix3m_close"].notna().sum())}
    log.info("vix_ingest_done", **result)
    return result


def run_french_ingest(store: Store, fetch: Fetch | None = None, *, today: date | None = None) -> dict[str, Any]:
    """Fetch the daily FF3 and momentum zips and upsert `ff_factors` (French rewrites history: every row is
    replaced by the current vintage, which `market_series_meta` records)."""
    day = today or pd.Timestamp.now(tz=TZ).date()
    get = fetch or _default_fetch()
    ff3_text = unzip_text(get(FF3_URL))
    mom_text = unzip_text(get(MOM_URL))
    frame = ff_frame(ff3_text, mom_text)
    rows = store.write_table(FF_TABLE, frame, DATE_KEYS, schema=FF_SCHEMA)
    vintage = french_vintage(ff3_text)
    _write_meta(store, [_meta("french_ff3_daily", FF3_URL, day, frame, vintage),
                        _meta("french_mom_daily", MOM_URL, day, parse_french_daily(mom_text), french_vintage(mom_text))])
    result = {"rows": rows, "first_date": str(frame["date"].min()), "last_date": str(frame["date"].max()),
              "vintage": vintage, "downloaded_on": str(day)}
    log.info("french_ingest_done", **result)
    return result


# ================================================================================================= panel join
def _session_dates(ts: pd.Series) -> pd.Series:
    t = pd.to_datetime(ts)
    if t.dt.tz is not None:
        t = t.dt.tz_convert(TZ).dt.tz_localize(None)
    return t.dt.normalize()


def join_market_series(store: Any, panel: pd.DataFrame) -> pd.DataFrame:
    """``panel`` plus the `vix` columns and `ff_*` factor columns by session date, for the tables the store has.
    Unchanged when neither table exists or the panel already carries the columns. See the module docstring for
    which columns are known on their own row's date (VIX: yes, at the close; ff_*: no)."""
    has = getattr(store, "has_table", None)
    if panel is None or panel.empty or not callable(has):
        return panel
    add: dict[str, np.ndarray] = {}
    day = None
    for table, cols, prefix in ((VIX_TABLE, VIX_COLUMNS, ""), (FF_TABLE, FF_COLUMNS, FF_PANEL_PREFIX)):
        out_cols = [f"{prefix}{c}" for c in cols]
        if not has(table) or all(c in panel.columns for c in out_cols):
            continue
        src = store.read_table(table)
        if src.empty:
            continue
        day = _session_dates(panel["ts"]) if day is None else day
        src = src.assign(date=pd.to_datetime(src["date"])).drop_duplicates("date").set_index("date")
        for c, out in zip(cols, out_cols, strict=True):
            if out not in panel.columns and c in src.columns:
                add[out] = day.map(src[c].astype(float)).to_numpy(dtype=float)
    if not add:
        return panel
    log.info("market_series_join", columns=sorted(add))
    return panel.assign(**add)


__all__ = [
    "VIX_URLS", "FF3_URL", "MOM_URL", "VIX_TABLE", "FF_TABLE", "META_TABLE", "VIX_COLUMNS", "FF_COLUMNS",
    "FF_PANEL_PREFIX", "FF_PUBLICATION_LAG_MONTHS", "parse_cboe_csv", "vix_frame", "parse_french_daily",
    "french_vintage", "ff_frame", "known_from", "unzip_text", "run_vix_ingest", "run_french_ingest",
    "join_market_series",
]
