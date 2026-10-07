"""Quiver Quantitative REST client: insider (Form 4) and congressional trades with point-in-time stamps.

Signals must be timestamped on when the record became public (`filed_at` / `uploaded_at`), never on the
transaction date, and the vendor's `ExcessReturn` / `PriceChange` / `SPYChange` columns embed future
returns, so they are dropped at the door. `pit_ts` is the earliest instant a backtest may see a row.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
import structlog

from ._common import TZ, as_date
from ._http import Http, default_cache_dir

log = structlog.get_logger(__name__)

QUIVER_BASE_URL = "https://api.quiverquant.com"
INSIDERS_PATH = "/beta/live/insiders"
CONGRESS_LIVE_PATH = "/beta/live/congresstrading"
CONGRESS_TICKER_PATH = "/beta/historical/congresstrading/{ticker}"
QUIVER_DEFAULT_CALLS_PER_MIN = 30  # limits are tiered and unpublished; stay conservative
QUIVER_PAGE_SIZE = 500
QUIVER_MAX_PAGES = 200
DEFAULT_AUTH_SCHEME = "Bearer"  # the OpenAPI spec says bearer; Quiver's own client sends "Token"

LOOKAHEAD_COLUMNS = frozenset({"ExcessReturn", "PriceChange", "SPYChange", "excess_return", "price_change", "spy_change"})

INSIDER_COLUMN_MAP = {
    "Ticker": "symbol",
    "Date": "transaction_date",
    "Name": "insider",
    "AcquiredDisposedCode": "acquired_disposed",
    "TransactionCode": "transaction_code",
    "Shares": "shares",
    "PricePerShare": "price",
    "SharesOwnedFollowing": "shares_owned_following",
    "fileDate": "filed_at",
    "uploaded": "uploaded_at",
    "officerTitle": "officer_title",
    "isDirector": "is_director",
    "isOfficer": "is_officer",
    "isTenPercentOwner": "is_ten_percent_owner",
    "directOrIndirectOwnership": "ownership",
}
INSIDER_COLUMNS = list(INSIDER_COLUMN_MAP.values()) + ["pit_ts"]
CONGRESS_COLUMN_MAP = {
    "Ticker": "symbol",
    "Representative": "representative",
    "BioGuideID": "bioguide_id",
    "House": "chamber",
    "Chamber": "chamber",
    "Party": "party",
    "District": "district",
    "Transaction": "transaction",
    "Range": "range",
    "Amount": "amount_low",
    "Trade_Size_USD": "trade_size_usd",
    "TransactionDate": "transaction_date",
    "Traded": "transaction_date",
    "ReportDate": "report_date",
    "Filed": "report_date",
    "Quiver_Upload_Time": "uploaded_at",
    "last_modified": "last_modified",
    "TickerType": "ticker_type",
    "Description": "description",
}
CONGRESS_COLUMNS = [
    "symbol", "representative", "bioguide_id", "chamber", "party", "district", "transaction", "range",
    "amount_low", "trade_size_usd", "transaction_date", "report_date", "uploaded_at", "last_modified",
    "ticker_type", "description", "pit_ts",
]


def _to_ts(values: pd.Series) -> pd.Series:
    """Instants (ISO timestamps with offsets) as tz-aware America/New_York."""
    parsed = pd.to_datetime(values, errors="coerce", utc=True, format="mixed")
    return parsed.dt.tz_convert(TZ)


def _to_date(values: pd.Series) -> pd.Series:
    """Calendar dates (``YYYY-MM-DD`` or midnight-UTC stamps) as `date` objects, None when missing."""
    parsed = pd.to_datetime(values, errors="coerce", utc=True, format="mixed")
    return parsed.dt.date.where(parsed.notna(), None).astype("object")


def _date_to_session_ts(dates: pd.Series) -> pd.Series:
    """A date becomes visible at its New York midnight (the earliest a nightly job could see it)."""
    return pd.to_datetime(dates, errors="coerce").dt.tz_localize(TZ)


def _rename(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """Rename vendor columns, folding aliases (first alias present wins) and dropping look-ahead fields."""
    out = pd.DataFrame(index=df.index)
    for src, dst in mapping.items():
        if src in df.columns and dst not in out.columns:
            out[dst] = df[src]
    for c in df.columns:
        if c not in mapping and c not in LOOKAHEAD_COLUMNS and c not in out.columns:
            out[c] = df[c]
    return out


class Quiver:
    def __init__(
        self,
        key: str,
        *,
        auth_scheme: str = DEFAULT_AUTH_SCHEME,
        base_url: str = QUIVER_BASE_URL,
        calls_per_min: float = QUIVER_DEFAULT_CALLS_PER_MIN,
        page_size: int = QUIVER_PAGE_SIZE,
        client: httpx.Client | None = None,
        cache_dir: str | Path | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not key:
            raise ValueError("quiver: api key is required (QUIVER_API_KEY)")
        self.base_url = base_url.rstrip("/")
        self.page_size = page_size
        self.http = Http(
            client=client,
            rate_per_min=calls_per_min,
            cache_dir=default_cache_dir("quiver") if cache_dir is None else cache_dir,
            headers={"Authorization": f"{auth_scheme} {key}", "Accept": "application/json"},
            clock=clock,
            sleep=sleep,
        )

    def _get_pages(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        url = f"{self.base_url}{path}"
        rows: list[dict[str, Any]] = []
        for page in range(1, QUIVER_MAX_PAGES + 1):
            payload = self.http.get_json(url, params={**params, "page": page, "page_size": self.page_size})
            batch = payload.get("results", payload) if isinstance(payload, dict) else payload
            if not batch:
                break
            rows.extend(batch)
            if len(batch) < self.page_size:
                break
        return rows

    # ------------------------------------------------------------------ insiders
    def insiders(
        self,
        ticker: str | None = None,
        since: date | str | None = None,
        *,
        uploaded_since: date | str | None = None,
        buys_only: bool = False,
    ) -> pd.DataFrame:
        params: dict[str, Any] = {}
        if ticker:
            params["ticker"] = ticker.upper()
        if since:
            params["date"] = as_date(since).isoformat()
        if uploaded_since:
            params["uploaded"] = as_date(uploaded_since).isoformat()
        rows = self._get_pages(INSIDERS_PATH, params)
        return self.normalize_insiders(pd.DataFrame(rows), buys_only=buys_only)

    @staticmethod
    def normalize_insiders(raw: pd.DataFrame, *, buys_only: bool = False) -> pd.DataFrame:
        if raw.empty:
            return pd.DataFrame(columns=INSIDER_COLUMNS)
        df = _rename(raw, INSIDER_COLUMN_MAP)
        for c in INSIDER_COLUMN_MAP.values():
            if c not in df.columns:
                df[c] = None
        df["symbol"] = df["symbol"].astype("str").str.upper()
        df["transaction_date"] = _to_date(df["transaction_date"])
        df["filed_at"] = _to_ts(df["filed_at"])
        df["uploaded_at"] = _to_ts(df["uploaded_at"])
        for c in ("shares", "price", "shares_owned_following"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["pit_ts"] = df[["filed_at", "uploaded_at"]].max(axis=1)
        dropped = int(df["pit_ts"].isna().sum())
        if dropped:
            log.warning("quiver_insiders_rows_without_pit_ts_dropped", rows=dropped)
        df = df[df["pit_ts"].notna()]
        if buys_only:
            df = df[(df["transaction_code"].astype(str).str.upper() == "P") & (df["acquired_disposed"].astype(str).str.upper() == "A")]
        extras = [c for c in df.columns if c not in INSIDER_COLUMNS]
        return df[INSIDER_COLUMNS + extras].sort_values(["pit_ts", "symbol"]).reset_index(drop=True)

    # ------------------------------------------------------------------ congress
    def congress(self, ticker: str | None = None, since: date | str | None = None) -> pd.DataFrame:
        if ticker:
            rows = self._get_pages(CONGRESS_TICKER_PATH.format(ticker=ticker.upper()), {})
        else:
            rows = self._get_pages(CONGRESS_LIVE_PATH, {})
        df = self.normalize_congress(pd.DataFrame(rows))
        if since is not None and not df.empty:
            df = df[df["pit_ts"] >= pd.Timestamp(as_date(since)).tz_localize(TZ)].reset_index(drop=True)
        return df

    @staticmethod
    def normalize_congress(raw: pd.DataFrame) -> pd.DataFrame:
        if raw.empty:
            return pd.DataFrame(columns=CONGRESS_COLUMNS)
        df = _rename(raw, CONGRESS_COLUMN_MAP)
        for c in CONGRESS_COLUMNS:
            if c not in df.columns:
                df[c] = None
        df["symbol"] = df["symbol"].astype("str").str.upper()
        df["transaction_date"] = _to_date(df["transaction_date"])
        df["report_date"] = _to_date(df["report_date"])
        df["uploaded_at"] = _to_ts(df["uploaded_at"])
        df["last_modified"] = _to_ts(df["last_modified"])
        df["amount_low"] = pd.to_numeric(df["amount_low"], errors="coerce")
        df["trade_size_usd"] = pd.to_numeric(df["trade_size_usd"], errors="coerce")
        report_ts = _date_to_session_ts(df["report_date"])
        df["pit_ts"] = pd.concat([report_ts, df["uploaded_at"]], axis=1).max(axis=1)
        dropped = int(df["pit_ts"].isna().sum())
        if dropped:
            log.warning("quiver_congress_rows_without_report_date_dropped", rows=dropped)
        df = df[df["pit_ts"].notna()]
        extras = [c for c in df.columns if c not in CONGRESS_COLUMNS]
        return df[CONGRESS_COLUMNS + extras].sort_values(["pit_ts", "symbol"]).reset_index(drop=True)
