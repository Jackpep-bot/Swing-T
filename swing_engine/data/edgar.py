"""SEC EDGAR: current-filings Atom feed (feedparser), Form 4 open-market buys (edgartools, guarded), the
company_tickers.json symbol map, and the data.sec.gov submissions / XBRL companyfacts JSON that feed the
point-in-time earnings-date and fundamentals tables (`data.fundamentals`, catalog slug
`earnings_dates_point_in_time`, docs/catalog/catalog.json). SEC fair-access policy: 10 requests/second and a User-Agent with
contact details, which `Edgar(user_agent)` sends on every call.

Point-in-time: every row is stamped with the filing's acceptance/filing time, never a transaction date.
"""
from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterable
from datetime import date
from pathlib import Path
from typing import Any

import feedparser
import httpx
import pandas as pd
import structlog

from ._common import TZ, as_date
from ._http import Http
from .calendar import next_trading_day, session_bounds

log = structlog.get_logger(__name__)

SEC_BASE_URL = "https://www.sec.gov"
EDGAR_CURRENT_PATH = "/cgi-bin/browse-edgar"
COMPANY_TICKERS_PATH = "/files/company_tickers.json"
EDGAR_CALLS_PER_MIN = 600  # fair-access policy: 10 req/s
EDGAR_BURST = 10
EDGAR_MAX_COUNT = 100  # the Atom feed serves at most 100 entries per page
FORM4_BUY_CODE = "P"
FORM4_ACQUIRED_CODE = "A"
FORM4_FORM = "4"
CIK_WIDTH = 10

_TITLE_RE = re.compile(r"^(?P<form>.+?) - (?P<company>.+?) \((?P<cik>\d+)\) \((?P<role>[^)]*)\)\s*$")
_ACCESSION_RE = re.compile(r"accession-number=(?P<acc>[\d-]+)")

CURRENT_COLUMNS = ["accession", "form_type", "company", "cik", "role", "filed_at", "title", "url", "summary"]
FORM4_COLUMNS = [
    "symbol", "cik", "company", "insider", "insider_title", "transaction_date", "filed_at",
    "shares", "price", "value", "accession", "url",
]
COMPANY_TICKER_COLUMNS = ["cik", "symbol", "name"]

# ---- data.sec.gov: submissions (8-K item 2.02 earnings dates) and XBRL companyfacts -----------------------------
SEC_DATA_BASE_URL = "https://data.sec.gov"
SUBMISSIONS_PATH = "/submissions/CIK{cik}.json"
SUBMISSIONS_PAGE_PATH = "/submissions/{name}"  # older filings pages listed under filings.files
COMPANYFACTS_PATH = "/api/xbrl/companyfacts/CIK{cik}.json"
HTTP_NOT_FOUND = 404
EARNINGS_ITEM = "2.02"  # 8-K Item 2.02 "Results of Operations and Financial Condition"
EARNINGS_FORMS: frozenset[str] = frozenset({"8-K"})  # 8-K/A amendments are not new announcements
ITEMS_SEPARATOR = ","
#: submissions JSON `acceptanceDateTime` carries a trailing "Z" but the wall-clock is US Eastern (EDGAR quirk).
#: Reading it as Eastern is also the conservative choice: if it were real UTC, an Eastern reading only moves the
#: timestamp later (never maps an after-close filing into the same session).
ACCEPTANCE_TZ = TZ
EARNINGS_COLUMNS = ["symbol", "cik", "accepted_at", "filing_date", "accession", "form", "session"]


def earnings_session(accepted_at: Any) -> date:
    """The first session whose close can react to an 8-K accepted at `accepted_at` (Eastern): that day when the
    filing lands before the session close (pre-market or intraday), else the next session (after 16:00 ET, or
    after an early close, or on a weekend/holiday)."""
    ts = pd.Timestamp(accepted_at)
    ts = ts.tz_localize(TZ) if ts.tzinfo is None else ts.tz_convert(TZ)
    d = ts.date()
    bounds = session_bounds(d)
    if bounds is not None and ts < bounds[1]:
        return d
    return next_trading_day(d)


def _acceptance_ts(value: Any) -> pd.Timestamp:
    text = str(value or "").strip()
    if not text:
        return pd.NaT
    ts = pd.to_datetime(text.rstrip("Zz"), errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    return ts.tz_convert(ACCEPTANCE_TZ) if ts.tzinfo is not None else ts.tz_localize(ACCEPTANCE_TZ)


def _filings_block(payload: dict[str, Any]) -> dict[str, Any]:
    """The columnar filings block of a submissions document (`filings.recent`) or of an older page (top level)."""
    filings = payload.get("filings")
    if isinstance(filings, dict) and isinstance(filings.get("recent"), dict):
        return filings["recent"]
    return payload


def _cell(block: dict[str, Any], key: str, i: int) -> Any:
    col = block.get(key)
    return col[i] if isinstance(col, list) and i < len(col) else None


def parse_submissions(payload: dict[str, Any], symbols: Iterable[str], cik: str | None = None) -> pd.DataFrame:
    """8-K filings with Item 2.02 from one submissions document/page, one row per (symbol, accession), stamped
    with the acceptance datetime (Eastern) and the session that first reacts to it. Never the period date."""
    block = _filings_block(payload)
    forms = block.get("form") or []
    cik_s = str(cik if cik is not None else payload.get("cik", "")).zfill(CIK_WIDTH)
    syms = sorted({s.upper().strip() for s in symbols if s})
    rows: list[dict[str, Any]] = []
    for i, form in enumerate(forms):
        if str(form) not in EARNINGS_FORMS:
            continue
        items = [t.strip() for t in str(_cell(block, "items", i) or "").split(ITEMS_SEPARATOR)]
        if EARNINGS_ITEM not in items:
            continue
        accepted = _acceptance_ts(_cell(block, "acceptanceDateTime", i))
        if pd.isna(accepted):
            continue
        filing_date = pd.to_datetime(_cell(block, "filingDate", i), errors="coerce")
        accession = _cell(block, "accessionNumber", i)
        for sym in syms:
            rows.append(
                {
                    "symbol": sym,
                    "cik": cik_s,
                    "accepted_at": accepted,
                    "filing_date": filing_date.date() if pd.notna(filing_date) else None,
                    "accession": accession,
                    "form": str(form),
                    "session": earnings_session(accepted),
                }
            )
    df = pd.DataFrame(rows, columns=EARNINGS_COLUMNS)
    if df.empty:
        return df
    df["accepted_at"] = pd.to_datetime(df["accepted_at"], utc=True).dt.tz_convert(TZ)
    return df.sort_values(["symbol", "accepted_at"], kind="mergesort").reset_index(drop=True)

# edgartools' DataFrame column names have shifted between releases; look for any of these
_CODE_CANDIDATES = ("Code", "TransactionCode", "transaction_code", "code")
_AD_CANDIDATES = ("AcquiredDisposed", "acquired_disposed", "AD", "acquiredDisposed")
_SHARES_CANDIDATES = ("Shares", "shares", "TransactionShares")
_PRICE_CANDIDATES = ("Price", "price", "TransactionPrice")
_DATE_CANDIDATES = ("Date", "date", "TransactionDate", "transaction_date")


def _pick(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    cols = list(columns)
    for c in candidates:
        if c in cols:
            return c
    return None


class Edgar:
    def __init__(
        self,
        user_agent: str,
        *,
        base_url: str = SEC_BASE_URL,
        data_base_url: str = SEC_DATA_BASE_URL,
        client: httpx.Client | None = None,
        calls_per_min: float = EDGAR_CALLS_PER_MIN,
        cache_dir: str | Path | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not user_agent or "@" not in user_agent:
            raise ValueError("edgar: user_agent must include a contact email (SEC fair-access policy)")
        self.user_agent = user_agent
        self.base_url = base_url.rstrip("/")
        self.data_base_url = data_base_url.rstrip("/")
        self.http = Http(
            client=client,
            rate_per_min=calls_per_min,
            burst=EDGAR_BURST,
            cache_dir=cache_dir if cache_dir is not None else None,
            headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
            clock=clock,
            sleep=sleep,
        )

    # ------------------------------------------------------------------ current filings (Atom)
    @staticmethod
    def parse_current_atom(text: str) -> pd.DataFrame:
        feed = feedparser.parse(text)
        rows = []
        for e in feed.entries:
            title = e.get("title", "")
            m = _TITLE_RE.match(title)
            acc = None
            am = _ACCESSION_RE.search(e.get("id", ""))
            if am:
                acc = am.group("acc")
            tags = [t.get("term") for t in e.get("tags", [])]
            form_type = (m.group("form") if m else None) or (tags[0] if tags else None)
            filed_at = pd.to_datetime(e.get("updated"), utc=True, errors="coerce")
            rows.append(
                {
                    "accession": acc,
                    "form_type": form_type,
                    "company": m.group("company") if m else title,
                    "cik": m.group("cik").zfill(CIK_WIDTH) if m else None,
                    "role": m.group("role") if m else None,
                    "filed_at": filed_at.tz_convert(TZ) if pd.notna(filed_at) else pd.NaT,
                    "title": title,
                    "url": e.get("link"),
                    "summary": e.get("summary", ""),
                }
            )
        df = pd.DataFrame(rows, columns=CURRENT_COLUMNS)
        if df.empty:
            return df
        df["filed_at"] = pd.to_datetime(df["filed_at"], utc=True).dt.tz_convert(TZ)
        return df.drop_duplicates(subset=["accession"]).sort_values("filed_at", ascending=False).reset_index(drop=True)

    def current_filings(self, form_types: Iterable[str] | str | None = None, count: int = EDGAR_MAX_COUNT) -> pd.DataFrame:
        """Latest filings from the EDGAR current-events Atom feed, one request per form type."""
        if isinstance(form_types, str):
            types: list[str | None] = [form_types]
        else:
            types = list(form_types) if form_types else [None]
        count = max(1, min(int(count), EDGAR_MAX_COUNT))
        frames = []
        for ft in types:
            params: dict[str, Any] = {"action": "getcurrent", "count": count, "output": "atom", "owner": "include"}
            if ft:
                params["type"] = ft
            text = self.http.get_text(f"{self.base_url}{EDGAR_CURRENT_PATH}", params=params)
            frames.append(self.parse_current_atom(text))
        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=CURRENT_COLUMNS)
        if df.empty:
            return df
        return df.drop_duplicates(subset=["accession"]).sort_values("filed_at", ascending=False).reset_index(drop=True)

    # ------------------------------------------------------------------ Form 4 buys (edgartools)
    def _fetch_form4_filings(self, since: date, until: date) -> list[Any]:
        """edgartools filings for form 4 in [since, until]. Isolated so tests can stub it."""
        import edgar as edgartools

        edgartools.set_identity(self.user_agent)
        filings = edgartools.get_filings(form=FORM4_FORM, filing_date=f"{since.isoformat()}:{until.isoformat()}")
        return list(filings) if filings is not None else []

    @staticmethod
    def _extract_buys(form4: Any, filing: Any) -> list[dict[str, Any]]:
        trades = getattr(form4, "market_trades", None)
        if trades is None or not isinstance(trades, pd.DataFrame) or trades.empty:
            return []
        code_col = _pick(trades.columns, _CODE_CANDIDATES)
        ad_col = _pick(trades.columns, _AD_CANDIDATES)
        shares_col = _pick(trades.columns, _SHARES_CANDIDATES)
        price_col = _pick(trades.columns, _PRICE_CANDIDATES)
        date_col = _pick(trades.columns, _DATE_CANDIDATES)
        if code_col is None or shares_col is None:
            return []
        buys = trades[trades[code_col].astype(str).str.upper() == FORM4_BUY_CODE]
        if ad_col is not None:
            buys = buys[buys[ad_col].astype(str).str.upper().str.startswith(FORM4_ACQUIRED_CODE)]
        filed_at = pd.to_datetime(getattr(filing, "filing_date", None))
        rows = []
        for _, t in buys.iterrows():
            shares = pd.to_numeric(t.get(shares_col), errors="coerce")
            price = pd.to_numeric(t.get(price_col), errors="coerce") if price_col else float("nan")
            rows.append(
                {
                    "symbol": getattr(filing, "ticker", None) or getattr(form4, "ticker", None),
                    "cik": str(getattr(filing, "cik", "") or "").zfill(CIK_WIDTH),
                    "company": getattr(filing, "company", None),
                    "insider": getattr(form4, "insider_name", None),
                    "insider_title": str(getattr(form4, "position", "") or ""),
                    "transaction_date": pd.to_datetime(t.get(date_col), errors="coerce") if date_col else pd.NaT,
                    "filed_at": filed_at,
                    "shares": float(shares) if pd.notna(shares) else float("nan"),
                    "price": float(price) if pd.notna(price) else float("nan"),
                    "value": float(shares * price) if pd.notna(shares) and pd.notna(price) else float("nan"),
                    "accession": getattr(filing, "accession_number", None) or getattr(filing, "accession_no", None),
                    "url": getattr(filing, "homepage_url", None) or getattr(filing, "filing_url", None),
                }
            )
        return rows

    def form4_buys(self, since: date | str, until: date | str | None = None) -> pd.DataFrame:
        """Open-market insider purchases (code P, acquired) filed in [since, until]. Returns an empty
        frame (and logs) if edgartools is unavailable or the network call fails."""
        since_d = as_date(since)
        until_d = as_date(until) if until is not None else date.today()
        try:
            filings = self._fetch_form4_filings(since_d, until_d)
        except Exception as exc:
            log.warning("edgar_form4_unavailable", error=str(exc))
            return pd.DataFrame(columns=FORM4_COLUMNS)
        rows: list[dict[str, Any]] = []
        for filing in filings:
            try:
                form4 = filing.obj()
                rows.extend(self._extract_buys(form4, filing))
            except Exception as exc:
                log.debug("edgar_form4_parse_failed", accession=getattr(filing, "accession_number", None), error=str(exc))
                continue
        df = pd.DataFrame(rows, columns=FORM4_COLUMNS)
        if df.empty:
            return df
        df["filed_at"] = pd.to_datetime(df["filed_at"], errors="coerce")
        df["symbol"] = df["symbol"].astype("str").str.upper()
        return df.sort_values(["filed_at", "symbol", "transaction_date"], kind="mergesort").reset_index(drop=True)

    # ------------------------------------------------------------------ company tickers
    def company_tickers(self) -> pd.DataFrame:
        payload = self.http.get_json(f"{self.base_url}{COMPANY_TICKERS_PATH}")
        rows = payload.values() if isinstance(payload, dict) else payload
        df = pd.DataFrame(
            [{"cik": str(r["cik_str"]).zfill(CIK_WIDTH), "symbol": str(r["ticker"]).upper(), "name": r["title"]} for r in rows],
            columns=COMPANY_TICKER_COLUMNS,
        )
        return df.sort_values("symbol").reset_index(drop=True)

    # ------------------------------------------------------------------ data.sec.gov JSON
    def _data_json(self, path: str) -> dict[str, Any] | None:
        """GET a data.sec.gov JSON document through the shared fair-access bucket; None on 404."""
        try:
            return self.http.get_json(f"{self.data_base_url}{path}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == HTTP_NOT_FOUND:
                log.info("edgar_data_missing", path=path)
                return None
            raise

    def submissions(self, cik: str, *, include_older: bool = True) -> list[dict[str, Any]]:
        """The submissions document for `cik` plus (with `include_older`) every older page it lists under
        `filings.files`. Empty list when the CIK is unknown."""
        first = self._data_json(SUBMISSIONS_PATH.format(cik=str(cik).zfill(CIK_WIDTH)))
        if first is None:
            return []
        pages = [first]
        if include_older:
            for f in (first.get("filings") or {}).get("files") or []:
                name = f.get("name") if isinstance(f, dict) else None
                if name:
                    page = self._data_json(SUBMISSIONS_PAGE_PATH.format(name=name))
                    if page is not None:
                        pages.append(page)
        return pages

    def earnings_dates(self, cik: str, symbols: Iterable[str], *, include_older: bool = True) -> pd.DataFrame:
        """Point-in-time earnings announcements (8-K Item 2.02) for `cik`, one row per symbol sharing the CIK."""
        syms = list(symbols)
        frames = [parse_submissions(p, syms, cik) for p in self.submissions(cik, include_older=include_older)]
        frames = [f for f in frames if not f.empty]
        if not frames:
            return pd.DataFrame(columns=EARNINGS_COLUMNS)
        df = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["symbol", "accession"])
        return df.sort_values(["symbol", "accepted_at"], kind="mergesort").reset_index(drop=True)

    def companyfacts(self, cik: str) -> dict[str, Any] | None:
        """Raw XBRL companyfacts payload for `cik`; None when the filer has no XBRL facts (404)."""
        return self._data_json(COMPANYFACTS_PATH.format(cik=str(cik).zfill(CIK_WIDTH)))


__all__ = [
    "Edgar", "FORM4_COLUMNS", "CURRENT_COLUMNS", "COMPANY_TICKER_COLUMNS", "EARNINGS_COLUMNS", "earnings_session",
    "parse_submissions",
]
