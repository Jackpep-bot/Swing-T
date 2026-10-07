"""Massive (ex-Polygon) REST bar/reference provider.

Basic plan: EOD bars, 5 calls/min, 2 years of history, active + delisted tickers. Every request goes
through a token bucket (`calls_per_min`, default 5) and raw JSON pages are cached under
`data/raw/massive/` so a re-run never re-spends quota on immutable history. Auth is a bearer header,
never a query parameter, so keys stay out of URLs, logs and cache keys.
"""
from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
import structlog

from swing_engine.core.config import Secrets, Settings
from swing_engine.core.interfaces import BarProvider
from swing_engine.core.registry import register

from ._common import as_date, empty_bars, normalize_bars, normalize_symbols
from ._http import Http, RawCache, default_cache_dir

log = structlog.get_logger(__name__)

MASSIVE_BASE_URL = "https://api.massive.com"
MASSIVE_BASIC_CALLS_PER_MIN = 5
TICKERS_PATH = "/v3/reference/tickers"
AGGS_PATH = "/v2/aggs/ticker/{symbol}/range/1/day/{start}/{end}"
SPLITS_PATH = "/v3/reference/splits"
TICKERS_PAGE_LIMIT = 1000
AGGS_PAGE_LIMIT = 50000
SPLITS_PAGE_LIMIT = 1000
MAX_PAGES = 500  # hard stop against a pagination loop
STOCKS_MARKET = "stocks"

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
    ) -> None:
        if not api_key:
            raise ValueError("massive: api_key is required (MASSIVE_API_KEY)")
        self.base_url = base_url.rstrip("/")
        self._today = today
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
        return cls(secrets.massive_api_key or "")

    # ------------------------------------------------------------------ plumbing
    def _paginate(self, path: str, params: dict[str, Any], *, cache_salt: str | None) -> list[dict[str, Any]]:
        """Follow `next_url` until exhausted; returns the concatenated `results` lists."""
        url: str | None = f"{self.base_url}{path}"
        query: dict[str, Any] | None = params
        results: list[dict[str, Any]] = []
        for page in range(MAX_PAGES):
            cache_key = None if cache_salt is None else RawCache.key(url, query, salt=f"{cache_salt}:{page}")
            payload = self.http.get_json(url, params=query, cache_key=cache_key)
            status = payload.get("status")
            if status not in (None, "OK", "DELAYED"):
                raise RuntimeError(f"massive: {path} returned status={status!r}: {payload.get('error', '')}")
            results.extend(payload.get("results") or [])
            url = payload.get("next_url")
            query = None  # next_url already carries the cursor
            if not url:
                break
        else:  # pragma: no cover
            log.warning("massive_pagination_truncated", path=path, pages=MAX_PAGES)
        return results

    def _immutable(self, end: date) -> bool:
        return end < self._today()

    # ------------------------------------------------------------------ reference
    def _tickers(self, active: bool) -> list[dict[str, Any]]:
        params = {"market": STOCKS_MARKET, "active": "true" if active else "false", "limit": TICKERS_PAGE_LIMIT, "sort": "ticker"}
        return self._paginate(TICKERS_PATH, params, cache_salt=f"tickers:{self._today().isoformat()}")

    def list_symbols(self, include_delisted: bool = True) -> pd.DataFrame:
        rows = self._tickers(active=True)
        if include_delisted:
            rows += self._tickers(active=False)
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
    def _symbol_bars(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        path = AGGS_PATH.format(symbol=symbol, start=start.isoformat(), end=end.isoformat())
        params = {"adjusted": "true", "sort": "asc", "limit": AGGS_PAGE_LIMIT}
        rows = self._paginate(path, params, cache_salt="aggs" if self._immutable(end) else None)
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

    def daily_bars(self, symbols: Iterable[str], start: date, end: date) -> pd.DataFrame:
        start_d, end_d = as_date(start), as_date(end)
        frames = []
        for sym in sorted({s.upper() for s in symbols}):
            try:
                frames.append(self._symbol_bars(sym, start_d, end_d))
            except httpx.HTTPStatusError as exc:
                log.error("massive_bars_failed", symbol=sym, status=exc.response.status_code)
                raise
        frames = [f for f in frames if not f.empty]
        if not frames:
            return empty_bars()
        return normalize_bars(pd.concat(frames, ignore_index=True))
