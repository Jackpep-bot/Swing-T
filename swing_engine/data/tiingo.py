"""Tiingo bar provider (free tier; owner approved 2026-10-14, he signs up and puts TIINGO_API_KEY in .env himself).
Daily bars back to the 1990s for listed AND delisted US tickers, the source for extending research stores before
2016 (docs/plan-store-2010.md).

Free-tier caps, enforced here so a long backfill never trips them:
* 50 requests an hour and 1,000 a day: the token bucket runs at ``TIINGO_REQUESTS_PER_HOUR`` (41 an hour stays under
  both);
* 500 distinct symbols a calendar month: every symbol fetched is recorded in ``data/raw/tiingo/symbols-YYYY-MM.json``;
  a new symbol beyond ``TIINGO_SYMBOLS_PER_MONTH`` raises ``TiingoQuotaReached`` (cached responses never count).

Tiingo returns raw OHLCV with ``splitFactor`` and ``divCash`` per day. OHLC here are split-adjusted only (the store's
convention); ``adj_close`` is Tiingo's split + dividend adjusted close. Known limit: the price endpoint is keyed by
ticker, so a ticker reused by a later company returns that company's history; the symbol list's start / end dates
show such reuse and the caller must check them (the store keys delisted names as ``TICKER~date``).

    uv run swing --settings config/live.yaml ingest --provider tiingo --symbols ... --start 2010-01-04 --end 2015-12-31
"""
from __future__ import annotations

import io
import json
import time
import zipfile
from collections.abc import Callable, Iterable
from datetime import date
from pathlib import Path

import httpx
import pandas as pd
import structlog

from swing_engine.core.config import Secrets, Settings
from swing_engine.core.interfaces import BarProvider
from swing_engine.core.registry import register

from ._common import as_date, empty_bars, normalize_bars, normalize_symbols
from ._http import Http, RawCache, default_cache_dir

log = structlog.get_logger(__name__)

TIINGO_BASE_URL = "https://api.tiingo.com"
TIINGO_TICKERS_URL = "https://apimedia.tiingo.com/docs/tiingo/daily/supported_tickers.zip"
PRICES_PATH = "/tiingo/daily/{symbol}/prices"
TIINGO_REQUESTS_PER_HOUR = 41  # free tier: 50 an hour and 1,000 a day; 41 x 24 = 984
TIINGO_SYMBOLS_PER_MONTH = 500  # free tier: distinct symbols a month
US_EXCHANGES = frozenset({"NYSE", "NASDAQ", "NYSE ARCA", "NYSE MKT", "AMEX", "BATS", "NYSE NAT"})
ETF_TYPES = frozenset({"ETF", "Mutual Fund"})


class TiingoQuotaReached(RuntimeError):
    """The month's distinct-symbol allowance is used up; resume next month (or with symbols already fetched)."""


@register("bar_provider", "tiingo")
class TiingoProvider(BarProvider):
    name = "tiingo"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = TIINGO_BASE_URL,
        requests_per_hour: float = TIINGO_REQUESTS_PER_HOUR,
        symbols_per_month: int = TIINGO_SYMBOLS_PER_MONTH,
        cache_dir: str | Path | None = None,
        client: httpx.Client | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        today: Callable[[], date] = date.today,
    ) -> None:
        if not api_key:
            raise ValueError("tiingo: api_key is required (TIINGO_API_KEY in .env)")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.symbols_per_month = symbols_per_month
        self._today = today
        self.cache_dir = Path(default_cache_dir(self.name) if cache_dir is None else cache_dir)
        self.http = Http(client=client, rate_per_min=requests_per_hour / 60.0, cache_dir=self.cache_dir, clock=clock,
                         sleep=sleep)

    @classmethod
    def from_settings(cls, settings: Settings, secrets: Secrets) -> TiingoProvider:
        return cls(secrets.tiingo_api_key or "")

    # ------------------------------------------------------------------ monthly symbol ledger
    def _ledger_path(self) -> Path:
        return self.cache_dir / f"symbols-{self._today():%Y-%m}.json"

    def symbols_used(self) -> set[str]:
        path = self._ledger_path()
        return set(json.loads(path.read_text())) if path.exists() else set()

    def _charge(self, symbol: str) -> None:
        used = self.symbols_used()
        if symbol in used:
            return
        if len(used) >= self.symbols_per_month:
            raise TiingoQuotaReached(f"tiingo: {len(used)} distinct symbols already fetched in {self._today():%Y-%m} "
                                     f"(free tier {self.symbols_per_month}); {symbol} not fetched")
        self._ledger_path().parent.mkdir(parents=True, exist_ok=True)
        self._ledger_path().write_text(json.dumps(sorted(used | {symbol})))

    # ------------------------------------------------------------------ reference
    def list_symbols(self, include_delisted: bool = True) -> pd.DataFrame:
        """Tiingo's supported-tickers file (public, no key): US stocks and ETFs with first and last price dates.
        A ticker whose last date is more than 10 days old is treated as delisted."""
        raw = self.http.get_bytes(TIINGO_TICKERS_URL)
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            df = pd.read_csv(z.open(z.namelist()[0]), dtype=str)
        df = df.loc[df["exchange"].isin(US_EXCHANGES) & (df["priceCurrency"] == "USD")
                    & df["assetType"].isin({"Stock", *ETF_TYPES}) & df["ticker"].notna()]
        end = pd.to_datetime(df["endDate"], errors="coerce").dt.date
        active = end >= (pd.Timestamp(self._today()) - pd.Timedelta(days=10)).date()
        out = pd.DataFrame({"symbol": df["ticker"].str.upper(), "name": None, "exchange": df["exchange"],
                            "type": df["assetType"].map(lambda t: "ETF" if t in ETF_TYPES else "CS"),
                            "active": active.to_numpy(), "listed_at": pd.to_datetime(df["startDate"], errors="coerce").dt.date,
                            "delisted_at": end.where(~active)})
        out = out if include_delisted else out.loc[out["active"]]
        return normalize_symbols(out.sort_values("active", kind="mergesort"))  # a reused ticker: the active row wins

    # ------------------------------------------------------------------ bars
    def _symbol_bars(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        url = f"{self.base_url}{PRICES_PATH.format(symbol=symbol.lower())}"
        public = {"startDate": start.isoformat(), "endDate": end.isoformat(), "format": "json"}
        key = RawCache.key(url, public, salt="eod") if end < self._today() else None
        if key is None or self.http.cache.get(key, ".json") is None:
            self._charge(symbol)
        try:  # the token goes in the query (redacted by Http) and never into the cache key
            rows = self.http.get_json(url, params={**public, "token": self.api_key}, cache_key=key)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:  # unknown ticker
                log.info("tiingo_unknown_symbol", symbol=symbol)
                return empty_bars()
            raise
        return split_adjust(pd.DataFrame(rows or []), symbol)

    def daily_bars(self, symbols: Iterable[str], start: date, end: date) -> pd.DataFrame:
        start_d, end_d = as_date(start), as_date(end)
        frames = [self._symbol_bars(s, start_d, end_d) for s in sorted({x.upper() for x in symbols})]
        frames = [f for f in frames if not f.empty]
        return normalize_bars(pd.concat(frames, ignore_index=True)) if frames else empty_bars()


def split_adjust(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Tiingo rows -> bars: OHLC divided (volume multiplied) by the product of the split factors after each day."""
    if df.empty:
        return empty_bars()
    df = df.sort_values("date").reset_index(drop=True)
    split = pd.to_numeric(df.get("splitFactor", 1.0), errors="coerce").fillna(1.0).replace(0.0, 1.0)
    after = split[::-1].cumprod()[::-1].shift(-1, fill_value=1.0)  # splits strictly after the day
    out = pd.DataFrame({"symbol": symbol, "ts": pd.to_datetime(df["date"]).dt.tz_localize(None).dt.date})
    for c in ("open", "high", "low", "close"):
        out[c] = pd.to_numeric(df[c], errors="coerce") / after
    out["volume"] = pd.to_numeric(df["volume"], errors="coerce") * after
    out["vwap"] = None
    out["adj_close"] = pd.to_numeric(df.get("adjClose", df["close"]), errors="coerce")
    return out

