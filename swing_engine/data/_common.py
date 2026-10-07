"""Shared constants and frame helpers for the data layer (no provider logic here)."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime

import pandas as pd

TZ = "America/New_York"
BAR_COLUMNS: list[str] = ["symbol", "ts", "open", "high", "low", "close", "volume", "vwap", "adj_close"]
PRICE_COLUMNS: list[str] = ["open", "high", "low", "close", "volume", "vwap", "adj_close"]
BAR_KEYS: list[str] = ["symbol", "ts"]
SYMBOL_COLUMNS: list[str] = ["symbol", "name", "exchange", "type", "active", "listed_at", "delisted_at"]
RAW_CACHE_DIR = "data/raw"  # relative to the repo root; providers append their own name


def as_date(value: date | datetime | str | pd.Timestamp) -> date:
    """Coerce a date-like value to a plain `date` (a datetime keeps its calendar day)."""
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()


def session_ts(d: date | datetime | str) -> pd.Timestamp:
    """Midnight America/New_York timestamp for a session date (the canonical daily-bar `ts`)."""
    return pd.Timestamp(as_date(d)).tz_localize(TZ).as_unit("us")


def to_session_ts(values: pd.Series | Iterable) -> pd.Series:
    """Vectorized `session_ts`: naive inputs are taken as New York local, aware inputs converted, then
    normalized to midnight so that any representation of a trading day maps to the same key."""
    s = pd.to_datetime(pd.Series(values))
    if s.dt.tz is None:
        s = s.dt.tz_localize(TZ)
    else:
        s = s.dt.tz_convert(TZ)
    return s.dt.normalize().dt.as_unit("us")


def empty_bars() -> pd.DataFrame:
    frame = pd.DataFrame({c: pd.Series(dtype="float64") for c in PRICE_COLUMNS})
    frame.insert(0, "ts", pd.Series(dtype=f"datetime64[us, {TZ}]"))
    frame.insert(0, "symbol", pd.Series(dtype="str"))
    return frame[BAR_COLUMNS]


def normalize_bars(df: pd.DataFrame) -> pd.DataFrame:
    """Return a long bars frame with the contract columns, float prices, tz-aware session `ts`,
    upper-case symbols, sorted by (symbol, ts) and de-duplicated on the key (last wins)."""
    if df is None or len(df) == 0:
        return empty_bars()
    out = df.copy()
    for c in PRICE_COLUMNS:
        if c not in out.columns:
            out[c] = float("nan")
        out[c] = pd.to_numeric(out[c], errors="coerce").astype("float64")
    out["symbol"] = out["symbol"].astype("str").str.upper().str.strip()
    out["ts"] = to_session_ts(out["ts"])
    out = out[BAR_COLUMNS]
    out = out.drop_duplicates(subset=BAR_KEYS, keep="last").sort_values(BAR_KEYS, kind="mergesort")
    return out.reset_index(drop=True)


def empty_symbols() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": pd.Series(dtype="str"),
            "name": pd.Series(dtype="str"),
            "exchange": pd.Series(dtype="str"),
            "type": pd.Series(dtype="str"),
            "active": pd.Series(dtype="bool"),
            "listed_at": pd.Series(dtype="object"),
            "delisted_at": pd.Series(dtype="object"),
        }
    )


def _to_date_or_none(values: pd.Series) -> pd.Series:
    """Dates stay calendar dates: naive values are taken as-is, aware values are read on the UTC calendar
    (vendors write `2024-01-02T00:00:00Z` for the day itself)."""
    parsed = pd.to_datetime(values, errors="coerce", format="mixed", utc=True)
    dates = parsed.dt.date
    return dates.where(parsed.notna(), None).astype("object")


def normalize_symbols(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure the `list_symbols` contract columns exist (extra provider columns are kept after them)."""
    if df is None or len(df) == 0:
        return empty_symbols()
    out = df.copy()
    for c in SYMBOL_COLUMNS:
        if c not in out.columns:
            out[c] = None
    out["symbol"] = out["symbol"].astype("str").str.upper().str.strip()
    out["active"] = out["active"].fillna(True).astype("bool")
    out["listed_at"] = _to_date_or_none(out["listed_at"])
    out["delisted_at"] = _to_date_or_none(out["delisted_at"])
    extras = [c for c in out.columns if c not in SYMBOL_COLUMNS]
    out = out[SYMBOL_COLUMNS + extras]
    out = out.drop_duplicates(subset=["symbol"], keep="last").sort_values("symbol", kind="mergesort")
    return out.reset_index(drop=True)
