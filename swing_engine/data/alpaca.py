"""Alpaca daily bars via alpaca-py's `StockHistoricalDataClient` (split-adjusted). alpaca-py is imported
lazily so registry discovery stays fast and tests can inject stub clients.

Basic plan: IEX prints, 200 req/min; delisted coverage is partial, so prefer Massive/EODHD for research
history and use Alpaca for execution-side data.
"""
from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from datetime import date, datetime, timedelta
from typing import Any

import pandas as pd
import structlog

from swing_engine.core.config import Secrets, Settings
from swing_engine.core.interfaces import BarProvider
from swing_engine.core.registry import register

from ._common import TZ, as_date, empty_bars, normalize_bars, normalize_symbols
from ._http import TokenBucket

log = structlog.get_logger(__name__)

ALPACA_DEFAULT_CALLS_PER_MIN = 200
ALPACA_BARS_CHUNK = 100  # symbols per multi-symbol bars request
ALPACA_DEFAULT_FEED = "iex"
ASSET_STATUS_ACTIVE = "active"
BARS_COLUMN_MAP = {"timestamp": "ts", "open": "open", "high": "high", "low": "low", "close": "close", "volume": "volume", "vwap": "vwap"}


@register("bar_provider", "alpaca")
class AlpacaProvider(BarProvider):
    name = "alpaca"

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        *,
        paper: bool = True,
        feed: str = ALPACA_DEFAULT_FEED,
        calls_per_min: float = ALPACA_DEFAULT_CALLS_PER_MIN,
        data_client: Any | None = None,
        trading_client: Any | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not data_client and not (api_key and secret_key):
            raise ValueError("alpaca: api_key and secret_key are required (ALPACA_API_KEY / ALPACA_SECRET_KEY)")
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper = paper
        self.feed = feed
        self._data_client = data_client
        self._trading_client = trading_client
        self.bucket = TokenBucket(calls_per_min, clock=clock, sleep=sleep)

    @classmethod
    def from_settings(cls, settings: Settings, secrets: Secrets) -> AlpacaProvider:
        return cls(secrets.alpaca_api_key or "", secrets.alpaca_secret_key or "", paper=secrets.alpaca_paper)

    # ------------------------------------------------------------------ clients (lazy)
    def data_client(self) -> Any:
        if self._data_client is None:
            from alpaca.data.historical import StockHistoricalDataClient

            self._data_client = StockHistoricalDataClient(self.api_key, self.secret_key)
        return self._data_client

    def trading_client(self) -> Any:
        if self._trading_client is None:
            from alpaca.trading.client import TradingClient

            self._trading_client = TradingClient(self.api_key, self.secret_key, paper=self.paper)
        return self._trading_client

    # ------------------------------------------------------------------ reference
    def list_symbols(self, include_delisted: bool = True) -> pd.DataFrame:
        from alpaca.trading.enums import AssetClass
        from alpaca.trading.requests import GetAssetsRequest

        self.bucket.acquire()
        assets = self.trading_client().get_all_assets(GetAssetsRequest(asset_class=AssetClass.US_EQUITY))
        rows = []
        for a in assets:
            status = str(getattr(a, "status", "")).split(".")[-1].lower()
            active = status == ASSET_STATUS_ACTIVE
            if not active and not include_delisted:
                continue
            rows.append(
                {
                    "symbol": a.symbol,
                    "name": getattr(a, "name", None),
                    "exchange": str(getattr(a, "exchange", "")).split(".")[-1],
                    "type": "CS",
                    "active": active,
                    "listed_at": None,
                    "delisted_at": None,
                    "tradable": bool(getattr(a, "tradable", False)),
                    "shortable": bool(getattr(a, "shortable", False)),
                    "easy_to_borrow": bool(getattr(a, "easy_to_borrow", False)),
                }
            )
        return normalize_symbols(pd.DataFrame(rows))

    # ------------------------------------------------------------------ bars
    def _request(self, symbols: list[str], start: date, end: date) -> Any:
        from alpaca.data.enums import Adjustment, DataFeed
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        return StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=TimeFrame.Day,
            start=datetime(start.year, start.month, start.day),
            end=datetime.combine(end + timedelta(days=1), datetime.min.time()),
            adjustment=Adjustment.SPLIT,
            feed=DataFeed(self.feed),
        )

    def daily_bars(self, symbols: Iterable[str], start: date, end: date) -> pd.DataFrame:
        start_d, end_d = as_date(start), as_date(end)
        wanted = sorted({s.upper() for s in symbols})
        frames = []
        for i in range(0, len(wanted), ALPACA_BARS_CHUNK):
            chunk = wanted[i : i + ALPACA_BARS_CHUNK]
            self.bucket.acquire()
            barset = self.data_client().get_stock_bars(self._request(chunk, start_d, end_d))
            df = barset.df if hasattr(barset, "df") else pd.DataFrame(barset)
            if df is None or len(df) == 0:
                continue
            df = df.reset_index()
            for src in BARS_COLUMN_MAP:
                if src not in df.columns:
                    df[src] = None
            df = df.rename(columns=BARS_COLUMN_MAP)
            df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_convert(TZ)
            df["adj_close"] = df["close"]
            frames.append(df[["symbol", "ts", "open", "high", "low", "close", "volume", "vwap", "adj_close"]])
        if not frames:
            return empty_bars()
        return normalize_bars(pd.concat(frames, ignore_index=True))
