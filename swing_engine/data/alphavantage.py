"""Alpha Vantage `EARNINGS_CALENDAR` (CSV, free tier: 25 requests/day) for earnings-blackout features."""
from __future__ import annotations

import io
import time
from collections.abc import Callable
from pathlib import Path

import httpx
import pandas as pd
import structlog

from ._http import Http

log = structlog.get_logger(__name__)

ALPHAVANTAGE_URL = "https://www.alphavantage.co/query"
EARNINGS_FUNCTION = "EARNINGS_CALENDAR"
EARNINGS_HORIZONS = ("3month", "6month", "12month")
DEFAULT_HORIZON = "3month"
ALPHAVANTAGE_CALLS_PER_MIN = 5
COLUMN_MAP = {
    "symbol": "symbol",
    "name": "name",
    "reportDate": "report_date",
    "fiscalDateEnding": "fiscal_date_ending",
    "estimate": "estimate",
    "currency": "currency",
}
EARNINGS_COLUMNS = list(COLUMN_MAP.values())


def parse_earnings_csv(text: str) -> pd.DataFrame:
    if not text.strip():
        return pd.DataFrame(columns=EARNINGS_COLUMNS)
    df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    for src in COLUMN_MAP:
        if src not in df.columns:
            df[src] = ""
    df = df.rename(columns=COLUMN_MAP)[EARNINGS_COLUMNS]
    df["symbol"] = df["symbol"].str.upper().str.strip()
    df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce").dt.date
    df["fiscal_date_ending"] = pd.to_datetime(df["fiscal_date_ending"], errors="coerce").dt.date
    df["estimate"] = pd.to_numeric(df["estimate"], errors="coerce")
    df = df[df["report_date"].notna() & (df["symbol"] != "")]
    return df.sort_values(["report_date", "symbol"]).reset_index(drop=True)


def earnings_calendar(
    key: str,
    horizon: str = DEFAULT_HORIZON,
    symbol: str | None = None,
    *,
    client: httpx.Client | None = None,
    cache_dir: str | Path | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> pd.DataFrame:
    """Upcoming earnings dates: columns symbol, name, report_date, fiscal_date_ending, estimate, currency."""
    if not key:
        raise ValueError("alphavantage: api key is required (ALPHAVANTAGE_API_KEY)")
    if horizon not in EARNINGS_HORIZONS:
        raise ValueError(f"horizon must be one of {EARNINGS_HORIZONS}")
    params = {"function": EARNINGS_FUNCTION, "horizon": horizon, "apikey": key}
    if symbol:
        params["symbol"] = symbol.upper()
    http = Http(client=client, rate_per_min=ALPHAVANTAGE_CALLS_PER_MIN, cache_dir=cache_dir, sleep=sleep)
    text = http.get_text(ALPHAVANTAGE_URL, params=params)
    if text.lstrip().startswith("{"):
        # the API answers JSON on errors / throttling instead of CSV
        log.warning("alphavantage_non_csv_response", body=text[:200])
        return pd.DataFrame(columns=EARNINGS_COLUMNS)
    return parse_earnings_csv(text)
