"""EODHD bar provider (EOD All World plan): daily bars plus the `delisted=1` symbol list that makes a
survivorship-bias-free universe possible. EODHD returns raw OHLC and a split+dividend `adjusted_close`;
OHLC are scaled by `adjusted_close / close` so prices are continuous across splits (this also folds
dividends in, a small bias documented here on purpose).
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

EODHD_BASE_URL = "https://eodhd.com/api"
EODHD_EXCHANGE = "US"
EODHD_DEFAULT_CALLS_PER_MIN = 60
EOD_PATH = "/eod/{symbol}.{exchange}"
SYMBOL_LIST_PATH = "/exchange-symbol-list/{exchange}"
EODHD_ETF_TYPES = frozenset({"ETF", "FUND"})
SYMBOL_COLUMN_MAP = {"Code": "symbol", "Name": "name", "Exchange": "exchange", "Type": "type"}
EOD_COLUMN_MAP = {"date": "ts", "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume"}


@register("bar_provider", "eodhd")
class EodhdProvider(BarProvider):
    name = "eodhd"

    def __init__(
        self,
        api_key: str,
        *,
        exchange: str = EODHD_EXCHANGE,
        calls_per_min: float = EODHD_DEFAULT_CALLS_PER_MIN,
        base_url: str = EODHD_BASE_URL,
        cache_dir: str | Path | None = None,
        client: httpx.Client | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        today: Callable[[], date] = date.today,
    ) -> None:
        if not api_key:
            raise ValueError("eodhd: api_key is required (EODHD_API_KEY)")
        self.api_key = api_key
        self.exchange = exchange
        self.base_url = base_url.rstrip("/")
        self._today = today
        self.http = Http(
            client=client,
            rate_per_min=calls_per_min,
            cache_dir=default_cache_dir(self.name) if cache_dir is None else cache_dir,
            clock=clock,
            sleep=sleep,
        )

    @classmethod
    def from_settings(cls, settings: Settings, secrets: Secrets) -> EodhdProvider:
        return cls(secrets.eodhd_api_key or "")

    def _get(self, path: str, params: dict[str, Any], *, cache_salt: str | None) -> Any:
        url = f"{self.base_url}{path}"
        public = {**params, "fmt": "json"}
        # the token is required as a query parameter by the vendor; it is excluded from the cache key
        cache_key = None if cache_salt is None else RawCache.key(url, public, salt=cache_salt)
        return self.http.get_json(url, params={**public, "api_token": self.api_key}, cache_key=cache_key)

    # ------------------------------------------------------------------ reference
    def _symbol_list(self, delisted: bool) -> pd.DataFrame:
        params: dict[str, Any] = {"delisted": 1} if delisted else {}
        rows = self._get(SYMBOL_LIST_PATH.format(exchange=self.exchange), params, cache_salt=f"symbols:{self._today()}")
        if not rows:
            return pd.DataFrame(columns=list(SYMBOL_COLUMN_MAP.values()))
        df = pd.DataFrame(rows)
        for src in SYMBOL_COLUMN_MAP:
            if src not in df.columns:
                df[src] = None
        df = df.rename(columns=SYMBOL_COLUMN_MAP)
        df["active"] = not delisted
        df["listed_at"] = None
        df["delisted_at"] = None
        keep = list(SYMBOL_COLUMN_MAP.values()) + ["active", "listed_at", "delisted_at"]
        extras = [c for c in ("Isin", "Country", "Currency") if c in df.columns]
        return df[keep + extras]

    def delisted_symbols(self) -> pd.DataFrame:
        return normalize_symbols(self._symbol_list(delisted=True))

    def list_symbols(self, include_delisted: bool = True) -> pd.DataFrame:
        frames = [self._symbol_list(delisted=False)]
        if include_delisted:
            frames.append(self._symbol_list(delisted=True))
        df = pd.concat(frames, ignore_index=True)
        if df.empty:
            return normalize_symbols(df)
        # a symbol present in both lists is a re-used ticker; the active row wins
        df = df.sort_values("active", kind="mergesort")
        return normalize_symbols(df)

    # ------------------------------------------------------------------ bars
    def _symbol_bars(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        params = {"from": start.isoformat(), "to": end.isoformat(), "period": "d", "order": "a"}
        salt = "eod" if end < self._today() else None
        rows = self._get(EOD_PATH.format(symbol=symbol, exchange=self.exchange), params, cache_salt=salt)
        if not rows:
            return empty_bars()
        df = pd.DataFrame(rows)
        for src in EOD_COLUMN_MAP:
            if src not in df.columns:
                df[src] = None
        df = df.rename(columns=EOD_COLUMN_MAP)
        adj = pd.to_numeric(df.get("adjusted_close", df["close"]), errors="coerce")
        close = pd.to_numeric(df["close"], errors="coerce")
        factor = (adj / close).where(close > 0, 1.0).fillna(1.0)
        for c in ("open", "high", "low", "close"):
            df[c] = pd.to_numeric(df[c], errors="coerce") * factor
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce") / factor
        df["adj_close"] = adj
        df["vwap"] = None
        df["symbol"] = symbol
        return df

    def daily_bars(self, symbols: Iterable[str], start: date, end: date) -> pd.DataFrame:
        start_d, end_d = as_date(start), as_date(end)
        frames = [self._symbol_bars(s, start_d, end_d) for s in sorted({x.upper() for x in symbols})]
        frames = [f for f in frames if not f.empty]
        if not frames:
            return empty_bars()
        return normalize_bars(pd.concat(frames, ignore_index=True))
