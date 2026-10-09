"""Alpaca historical news (Benzinga, free with the paper key; owner-approved data build 1, 2026-10-09) reduced to
headline counts, and the point-in-time no-news flag (Chan 2003, docs/strategies/*_no_news.md).

Ingest (`swing ingest-news`): GET data.alpaca.markets/v1beta1/news for the whole market one calendar month at a
time (no symbol filter: one stream covers every ticker), 50 articles a page, oldest first, no article content.
Table `news_articles` keeps only (id, symbol, published_at, source): one row per article x tagged symbol, never
headline or body text. `news_ingest_meta` marks each finished month so a run resumes where it stopped; the month
still in progress is stored as `partial` and fetched again next run. Rate limit: the Basic plan's 200 calls/min,
throttled below it by `NEWS_CALLS_PER_MIN`.

Point-in-time: keyed on `created_at` (first publication), never `updated_at`. Panel features (`join_news`, called
from `data.fundamentals.join_edgar`):
* `news_count_1d`: articles tagged with the symbol published in (close - 24h, close] of the row's session close
  (early closes honoured), i.e. known at the close the signal is taken on.
* `news_flag_1d`: 1.0 when news_count_1d > 0.
Both are NaN on sessions whose 24h window touches a month not ingested, or that close after a partial month's
`fetched_until` (no false "no news"). Run `swing ingest-news` before the scan to cover the current session.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import structlog

from ._common import TZ
from ._http import Http
from .calendar import session_bounds
from .store import Store

log = structlog.get_logger(__name__)

NEWS_URL = "https://data.alpaca.markets/v1beta1/news"
NEWS_PAGE_LIMIT = 50  # API maximum per page
NEWS_CALLS_PER_MIN = 180  # Basic plan: 200/min (x-ratelimit-limit header, checked 2026-10-09)
NEWS_FIRST_DAY = date(2015, 1, 1)  # Benzinga history on Alpaca starts in 2015
NEWS_DEFAULT_START = date(2016, 1, 1)  # first bar in data/live/market.duckdb is 2016-01-04
WINDOW = pd.Timedelta(hours=24)

TABLE = "news_articles"
KEYS: list[str] = ["id", "symbol"]
SCHEMA: dict[str, str] = {"id": "BIGINT", "symbol": "VARCHAR", "published_at": "TIMESTAMPTZ", "source": "VARCHAR"}
META_TABLE = "news_ingest_meta"
META_KEYS: list[str] = ["month"]
META_SCHEMA: dict[str, str] = {
    "month": "VARCHAR", "fetched_on": "DATE", "status": "VARCHAR", "pages": "INTEGER", "rows": "INTEGER",
    "error": "VARCHAR", "fetched_until": "TIMESTAMP",  # UTC end of the fetched span (a partial month ends here)
}
STATUS_OK, STATUS_PARTIAL, STATUS_ERROR = "ok", "partial", "error"
FEATURE_COLUMNS: list[str] = ["news_count_1d", "news_flag_1d"]
SEC_PER_SYMBOL = 10**10  # composite sort key: symbol code * 1e10 + epoch seconds (fits int64)


# ============================================================================================ parsing
def parse_news_page(payload: dict[str, Any]) -> pd.DataFrame:
    """`news_articles` rows from one API page: one per article x symbol, published_at = created_at (UTC)."""
    rows = [
        {"id": int(a["id"]), "symbol": str(sym).upper().strip(), "published_at": a.get("created_at"),
         "source": a.get("source") or ""}
        for a in payload.get("news") or []
        if a.get("id") is not None and a.get("created_at")
        for sym in a.get("symbols") or []
        if str(sym).strip()
    ]
    df = pd.DataFrame(rows, columns=list(SCHEMA))
    df["published_at"] = pd.to_datetime(df["published_at"], utc=True)
    return df


# ============================================================================================= client
class AlpacaNews:
    """Thin REST client for the historical news endpoint; keys go in headers only (never logged)."""

    def __init__(self, api_key: str, secret_key: str, *, http: Http | None = None,
                 calls_per_min: float = NEWS_CALLS_PER_MIN) -> None:
        if http is None and not (api_key and secret_key):
            raise ValueError("alpaca news: ALPACA_API_KEY / ALPACA_SECRET_KEY are required")
        self.http = http or Http(rate_per_min=calls_per_min, headers={
            "APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key})

    def page(self, start: datetime, end: datetime, token: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {
            "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"), "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "limit": NEWS_PAGE_LIMIT, "sort": "asc", "include_content": "false",
        }
        if token:
            params["page_token"] = token
        return self.http.get_json(NEWS_URL, params=params)


# ============================================================================================= ingest
def month_list(start: date, end: date) -> list[str]:
    """'2016-01' .. the month containing `end`."""
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _month_bounds(month: str) -> tuple[datetime, datetime]:
    y, m = (int(x) for x in month.split("-"))
    start = datetime(y, m, 1)
    return start, datetime(y + 1, 1, 1) if m == 12 else datetime(y, m + 1, 1)


def run_news_ingest(
    store: Store,
    client: AlpacaNews,
    *,
    start: date = NEWS_DEFAULT_START,
    end: date | None = None,
    months: int | None = None,
    now: datetime | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Fetch every month in [start, end] not yet ingested OK (at most `months` this run) into `news_articles`.
    Rows are written page by page, so an interrupted month keeps what it fetched and is redone (upsert) next run."""
    now_utc = now or datetime.now(UTC).replace(tzinfo=None)
    last = end or now_utc.date()
    meta = store.read_table(META_TABLE)
    done = set(meta.loc[meta["status"] == STATUS_OK, "month"]) if not meta.empty else set()
    todo = [mo for mo in month_list(max(start, NEWS_FIRST_DAY), last) if mo not in done]
    if months is not None:
        todo = todo[: max(0, int(months))]
    if progress:
        progress(f"news: {len(done)} months done, {len(todo)} to fetch")
    totals = {"months": 0, "pages": 0, "rows": 0, "failed": 0}
    errors: dict[str, str] = {}
    for mo in todo:
        lo, hi = _month_bounds(mo)
        hi_eff = min(hi, now_utc)
        row: dict[str, Any] = {"month": mo, "fetched_on": now_utc.date(), "pages": 0, "rows": 0, "error": None,
                               "fetched_until": hi_eff}
        try:
            token: str | None = None
            while True:
                payload = client.page(lo, hi_eff, token)
                row["pages"] += 1
                row["rows"] += store.write_table(TABLE, parse_news_page(payload), KEYS, schema=SCHEMA)
                token = payload.get("next_page_token")
                if not token:
                    break
            row["status"] = STATUS_OK if hi <= now_utc else STATUS_PARTIAL
            totals["months"] += 1
        except Exception as exc:  # one bad month must not stop the run; it is retried next time
            row["status"], row["error"] = STATUS_ERROR, str(exc)[:500]
            totals["failed"] += 1
            errors[mo] = row["error"]
            log.warning("news_ingest_month_failed", month=mo, error=row["error"])
        totals["pages"] += row["pages"]
        totals["rows"] += row["rows"]
        store.write_table(META_TABLE, pd.DataFrame([row], columns=list(META_SCHEMA)), META_KEYS, schema=META_SCHEMA)
        if progress:
            progress(f"news: {mo} {row['status']} {row['pages']} pages {row['rows']} rows")
    log.info("news_ingest_done", **totals)
    return {**totals, "months_done_before": len(done), "errors": errors}


# ===================================================================================== panel features
def _closes(ts: pd.Series) -> pd.Series:
    """Session close (UTC) for each panel `ts` (midnight New York); NaT when the market was closed."""
    day = pd.to_datetime(ts)
    day = (day.dt.tz_convert(TZ) if day.dt.tz is not None else day.dt.tz_localize(TZ)).dt.date
    cache: dict[date, Any] = {}
    for d in set(day):
        b = session_bounds(d)
        cache[d] = pd.Timestamp(b[1]).tz_convert("UTC") if b is not None else pd.NaT
    return pd.to_datetime(day.map(cache), utc=True)


EPOCH = pd.Timestamp(0, tz="UTC")


def _epoch_s(ts: pd.Series) -> np.ndarray:
    """Whole epoch seconds, independent of the datetime unit (ns / us)."""
    return ((ts - EPOCH) // pd.Timedelta(seconds=1)).to_numpy(np.int64)


def news_features(
    articles: pd.DataFrame, index: pd.DataFrame, covered: Mapping[str, Any] | None = None
) -> pd.DataFrame:
    """FEATURE_COLUMNS per (symbol, ts) row of `index` from `news_articles` rows. `covered` maps each fetched month
    ('YYYY-MM') to the UTC instant it is complete up to (None = the whole month); a row whose 24h window touches an
    uncovered month, or closes after a partial month's fetch, gets NaN. covered=None treats everything as covered."""
    out = index[["symbol", "ts"]].reset_index(drop=True).copy()
    out["news_count_1d"] = np.nan
    if out.empty:
        return out.assign(news_flag_1d=np.nan)
    close = _closes(out["ts"])
    counts = np.zeros(len(out))
    if articles is not None and not articles.empty:
        codes = {s: i for i, s in enumerate(sorted(set(out["symbol"]) | set(articles["symbol"])))}
        a_sec = _epoch_s(pd.to_datetime(articles["published_at"], utc=True))
        a_key = np.sort(articles["symbol"].map(codes).to_numpy(np.int64) * SEC_PER_SYMBOL + a_sec)
        q_code = out["symbol"].map(codes).to_numpy(np.int64) * SEC_PER_SYMBOL
        ok = close.notna().to_numpy()
        c_sec = np.where(ok, _epoch_s(close.fillna(EPOCH)), 0)
        hi = np.searchsorted(a_key, q_code + c_sec, side="right")
        lo = np.searchsorted(a_key, q_code + c_sec - int(WINDOW.total_seconds()), side="right")
        counts = np.where(ok, hi - lo, 0)
    valid = close.notna()
    if covered is not None:
        start_m = (close - WINDOW).dt.tz_convert(TZ).dt.strftime("%Y-%m")
        end_m = close.dt.tz_convert(TZ).dt.strftime("%Y-%m")
        far = pd.Timestamp.max.tz_localize("UTC")
        until = {m: far if u is None or pd.isna(u) else pd.Timestamp(u).tz_localize("UTC") for m, u in covered.items()}
        valid &= start_m.isin(until.keys()) & end_m.isin(until.keys())
        valid &= close <= pd.to_datetime(end_m.map(until), utc=True).fillna(pd.Timestamp.min.tz_localize("UTC"))
    out["news_count_1d"] = np.where(valid, counts, np.nan)
    out["news_flag_1d"] = np.where(valid, (counts > 0).astype("float64"), np.nan)
    return out


def join_news(store: Store, panel: pd.DataFrame) -> pd.DataFrame:
    """``panel`` plus FEATURE_COLUMNS from `news_articles` (only months marked OK count as covered). Unchanged
    when the table is absent or the panel already carries the columns."""
    if panel is None or panel.empty or all(c in panel.columns for c in FEATURE_COLUMNS):
        return panel
    has = getattr(store, "has_table", None)
    if not callable(has) or not has(TABLE):
        return panel
    syms = sorted(set(panel["symbol"].astype(str)))
    ts = pd.to_datetime(panel["ts"])
    lo = (ts.min() - timedelta(days=3)).tz_convert("UTC") if ts.dt.tz is not None else ts.min() - timedelta(days=3)
    hi = (ts.max() + timedelta(days=2)).tz_convert("UTC") if ts.dt.tz is not None else ts.max() + timedelta(days=2)
    arts = store.read_table(TABLE, "symbol IN (SELECT unnest(?)) AND published_at BETWEEN ? AND ?",
                            [syms, pd.Timestamp(lo).to_pydatetime(), pd.Timestamp(hi).to_pydatetime()])
    meta = store.read_table(META_TABLE)
    covered: dict[str, Any] = {}
    if not meta.empty:
        for r in meta.itertuples():
            if r.status == STATUS_OK:
                covered[r.month] = None
            elif r.status == STATUS_PARTIAL:
                covered[r.month] = getattr(r, "fetched_until", None)
    feats = news_features(arts, panel, covered)
    missing = [c for c in FEATURE_COLUMNS if c not in panel.columns]
    log.info("news_join", symbols=len(syms), articles=len(arts), columns=missing)
    return panel.assign(**{c: feats[c].to_numpy() for c in missing})


__all__ = [
    "TABLE", "META_TABLE", "FEATURE_COLUMNS", "AlpacaNews", "parse_news_page", "month_list", "run_news_ingest",
    "news_features", "join_news",
]
