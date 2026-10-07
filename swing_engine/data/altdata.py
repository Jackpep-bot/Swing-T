"""Free nightly alternative-data files (no key): Nasdaq short-sale-restriction (Rule 201) list, Nasdaq
Reg SHO threshold list and FINRA consolidated (CNMS) daily short volume. Pure parsers plus one fetcher.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date
from pathlib import Path

import httpx
import pandas as pd
import structlog

from ._common import as_date
from ._http import Http, default_cache_dir

log = structlog.get_logger(__name__)

NASDAQ_SSR_URL = "https://www.nasdaqtrader.com/dynamic/symdir/shorthalts/shorthalts{yyyymmdd}.txt"
NASDAQ_REGSHO_URL = "https://www.nasdaqtrader.com/dynamic/symdir/regsho/nasdaqth{yyyymmdd}.txt"
FINRA_CNMS_URL = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{yyyymmdd}.txt"
ALTDATA_CALLS_PER_MIN = 60
TRAILER_PREFIX = "file creation time"
SSR_COLUMNS = ["symbol", "security_name", "market_category", "trigger_time", "date"]
REGSHO_COLUMNS = ["symbol", "security_name", "market_category", "threshold_flag", "rule_3210", "date"]
SHORT_VOLUME_COLUMNS = ["date", "symbol", "short_volume", "short_exempt_volume", "total_volume", "market", "short_ratio"]
HTTP_NOT_FOUND = 404


def _snake(name: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in name.strip().lower()).strip("_")


def _split_rows(text: str) -> tuple[list[str], list[list[str]]]:
    """Header + rows of a Nasdaq/FINRA delimited file; the delimiter is sniffed ('|' or ','), trailer
    lines ('File Creation Time: ...') and short rows are dropped."""
    lines = [ln.rstrip("\r") for ln in text.splitlines() if ln.strip()]
    if not lines:
        return [], []
    delim = "|" if "|" in lines[0] else ","
    header = [_snake(h) for h in lines[0].split(delim)]
    rows = []
    for ln in lines[1:]:
        if ln.strip().lower().startswith(TRAILER_PREFIX):
            continue
        parts = [p.strip() for p in ln.split(delim)]
        if len(parts) < len(header):
            continue
        rows.append(parts[: len(header)])
    return header, rows


def _frame(text: str) -> pd.DataFrame:
    header, rows = _split_rows(text)
    if not header:
        return pd.DataFrame()
    return pd.DataFrame(rows, columns=header)


def _yes(values: pd.Series) -> pd.Series:
    return values.astype("str").str.strip().str.upper().str.startswith("Y")


def parse_ssr_list(text: str, file_date: date | None = None) -> pd.DataFrame:
    """Nasdaq shorthaltsYYYYMMDD.txt -> symbol, security_name, market_category, trigger_time, date."""
    df = _frame(text)
    if df.empty or "symbol" not in df.columns:
        return pd.DataFrame(columns=SSR_COLUMNS)
    out = pd.DataFrame({"symbol": df["symbol"].str.upper()})
    out["security_name"] = df.get("security_name", pd.Series([None] * len(df), index=df.index))
    out["market_category"] = df.get("market_category", pd.Series([None] * len(df), index=df.index))
    trigger_col = next((c for c in df.columns if c.startswith("trigger")), None)
    out["trigger_time"] = df[trigger_col] if trigger_col else None
    out["date"] = file_date
    extras = [c for c in df.columns if _snake(c) not in {"symbol", "security_name", "market_category", trigger_col}]
    for c in extras:
        out[c] = df[c]
    return out.reset_index(drop=True)


def parse_regsho_threshold(text: str, file_date: date | None = None) -> pd.DataFrame:
    """Nasdaq nasdaqthYYYYMMDD.txt -> symbol, security_name, market_category, threshold_flag, rule_3210, date."""
    df = _frame(text)
    if df.empty or "symbol" not in df.columns:
        return pd.DataFrame(columns=REGSHO_COLUMNS)
    out = pd.DataFrame({"symbol": df["symbol"].str.upper()})
    out["security_name"] = df.get("security_name", pd.Series([None] * len(df), index=df.index))
    out["market_category"] = df.get("market_category", pd.Series([None] * len(df), index=df.index))
    flag_col = next((c for c in df.columns if "threshold" in c), None)
    out["threshold_flag"] = _yes(df[flag_col]) if flag_col else True
    rule_col = next((c for c in df.columns if "3210" in c), None)
    out["rule_3210"] = _yes(df[rule_col]) if rule_col else False
    out["date"] = file_date
    return out.reset_index(drop=True)


def parse_finra_short_volume(text: str) -> pd.DataFrame:
    """FINRA CNMSshvolYYYYMMDD.txt -> date, symbol, short_volume, short_exempt_volume, total_volume, market, short_ratio."""
    df = _frame(text)
    if df.empty or "symbol" not in df.columns:
        return pd.DataFrame(columns=SHORT_VOLUME_COLUMNS)
    out = pd.DataFrame({"symbol": df["symbol"].str.upper()})
    out["date"] = pd.to_datetime(df.get("date"), format="%Y%m%d", errors="coerce").dt.date
    for src, dst in (("shortvolume", "short_volume"), ("shortexemptvolume", "short_exempt_volume"), ("totalvolume", "total_volume")):
        out[dst] = pd.to_numeric(df.get(src), errors="coerce")
    out["market"] = df.get("market")
    out = out[out["date"].notna()]
    out["short_ratio"] = (out["short_volume"] / out["total_volume"]).where(out["total_volume"] > 0)
    return out[SHORT_VOLUME_COLUMNS].reset_index(drop=True)


def nightly_files(
    d: date | str,
    *,
    client: httpx.Client | None = None,
    cache_dir: str | Path | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, pd.DataFrame]:
    """Fetch and parse the three files for session `d`: keys `ssr`, `regsho_threshold`, `short_volume`.
    A file that is not published yet (HTTP 404) yields an empty frame rather than an exception."""
    day = as_date(d)
    stamp = day.strftime("%Y%m%d")
    http = Http(
        client=client,
        rate_per_min=ALTDATA_CALLS_PER_MIN,
        cache_dir=default_cache_dir("altdata") if cache_dir is None else cache_dir,
        sleep=sleep,
    )
    sources: dict[str, tuple[str, Callable[[str], pd.DataFrame], list[str]]] = {
        "ssr": (NASDAQ_SSR_URL, lambda t: parse_ssr_list(t, day), SSR_COLUMNS),
        "regsho_threshold": (NASDAQ_REGSHO_URL, lambda t: parse_regsho_threshold(t, day), REGSHO_COLUMNS),
        "short_volume": (FINRA_CNMS_URL, parse_finra_short_volume, SHORT_VOLUME_COLUMNS),
    }
    out: dict[str, pd.DataFrame] = {}
    for key, (template, parser, columns) in sources.items():
        url = template.format(yyyymmdd=stamp)
        try:
            text = http.get_text(url, cache_key=f"{key}_{stamp}", cache_suffix=".txt")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == HTTP_NOT_FOUND:
                log.info("altdata_file_missing", source=key, date=str(day))
                out[key] = pd.DataFrame(columns=columns)
                continue
            raise
        out[key] = parser(text)
        log.info("altdata_file_parsed", source=key, date=str(day), rows=len(out[key]))
    return out
