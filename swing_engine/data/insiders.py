"""SEC Form 4 open-market insider trades from the quarterly "Insider Transactions Data Sets" (2006 Q1 onward,
docs/proposals/free-data-sources-2026-10.md section 1) and the panel features the two insider strategies read.

Table `insider_trades` (one row per non-derivative transaction x reporting owner): symbol, cik (issuer),
accession, trans_id (NONDERIV_TRANS_SK), filing_date, transaction_date, owner_cik, owner_name, is_director,
is_officer, officer_title, is_ten_pct, code, shares, price, value. Only original Form 4 filings (4/A amendments
and Forms 3/5 are dropped) and only open-market codes P (purchase) and S (sale); grants, exercises and tax
withholding (A, M, F, ...) never enter. `insider_ingest_meta` records each quarter so `swing ingest-insiders`
resumes where it stopped.

Point-in-time: FILING_DATE has no time of day, so a filing is visible from the session AFTER its filing date
(the same rule as companyfacts); never keyed on the transaction date. The Cohen-Malloy-Pomorski (2012) label for
an insider in calendar year Y uses only that insider's trades filed before Jan 1 of Y.

Panel features (`join_insiders`, called from `data.fundamentals.join_edgar`):
* `insider_cluster_score`: distinct insiders with code-P buys visible in the last CLUSTER_WINDOW_DAYS calendar
  days / CLUSTER_MIN (so >= 1 means a cluster, `insider_cluster` min_score 1.0); 0 when >= CLUSTER_IDENTICAL_PCT
  of those trades share one transaction date + price (ESPP / joint-filer pseudo-clusters).
* `opp_buy_value_21d`: dollar value of opportunistic code-P buys visible in the last OPP_WINDOW_SESSIONS sessions.
* `opp_buy_flag`: 1 on the session an opportunistic buy first becomes visible (`opportunistic_insider_purchases_cmp`).
"""
from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Callable, Iterable
from datetime import date
from typing import Any

import httpx
import numpy as np
import pandas as pd
import structlog

from swing_engine.monitor.constants import (
    INSIDER_CLUSTER_IDENTICAL_REJECT_PCT,
    INSIDER_CLUSTER_MIN,
    INSIDER_CLUSTER_WINDOW_DAYS,
)

from ._common import TZ
from .calendar import trading_days
from .edgar import CIK_WIDTH, Edgar
from .store import Store

log = structlog.get_logger(__name__)

INSIDERS_VERSION = "2026.10.08"
DATASET_PATH = "/files/structureddata/data/insider-transactions-data-sets/{quarter}_form345.zip"
FIRST_YEAR = 2006  # first posted quarter: 2006q1
HTTP_NOT_FOUND = 404

TRADES_TABLE = "insider_trades"
TRADE_KEYS: list[str] = ["accession", "trans_id", "owner_cik"]
TRADE_SCHEMA: dict[str, str] = {
    "symbol": "VARCHAR",
    "cik": "VARCHAR",
    "accession": "VARCHAR",
    "trans_id": "VARCHAR",
    "filing_date": "DATE",
    "transaction_date": "DATE",
    "owner_cik": "VARCHAR",
    "owner_name": "VARCHAR",
    "is_director": "BOOLEAN",
    "is_officer": "BOOLEAN",
    "officer_title": "VARCHAR",
    "is_ten_pct": "BOOLEAN",
    "code": "VARCHAR",
    "shares": "DOUBLE",
    "price": "DOUBLE",
    "value": "DOUBLE",
}
TRADE_COLUMNS = list(TRADE_SCHEMA)
META_TABLE = "insider_ingest_meta"
META_KEYS: list[str] = ["quarter"]
META_SCHEMA: dict[str, str] = {
    "quarter": "VARCHAR", "fetched_on": "DATE", "status": "VARCHAR", "rows": "INTEGER", "error": "VARCHAR",
}
STATUS_OK, STATUS_MISSING, STATUS_ERROR = "ok", "missing", "error"  # missing = not posted yet (404), retried

FORM = "4"
BUY, SELL = "P", "S"
#: open-market codes kept and the acquired/disposed flag each must carry ("" = flag left blank by the filer)
KEEP_CODES: dict[str, str] = {BUY: "A", SELL: "D"}
DATE_FORMAT = "%d-%b-%Y"  # 31-JAN-2024
SEC_TICKER_CLASS_SEP, STORE_TICKER_CLASS_SEP = "-", "."
NO_SYMBOL = frozenset({"", "NONE", "N/A", "NA"})

# ---- Cohen-Malloy-Pomorski (2012) classification -----------------------------------------------------------
CMP_HISTORY_YEARS = 3  # a trade in each of the 3 prior calendar years; routine = same month in all 3
ROUTINE, OPPORTUNISTIC, UNCLASSIFIED = "routine", "opportunistic", "unclassified"
#: CMP leave insiders without 3 prior years of trades unclassified (excluded); True counts them as opportunistic.
UNCLASSIFIED_IS_OPPORTUNISTIC = False

# ---- panel features --------------------------------------------------------------------------------------
CLUSTER_MIN = INSIDER_CLUSTER_MIN
CLUSTER_WINDOW_DAYS = INSIDER_CLUSTER_WINDOW_DAYS
CLUSTER_IDENTICAL_PCT = INSIDER_CLUSTER_IDENTICAL_REJECT_PCT
OPP_WINDOW_SESSIONS = 21  # card feature spec: last 21 sessions
FEATURE_COLUMNS: list[str] = ["insider_cluster_score", "opp_buy_value_21d", "opp_buy_flag"]
CALENDAR_PAD_DAYS = 45  # sessions fetched beyond the last filing/panel day


# ============================================================================================ parsing
def _tsv(zf: zipfile.ZipFile, name: str, cols: list[str]) -> pd.DataFrame:
    with zf.open(name) as f:
        return pd.read_csv(
            f, sep="\t", dtype=str, usecols=cols, quoting=csv.QUOTE_NONE, keep_default_na=False,
            encoding="utf-8", encoding_errors="replace",
        )


def _norm_symbol(s: pd.Series) -> pd.Series:
    return s.str.strip().str.upper().str.replace(SEC_TICKER_CLASS_SEP, STORE_TICKER_CLASS_SEP, regex=False)


def cik_symbols(tickers: pd.DataFrame) -> dict[str, list[str]]:
    """company_tickers.json frame -> {10-digit CIK: [store-style symbols]}."""
    out: dict[str, list[str]] = {}
    syms = _norm_symbol(tickers["symbol"].astype(str))
    for cik, sym in zip(tickers["cik"].astype(str).str.zfill(CIK_WIDTH), syms, strict=False):
        out.setdefault(cik, []).append(sym)
    return out


def parse_quarter(data: bytes, cik_map: dict[str, list[str]] | None = None) -> pd.DataFrame:
    """`insider_trades` rows from one quarterly zip. Symbol: the issuer CIK's current ticker (the filed one when it
    is among them, else the first), falling back to the filed ISSUERTRADINGSYMBOL for CIKs no longer listed."""
    cik_map = cik_map or {}
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        sub = _tsv(zf, "SUBMISSION.tsv", ["ACCESSION_NUMBER", "FILING_DATE", "DOCUMENT_TYPE", "ISSUERCIK",
                                          "ISSUERTRADINGSYMBOL"])
        tr = _tsv(zf, "NONDERIV_TRANS.tsv", ["ACCESSION_NUMBER", "NONDERIV_TRANS_SK", "TRANS_DATE", "TRANS_CODE",
                                             "TRANS_SHARES", "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD"])
        own = _tsv(zf, "REPORTINGOWNER.tsv", ["ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNERNAME",
                                              "RPTOWNER_RELATIONSHIP", "RPTOWNER_TITLE"])
    sub = sub[sub["DOCUMENT_TYPE"].str.strip() == FORM]
    code = tr["TRANS_CODE"].str.strip().str.upper()
    ad = tr["TRANS_ACQUIRED_DISP_CD"].str.strip().str.upper()
    keep = pd.Series(False, index=tr.index)
    for c, flag in KEEP_CODES.items():
        keep |= (code == c) & ad.isin([flag, ""])
    tr = tr[keep].assign(code=code[keep])
    df = tr.merge(sub, on="ACCESSION_NUMBER").merge(own, on="ACCESSION_NUMBER")
    if df.empty:
        return pd.DataFrame(columns=TRADE_COLUMNS)
    cik = df["ISSUERCIK"].str.strip().str.zfill(CIK_WIDTH)
    filed_sym = _norm_symbol(df["ISSUERTRADINGSYMBOL"])

    def pick(c: str, f: str) -> str:
        current = cik_map.get(c)
        if not current:
            return f
        return f if f in current else current[0]

    rel = df["RPTOWNER_RELATIONSHIP"].str.lower()
    shares = pd.to_numeric(df["TRANS_SHARES"], errors="coerce")
    price = pd.to_numeric(df["TRANS_PRICEPERSHARE"], errors="coerce")
    out = pd.DataFrame(
        {
            "symbol": [pick(c, f) for c, f in zip(cik, filed_sym, strict=True)],
            "cik": cik,
            "accession": df["ACCESSION_NUMBER"].str.strip(),
            "trans_id": df["NONDERIV_TRANS_SK"].str.strip(),
            "filing_date": pd.to_datetime(df["FILING_DATE"].str.strip(), format=DATE_FORMAT, errors="coerce").dt.date,
            "transaction_date": pd.to_datetime(df["TRANS_DATE"].str.strip(), format=DATE_FORMAT,
                                               errors="coerce").dt.date,
            "owner_cik": df["RPTOWNERCIK"].str.strip().str.zfill(CIK_WIDTH),
            "owner_name": df["RPTOWNERNAME"].str.strip(),
            "is_director": rel.str.contains("director", regex=False),
            "is_officer": rel.str.contains("officer", regex=False),
            "officer_title": df["RPTOWNER_TITLE"].str.strip(),
            "is_ten_pct": rel.str.contains("tenpercent", regex=False),
            "code": df["code"],
            "shares": shares,
            "price": price,
            "value": shares * price,
        },
        columns=TRADE_COLUMNS,
    )
    out = out[~out["symbol"].isin(NO_SYMBOL) & out["filing_date"].notna() & out["transaction_date"].notna()]
    return out.sort_values(["filing_date", "symbol", "accession", "trans_id"], kind="mergesort").reset_index(drop=True)


# ============================================================================================= ingest
def quarter_list(start_year: int, today: date) -> list[str]:
    """'2006q1' .. the last quarter that ended before `today`."""
    last_q = (today.month - 1) // 3  # quarters fully completed this year
    out = []
    for y in range(start_year, today.year + 1):
        for q in range(1, 5):
            if y == today.year and q > last_q:
                break
            out.append(f"{y}q{q}")
    return out


def run_insider_ingest(
    store: Store,
    edgar: Edgar,
    *,
    start_year: int = FIRST_YEAR,
    quarters: int | None = None,
    today: date | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Download each quarterly zip not yet ingested OK (at most `quarters` of them this run) into `insider_trades`.
    A 404 (quarter not posted yet) is recorded as missing and retried next run; other failures never stop the run."""
    day = today or date.today()
    meta = store.read_table(META_TABLE)
    done = set(meta.loc[meta["status"] == STATUS_OK, "quarter"]) if not meta.empty else set()
    todo = [q for q in quarter_list(start_year, day) if q not in done]
    if quarters is not None:
        todo = todo[: max(0, int(quarters))]
    if progress:
        progress(f"insiders: {len(done)} quarters done, {len(todo)} to fetch")
    cik_map = cik_symbols(edgar.company_tickers()) if todo else {}
    totals = {"rows": 0, "fetched": 0, "missing": 0, "failed": 0}
    errors: dict[str, str] = {}
    for q in todo:
        row: dict[str, Any] = {"quarter": q, "fetched_on": day, "rows": 0, "error": None}
        try:
            data = edgar.http.get_bytes(f"{edgar.base_url}{DATASET_PATH.format(quarter=q)}")
            row["rows"] = store.write_table(TRADES_TABLE, parse_quarter(data, cik_map), TRADE_KEYS, schema=TRADE_SCHEMA)
            row["status"] = STATUS_OK
            totals["fetched"] += 1
            totals["rows"] += row["rows"]
        except httpx.HTTPStatusError as exc:
            missing = exc.response.status_code == HTTP_NOT_FOUND
            row["status"] = STATUS_MISSING if missing else STATUS_ERROR
            row["error"] = str(exc)[:500]
            totals["missing" if missing else "failed"] += 1
            if not missing:
                errors[q] = row["error"]
        except Exception as exc:  # a corrupt zip must not stop the other quarters
            row["status"], row["error"] = STATUS_ERROR, str(exc)[:500]
            totals["failed"] += 1
            errors[q] = row["error"]
            log.warning("insider_ingest_quarter_failed", quarter=q, error=row["error"])
        store.write_table(META_TABLE, pd.DataFrame([row], columns=list(META_SCHEMA)), META_KEYS, schema=META_SCHEMA)
        if progress:
            progress(f"insiders: {q} {row['status']} {row['rows']} rows")
    log.info("insider_ingest_done", **totals)
    return {**totals, "quarters_done_before": len(done), "errors": errors}


# ===================================================================================== classification
def cmp_labels(trades: pd.DataFrame) -> pd.DataFrame:
    """CMP label per (owner_cik, year) for every year an owner traded: routine when one calendar month carries a
    trade in each of the CMP_HISTORY_YEARS prior years, opportunistic when every prior year has a trade but no month
    repeats, else unclassified. Only trades FILED before Jan 1 of `year` count (point-in-time)."""
    cols = ["owner_cik", "year", "cmp_class"]
    if trades is None or trades.empty:
        return pd.DataFrame(columns=cols)
    td = pd.to_datetime(trades["transaction_date"])
    t = pd.DataFrame({"owner_cik": trades["owner_cik"].to_numpy(), "ty": td.dt.year.to_numpy(),
                      "tm": td.dt.month.to_numpy(),
                      "known": pd.to_datetime(trades["filing_date"]).dt.year.to_numpy() + 1})
    first_known = t.groupby(["owner_cik", "ty", "tm"])["known"].min()
    hist: dict[str, dict[tuple[int, int], int]] = {}
    for (owner, ty, tm), k in first_known.items():
        hist.setdefault(owner, {})[(int(ty), int(tm))] = int(k)
    rows = []
    for owner, year in t[["owner_cik", "ty"]].drop_duplicates().itertuples(index=False):
        h = hist[owner]
        months = [{m for (yy, m), k in h.items() if yy == y and k <= year}
                  for y in range(year - CMP_HISTORY_YEARS, year)]
        if not all(months):
            label = UNCLASSIFIED
        elif set.intersection(*months):
            label = ROUTINE
        else:
            label = OPPORTUNISTIC
        rows.append((owner, int(year), label))
    return pd.DataFrame(rows, columns=cols)


def label_trades(trades: pd.DataFrame, history: pd.DataFrame | None = None) -> pd.Series:
    """`cmp_class` for each row of `trades`, classified on `history` (default: `trades` itself), index-aligned."""
    labels = cmp_labels(trades if history is None else history)
    key = pd.DataFrame({"owner_cik": trades["owner_cik"].to_numpy(),
                        "year": pd.to_datetime(trades["transaction_date"]).dt.year.to_numpy()})
    merged = key.merge(labels, on=["owner_cik", "year"], how="left")
    return pd.Series(merged["cmp_class"].fillna(UNCLASSIFIED).to_numpy(), index=trades.index, name="cmp_class")


# ======================================================================================= panel features
def _days(values: Iterable[Any]) -> np.ndarray:
    ts = pd.to_datetime(pd.Series(list(values) if not isinstance(values, pd.Series) else values))
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert(TZ).dt.tz_localize(None)
    return ts.to_numpy().astype("datetime64[D]")


def _expand(keys: pd.DataFrame, start: np.ndarray, length: np.ndarray) -> pd.DataFrame:
    """Repeat each row of `keys` `length` times with `idx` = start, start+1, ..."""
    length = np.maximum(length, 0)
    rep = keys.loc[keys.index.repeat(length)].reset_index(drop=True)
    offsets = np.arange(int(length.sum())) - np.repeat(np.cumsum(length) - length, length)
    return rep.assign(idx=np.repeat(start, length) + offsets)


def insider_features(trades: pd.DataFrame, index: pd.DataFrame, cmp_class: pd.Series | None = None) -> pd.DataFrame:
    """FEATURE_COLUMNS per (symbol, ts) row of `index`, from `insider_trades` rows (`cmp_class` aligned with them;
    default: classified on `trades` alone). Zero where nothing is visible."""
    out = index[["symbol", "ts"]].reset_index(drop=True).copy()
    for c in FEATURE_COLUMNS:
        out[c] = 0.0
    if out.empty or trades is None or trades.empty:
        return out
    labels = label_trades(trades) if cmp_class is None else cmp_class
    buys = trades.assign(cmp_class=labels.to_numpy())
    buys = buys[(buys["code"] == BUY) & buys["symbol"].isin(set(out["symbol"]))].reset_index(drop=True)
    if buys.empty:
        return out
    panel_days = _days(out["ts"])
    filed = _days(buys["filing_date"])
    near = (filed >= panel_days.min() - np.timedelta64(CALENDAR_PAD_DAYS, "D")) & (filed <= panel_days.max())
    buys, filed = buys[near].reset_index(drop=True), filed[near]
    if buys.empty:
        return out
    sessions = np.array(trading_days(min(filed.min(), panel_days.min()).astype(date),
                                     (max(filed.max(), panel_days.max()) + np.timedelta64(CALENDAR_PAD_DAYS, "D")).astype(date)),
                        dtype="datetime64[D]")
    buys["idx"] = np.searchsorted(sessions, filed, side="right")  # first session AFTER the filing date
    buys["avail"] = sessions[np.minimum(buys["idx"], len(sessions) - 1)]
    out["idx"] = np.searchsorted(sessions, panel_days, side="left")
    keys = ["symbol", "idx"]

    opp_ok = [OPPORTUNISTIC, UNCLASSIFIED] if UNCLASSIFIED_IS_OPPORTUNISTIC else [OPPORTUNISTIC]
    opp = buys[buys["cmp_class"].isin(opp_ok)].drop_duplicates(["accession", "trans_id"])
    if not opp.empty:
        per_day = opp.groupby(keys, as_index=False)["value"].sum(min_count=1)
        flag = per_day[keys].assign(opp_buy_flag=1.0)
        win = _expand(per_day[["symbol", "value"]], per_day["idx"].to_numpy(),
                      np.full(len(per_day), OPP_WINDOW_SESSIONS)).groupby(keys, as_index=False)["value"].sum()
        out = out.drop(columns=["opp_buy_flag"]).merge(flag, on=keys, how="left")
        out = out.drop(columns=["opp_buy_value_21d"]).merge(win.rename(columns={"value": "opp_buy_value_21d"}),
                                                            on=keys, how="left")

    # cluster: sessions s with avail <= s < avail + CLUSTER_WINDOW_DAYS (filing visible within the window)
    end = np.searchsorted(sessions, buys["avail"].to_numpy() + np.timedelta64(CLUSTER_WINDOW_DAYS, "D"), side="left")
    ex = _expand(buys[["symbol", "owner_cik", "accession", "trans_id", "transaction_date", "price"]],
                 buys["idx"].to_numpy(), end - buys["idx"].to_numpy())
    owners = ex.groupby(keys)["owner_cik"].nunique()
    trades_in = ex.drop_duplicates(["symbol", "idx", "accession", "trans_id"])
    same = trades_in.groupby([*keys, "transaction_date", trades_in["price"].fillna(-1.0)]).size()
    identical = same.groupby(level=[0, 1]).max() / trades_in.groupby(keys).size()
    score = owners / CLUSTER_MIN
    score[(owners >= CLUSTER_MIN) & (identical * 100.0 >= CLUSTER_IDENTICAL_PCT)] = 0.0
    out = out.drop(columns=["insider_cluster_score"]).merge(score.rename("insider_cluster_score").reset_index(),
                                                            on=keys, how="left")
    for c in FEATURE_COLUMNS:
        out[c] = out[c].fillna(0.0).astype("float64")
    return out[["symbol", "ts", *FEATURE_COLUMNS]]


def join_insiders(store: Store, panel: pd.DataFrame) -> pd.DataFrame:
    """``panel`` plus FEATURE_COLUMNS from `insider_trades` (visible the session after the filing date). Unchanged
    when the table is absent or the panel already carries the columns."""
    if panel is None or panel.empty or all(c in panel.columns for c in FEATURE_COLUMNS):
        return panel
    has = getattr(store, "has_table", None)
    if not callable(has) or not has(TRADES_TABLE):
        return panel
    syms = sorted(set(panel["symbol"].astype(str)))
    buys = store.read_table(TRADES_TABLE, "code = ? AND symbol IN (SELECT unnest(?))", [BUY, syms])
    history = (store.read_table(TRADES_TABLE, "owner_cik IN (SELECT unnest(?))", [sorted(set(buys["owner_cik"]))])
               if not buys.empty else buys)
    feats = insider_features(buys, panel, label_trades(buys, history) if not buys.empty else None)
    missing = [c for c in FEATURE_COLUMNS if c not in panel.columns]
    log.info("insider_join", symbols=len(syms), buys=len(buys), columns=missing)
    return panel.assign(**{c: feats[c].to_numpy() for c in missing})


__all__ = [
    "TRADES_TABLE", "META_TABLE", "FEATURE_COLUMNS", "parse_quarter", "quarter_list", "run_insider_ingest",
    "cmp_labels", "label_trades", "insider_features", "join_insiders", "cik_symbols",
]
