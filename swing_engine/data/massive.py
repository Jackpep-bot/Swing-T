"""Massive (ex-Polygon) REST bar/reference provider.

Basic (free) plan: EOD bars, 5 calls/min, 2 years of history, active + delisted tickers. Every request goes
through a token bucket (`calls_per_min`, default 5; paid plans raise it with env `MASSIVE_CALLS_PER_MIN` or
`settings.data.massive_calls_per_min`) and immutable raw JSON is cached under `data/raw/massive/` so a re-run
never re-spends quota on history. Auth is a bearer header, never a query parameter, so keys stay out of URLs,
logs and cache keys.

Two bar paths:

* Per-symbol aggregates (`daily_bars`): ``GET /v2/aggs/ticker/{T}/range/1/day/{from}/{to}``, one call per
  symbol. Right for a handful of names (`swing ingest --symbols SPY,AAPL`).
* Grouped daily (`grouped_daily`): ``GET /v2/aggs/grouped/locale/us/market/stocks/{YYYY-MM-DD}`` returns every
  US stock's bar for one session in ONE call (~12.6k tickers on 2026-10-02). Documented result fields:
  ``T`` ticker, ``o``/``h``/``l``/``c`` prices, ``v`` volume, ``vw`` VWAP, ``n`` trade count, ``t`` Unix ms
  marking the END of the aggregate window, ``otc`` (present only when true). Query params: ``adjusted``
  (default true) adjusts for SPLITS only -- dividends are not adjusted -- and ``include_otc`` (default
  false). A holiday or a session not yet published returns ``resultsCount: 0`` and no ``results``. Because
  ``adjusted=true`` reflects the splits known at request time, a day fetched before a later split goes
  stale; `data.ingest` repairs that by refetching split names per symbol.

Reference data: the full ``/v3/reference/tickers`` listing is ~30 pages (minutes on the free tier), so bar
ingest never pages it when symbols are given (`symbol_details` hits ``/v3/reference/tickers/{T}`` per name
instead). The universe uses `universe_reference`: the active common-stock list (``type=CS`` plus ``ADRC``,
and ``ETF`` when ETFs are allowed) paged once and cached on disk for `REFERENCE_CACHE_DAYS`, plus the
recently delisted names of those types (``active=false`` sorted newest delisting first and paged only back to
the window start, so it stays a page or two).
"""
from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterable, Mapping
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
import structlog

from swing_engine.core.config import Secrets, Settings
from swing_engine.core.interfaces import BarProvider
from swing_engine.core.registry import register

from ._common import as_date, empty_bars, normalize_bars, normalize_symbols, session_ts
from ._http import Http, RawCache, default_cache_dir

log = structlog.get_logger(__name__)

MASSIVE_BASE_URL = "https://api.massive.com"
MASSIVE_BASIC_CALLS_PER_MIN = 5
CALLS_PER_MIN_ENV = "MASSIVE_CALLS_PER_MIN"  # paid plans: e.g. 100 (or more) calls/min
CALLS_PER_MIN_SETTING = "massive_calls_per_min"  # optional field on settings.data
TICKERS_PATH = "/v3/reference/tickers"
TICKER_DETAILS_PATH = "/v3/reference/tickers/{ticker}"
AGGS_PATH = "/v2/aggs/ticker/{symbol}/range/1/day/{start}/{end}"
GROUPED_PATH = "/v2/aggs/grouped/locale/us/market/stocks/{day}"
SPLITS_PATH = "/v3/reference/splits"
TICKERS_PAGE_LIMIT = 1000
AGGS_PAGE_LIMIT = 50000
SPLITS_PAGE_LIMIT = 1000
MAX_PAGES = 500  # hard stop against a pagination loop
INACTIVE_REFERENCE_MAX_PAGES = 10  # delisted-name paging budget ("only if cheap"); newest delistings first
STOCKS_MARKET = "stocks"
OK_STATUSES = (None, "OK", "DELAYED")
HTTP_NOT_FOUND = 404

#: reference cache: one JSON file per (type, active) under data/raw/massive/, refreshed after this many days
REFERENCE_CACHE_DAYS = 7
REFERENCE_CACHE_PREFIX = "reference_tickers"
#: ticker types the universe keeps (Massive codes). ADRC = ADR of common stock, matching
#: `data.universe.COMMON_STOCK_TYPES`; preferreds, warrants, rights, units and funds are left out.
REFERENCE_STOCK_TYPES: tuple[str, ...] = ("CS", "ADRC")
REFERENCE_ETF_TYPES: tuple[str, ...] = ("ETF",)

TICKER_COLUMN_MAP = {
    "ticker": "symbol",
    "name": "name",
    "primary_exchange": "exchange",
    "type": "type",
    "active": "active",
    "list_date": "listed_at",
    "delisted_utc": "delisted_at",
}
TICKER_EXTRA_COLUMNS = ["cik", "composite_figi", "share_class_figi", "market", "locale", "currency_name"]
AGG_COLUMN_MAP = {"t": "ts", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume", "vw": "vwap"}
GROUPED_COLUMN_MAP = {"T": "symbol", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume", "vw": "vwap"}


def resolve_calls_per_min(settings: Settings | None = None, env: Mapping[str, str] | None = None) -> float:
    """Plan rate limit: env `MASSIVE_CALLS_PER_MIN`, else `settings.data.massive_calls_per_min` (when that
    field exists), else the Basic plan's 5/min."""
    environ = os.environ if env is None else env
    raw = environ.get(CALLS_PER_MIN_ENV)
    if raw is not None and str(raw).strip():
        value = float(raw)
    else:
        configured = getattr(getattr(settings, "data", None), CALLS_PER_MIN_SETTING, None)
        value = float(configured) if configured is not None else float(MASSIVE_BASIC_CALLS_PER_MIN)
    if value <= 0:
        raise ValueError(f"massive: calls_per_min must be positive, got {value}")
    return value


def _symbols_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Massive ticker records -> the `list_symbols` contract frame (later rows win on duplicate tickers)."""
    if not rows:
        return normalize_symbols(pd.DataFrame())
    df = pd.DataFrame(rows)
    for src in TICKER_COLUMN_MAP:
        if src not in df.columns:
            df[src] = None
    for extra in TICKER_EXTRA_COLUMNS:
        if extra not in df.columns:
            df[extra] = None
    df = df.rename(columns=TICKER_COLUMN_MAP)[list(TICKER_COLUMN_MAP.values()) + TICKER_EXTRA_COLUMNS]
    return normalize_symbols(df)


def _delisted_on(row: Mapping[str, Any]) -> date | None:
    value = row.get("delisted_utc")
    if not value:
        return None
    try:
        return as_date(pd.Timestamp(value))
    except (TypeError, ValueError):
        return None


@register("bar_provider", "massive")
class MassiveProvider(BarProvider):
    name = "massive"

    def __init__(
        self,
        api_key: str,
        *,
        calls_per_min: float = MASSIVE_BASIC_CALLS_PER_MIN,
        base_url: str = MASSIVE_BASE_URL,
        cache_dir: str | Path | None = None,
        client: httpx.Client | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        today: Callable[[], date] = date.today,
        cache_grouped: bool = False,
    ) -> None:
        """`cache_grouped` keeps each grouped-daily response (~1.5 MB/day, ~2 GB for 5 years) under the raw
        cache; off by default because the store's per-day ledger already makes a backfill resumable."""
        if not api_key:
            raise ValueError("massive: api_key is required (MASSIVE_API_KEY)")
        self.base_url = base_url.rstrip("/")
        self.calls_per_min = float(calls_per_min)
        self._today = today
        self._cache_grouped = cache_grouped
        self.http = Http(
            client=client,
            rate_per_min=calls_per_min,
            cache_dir=default_cache_dir(self.name) if cache_dir is None else cache_dir,
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            clock=clock,
            sleep=sleep,
        )

    @classmethod
    def from_settings(cls, settings: Settings, secrets: Secrets) -> MassiveProvider:
        return cls(secrets.massive_api_key or "", calls_per_min=resolve_calls_per_min(settings))

    # ------------------------------------------------------------------ plumbing
    @staticmethod
    def _check(payload: Mapping[str, Any], path: str) -> None:
        status = payload.get("status")
        if status not in OK_STATUSES:
            raise RuntimeError(f"massive: {path} returned status={status!r}: {payload.get('error', '')}")

    def _paginate(
        self,
        path: str,
        params: dict[str, Any],
        *,
        cache_salt: str | None,
        max_pages: int = MAX_PAGES,
        stop: Callable[[list[dict[str, Any]]], bool] | None = None,
    ) -> list[dict[str, Any]]:
        """Follow `next_url` until exhausted, `stop(page_results)` is true, or `max_pages` is reached;
        returns the concatenated `results` lists."""
        url: str | None = f"{self.base_url}{path}"
        query: dict[str, Any] | None = params
        results: list[dict[str, Any]] = []
        for page in range(max_pages):
            cache_key = None if cache_salt is None else RawCache.key(url, query, salt=f"{cache_salt}:{page}")
            payload = self.http.get_json(url, params=query, cache_key=cache_key)
            self._check(payload, path)
            rows = payload.get("results") or []
            results.extend(rows)
            url = payload.get("next_url")
            query = None  # next_url already carries the cursor
            if not url or (stop is not None and stop(rows)):
                break
        else:
            log.warning("massive_pagination_truncated", path=path, pages=max_pages)
        return results

    def _immutable(self, end: date) -> bool:
        return end < self._today()

    # ------------------------------------------------------------------ reference
    def _tickers(self, active: bool) -> list[dict[str, Any]]:
        params = {"market": STOCKS_MARKET, "active": "true" if active else "false", "limit": TICKERS_PAGE_LIMIT, "sort": "ticker"}
        return self._paginate(TICKERS_PATH, params, cache_salt=f"tickers:{self._today().isoformat()}")

    def list_symbols(self, include_delisted: bool = True) -> pd.DataFrame:
        """Every stock-market ticker (all types). Expensive on the Basic plan (dozens of pages): bar ingest
        and the universe use `symbol_details` / `universe_reference` instead."""
        rows = self._tickers(active=True)
        if include_delisted:
            rows += self._tickers(active=False)
        return _symbols_frame(rows)

    def symbol_details(self, symbols: Iterable[str]) -> pd.DataFrame:
        """Reference rows for just these tickers (one ``/v3/reference/tickers/{T}`` call each); unknown or
        delisted tickers (404) are skipped."""
        rows: list[dict[str, Any]] = []
        for sym in sorted({s.upper().strip() for s in symbols if s and s.strip()}):
            url = f"{self.base_url}{TICKER_DETAILS_PATH.format(ticker=sym)}"
            try:
                payload = self.http.get_json(url)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == HTTP_NOT_FOUND:
                    log.info("massive_ticker_details_missing", symbol=sym)
                    continue
                raise
            self._check(payload, TICKER_DETAILS_PATH)
            result = payload.get("results")
            if isinstance(result, dict) and result:
                rows.append(result)
        return _symbols_frame(rows)

    def _reference_cache_key(self, ticker_type: str, active: bool) -> str:
        return f"{REFERENCE_CACHE_PREFIX}_{ticker_type}_{'active' if active else 'inactive'}"

    def _cached_reference(self, key: str, delisted_since: date | None) -> list[dict[str, Any]] | None:
        text = self.http.cache.get(key)
        if text is None:
            return None
        try:
            doc = json.loads(text)
            fetched_on = date.fromisoformat(doc["fetched_on"])
            covered = doc.get("delisted_since")
        except (ValueError, KeyError, TypeError):
            return None
        if (self._today() - fetched_on).days >= REFERENCE_CACHE_DAYS:
            return None
        if delisted_since is not None and covered is not None and date.fromisoformat(covered) > delisted_since:
            return None  # the cached delisting window does not reach back far enough
        return list(doc.get("results") or [])

    def reference_tickers(
        self, ticker_type: str, *, active: bool = True, delisted_since: date | None = None
    ) -> list[dict[str, Any]]:
        """Raw ticker records of one Massive `type` (e.g. ``CS``), paged once and cached on disk for
        `REFERENCE_CACHE_DAYS`. With ``active=False`` the listing is sorted newest delisting first and paging
        stops once a whole page delisted before `delisted_since` (budget `INACTIVE_REFERENCE_MAX_PAGES`)."""
        key = self._reference_cache_key(ticker_type, active)
        since = as_date(delisted_since) if delisted_since is not None and not active else None
        cached = self._cached_reference(key, since)
        if cached is not None:
            return cached
        params: dict[str, Any] = {"market": STOCKS_MARKET, "type": ticker_type, "limit": TICKERS_PAGE_LIMIT}
        if active:
            params.update(active="true", sort="ticker", order="asc")
            rows = self._paginate(TICKERS_PATH, params, cache_salt=None)
        else:
            params.update(active="false", sort="delisted_utc", order="desc")

            def older_than_window(page: list[dict[str, Any]]) -> bool:
                if since is None:
                    return False
                dates = [_delisted_on(r) for r in page]
                return bool(dates) and all(d is not None and d < since for d in dates)

            rows = self._paginate(
                TICKERS_PATH, params, cache_salt=None, max_pages=INACTIVE_REFERENCE_MAX_PAGES, stop=older_than_window
            )
            if since is not None:
                rows = [r for r in rows if (_delisted_on(r) or since) >= since]
        doc = {
            "fetched_on": self._today().isoformat(),
            "type": ticker_type,
            "active": active,
            "delisted_since": since.isoformat() if since is not None else None,
            "results": rows,
        }
        self.http.cache.put(key, json.dumps(doc))
        log.info("massive_reference_fetched", type=ticker_type, active=active, rows=len(rows))
        return rows

    def universe_reference(self, include_etfs: bool = False, delisted_since: date | None = None) -> pd.DataFrame:
        """Reference rows the universe may keep: active common stock (+ ADRs, + ETFs when `include_etfs`),
        plus names of those types delisted on/after `delisted_since` (none when it is None). Active rows win
        when a ticker was reused after an older delisting."""
        types = REFERENCE_STOCK_TYPES + (REFERENCE_ETF_TYPES if include_etfs else ())
        inactive: list[dict[str, Any]] = []
        if delisted_since is not None:
            for kind in types:
                inactive += self.reference_tickers(kind, active=False, delisted_since=as_date(delisted_since))
        active: list[dict[str, Any]] = []
        for kind in types:
            active += self.reference_tickers(kind, active=True)
        return _symbols_frame(inactive + active)

    def splits(self, symbol: str | None = None, since: date | None = None) -> pd.DataFrame:
        params: dict[str, Any] = {"limit": SPLITS_PAGE_LIMIT, "sort": "execution_date", "order": "asc"}
        if symbol:
            params["ticker"] = symbol.upper()
        if since:
            params["execution_date.gte"] = as_date(since).isoformat()
        rows = self._paginate(SPLITS_PATH, params, cache_salt=f"splits:{self._today().isoformat()}")
        cols = ["symbol", "ex_date", "split_from", "split_to", "ratio"]
        if not rows:
            return pd.DataFrame(columns=cols)
        df = pd.DataFrame(rows).rename(columns={"ticker": "symbol", "execution_date": "ex_date"})
        df["ex_date"] = pd.to_datetime(df["ex_date"]).dt.date
        df["ratio"] = df["split_to"].astype(float) / df["split_from"].astype(float)
        return df[cols].sort_values(["symbol", "ex_date"]).reset_index(drop=True)

    # ------------------------------------------------------------------ bars
    def _symbol_bars(self, symbol: str, start: date, end: date, *, use_cache: bool = True) -> pd.DataFrame:
        path = AGGS_PATH.format(symbol=symbol, start=start.isoformat(), end=end.isoformat())
        params = {"adjusted": "true", "sort": "asc", "limit": AGGS_PAGE_LIMIT}
        salt = "aggs" if use_cache and self._immutable(end) else None
        rows = self._paginate(path, params, cache_salt=salt)
        if not rows:
            return empty_bars()
        df = pd.DataFrame(rows)
        for src in AGG_COLUMN_MAP:
            if src not in df.columns:
                df[src] = None
        df = df.rename(columns=AGG_COLUMN_MAP)
        df["symbol"] = symbol
        df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
        df["adj_close"] = df["close"]  # adjusted=true already split-adjusts OHLC
        return df

    def daily_bars(self, symbols: Iterable[str], start: date, end: date, *, use_cache: bool = True) -> pd.DataFrame:
        """Per-symbol aggregates. `use_cache=False` bypasses the raw cache (split repair: a cached adjusted
        series is stale once a later split lands)."""
        start_d, end_d = as_date(start), as_date(end)
        frames = []
        for sym in sorted({s.upper() for s in symbols}):
            try:
                frames.append(self._symbol_bars(sym, start_d, end_d, use_cache=use_cache))
            except httpx.HTTPStatusError as exc:
                log.error("massive_bars_failed", symbol=sym, status=exc.response.status_code)
                raise
        frames = [f for f in frames if not f.empty]
        if not frames:
            return empty_bars()
        return normalize_bars(pd.concat(frames, ignore_index=True))

    def grouped_daily(self, day: date | str, *, include_otc: bool = False) -> pd.DataFrame:
        """Every US stock's split-adjusted bar for one session, in one call, as long-format contract bars
        (``ts`` = the requested session at midnight New York; Massive's ``t`` marks the window end).
        Empty for holidays and sessions not yet published; empties are never cached."""
        d = as_date(day)
        url = f"{self.base_url}{GROUPED_PATH.format(day=d.isoformat())}"
        params = {"adjusted": "true", "include_otc": "true" if include_otc else "false"}
        cache_key = RawCache.key(url, params, salt="grouped") if self._cache_grouped and self._immutable(d) else None
        text = self.http.cache.get(cache_key) if cache_key is not None else None
        payload = json.loads(text) if text is not None else self.http.get_json(url, params=params)
        self._check(payload, GROUPED_PATH)
        rows = payload.get("results") or []
        if not rows:
            return empty_bars()
        if cache_key is not None and text is None:
            self.http.cache.put(cache_key, json.dumps(payload))
        df = pd.DataFrame(rows)
        for src in GROUPED_COLUMN_MAP:
            if src not in df.columns:
                df[src] = None
        df = df.rename(columns=GROUPED_COLUMN_MAP)
        df = df[df["symbol"].notna()]
        df["ts"] = session_ts(d)
        df["adj_close"] = df["close"]  # adjusted=true already split-adjusts OHLC
        return normalize_bars(df)
