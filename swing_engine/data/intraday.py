"""1-minute bars (SPY, QQQ, IWM, GLD, BTC/USD) from Alpaca's free plan, session labels and resampling to 2m-4h.

Spike, real calls with the paper key on the Basic (free) plan, 2026-10-13:
* Stocks `GET data.alpaca.markets/v2/stocks/bars`, timeframe=1Min, **feed=sip**: served free back to
  2016-01-01T00:00Z for all four ETFs (a query from 2010 returns nothing earlier; that is the API's own floor).
  feed=iex returns nothing for 2016 (IEX history starts later), so SIP is the feed used and there is no IEX bias.
  The only limit is recency: SIP data younger than 15 minutes is not served (an open-ended query stops ~16 minutes
  ago), so the ingest never asks past now - 16 minutes.
* `adjustment=split` works on minute bars (AAPL 2020-08-03 14:00Z: raw 442.12 / split 110.53). None of the four
  ETFs has split since 2016, so raw == split here. Adjustment is as of the fetch: after a future split, delete that
  symbol's `intraday_ingest_meta` rows and re-ingest.
* Crypto `GET /v1beta3/crypto/us/bars` (BTC/USD): earliest bar 2021-01-01T06:00Z, works even without keys. Bias:
  these are prints on Alpaca's own crypto venue only (about 1 BTC a minute), not a consolidated tape, so volume
  and trade_count are tiny and highs/lows can miss moves seen elsewhere.
* Limits: `x-ratelimit-limit: 200` calls/min on both endpoints; page size max 10,000 bars (20,000 -> HTTP 400);
  a full page is ~1 MB and returns in ~0.2s. A minute with no trade has no bar (gaps are normal, mostly pre/post).
* Size: SPY ~16k bars a month with extended hours, BTC/USD up to 43k: about 9-10M rows, ~1,400 calls in total.

Store: table `bars_1m` (symbol, ts UTC = minute open, open, high, low, close, volume, vwap, trade_count, session) in
its own DuckDB file (`data.intraday_store_path`), never the daily market store. `session` is 'pre' | 'rth' | 'post'
from the NYSE calendar (early closes respected; 'closed' if a bar ever lands on a non-session day) and 'crypto'.
`intraday_ingest_meta` marks each finished (symbol, month); the month in progress is 'partial' and refetched.

Resampling (`resample`, `read_bars`): bar ts = bar open time, `ts_close` = the instant the bar is final.
* ETFs are anchored at 09:30 New York and never cross a session boundary: a bucket is cut at the open, at the close
  (early closes too) and at 20:00. So 4h bars are 09:30-13:30 and a PARTIAL 13:30-16:00, 1h bars end with a partial
  15:30-16:00, then post-market bars start at the close (16:00-17:30 for 4h). Pre-market: 4h 05:30-09:30 etc.
* Crypto is anchored on the UTC epoch (4h bars open at 00, 04, 08 ... UTC).
* No look-ahead: a bar holds only minutes in [ts, ts_close). A bar is returned only once it is complete, meaning
  the data runs to its close (`as_of`, default each symbol's last minute + 1 minute). "Last minute exists" cannot be
  taken literally because quiet minutes have no bar.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pandas as pd
import structlog

from ._common import TZ
from ._http import Http
from .calendar import schedule
from .news import _month_bounds, month_list
from .store import Store

log = structlog.get_logger(__name__)

STOCK_BARS_URL = "https://data.alpaca.markets/v2/stocks/bars"
CRYPTO_BARS_URL = "https://data.alpaca.markets/v1beta3/crypto/us/bars"
STOCK_FEED = "sip"  # free for data older than 15 minutes (spike 2026-10-13)
PAGE_LIMIT = 10_000  # API maximum per page
CALLS_PER_MIN = 180  # Basic plan: 200/min (x-ratelimit-limit header)
SIP_DELAY = timedelta(minutes=16)  # free plan: nothing younger than 15 minutes
DEFAULT_SYMBOLS: list[str] = ["SPY", "QQQ", "IWM", "GLD", "BTC/USD"]
STOCK_FIRST_DAY = date(2016, 1, 1)  # floor of Alpaca's minute history
CRYPTO_FIRST_DAY = date(2021, 1, 1)
RTH_ANCHOR = pd.Timedelta(hours=9, minutes=30)  # New York wall time
EXT_CLOSE = pd.Timedelta(hours=20)  # end of Alpaca's extended session, New York wall time
ONE_MINUTE = pd.Timedelta(minutes=1)
TIMEFRAMES: dict[str, int] = {"1m": 1, "2m": 2, "5m": 5, "15m": 15, "30m": 30, "1h": 60, "4h": 240}  # minutes

TABLE = "bars_1m"
KEYS: list[str] = ["symbol", "ts"]
SCHEMA: dict[str, str] = {
    "symbol": "VARCHAR", "ts": "TIMESTAMPTZ", "open": "DOUBLE", "high": "DOUBLE", "low": "DOUBLE", "close": "DOUBLE",
    "volume": "DOUBLE", "vwap": "DOUBLE", "trade_count": "BIGINT", "session": "VARCHAR",
}
META_TABLE = "intraday_ingest_meta"
META_KEYS: list[str] = ["symbol", "month"]
META_SCHEMA: dict[str, str] = {
    "symbol": "VARCHAR", "month": "VARCHAR", "fetched_on": "DATE", "status": "VARCHAR", "pages": "INTEGER",
    "rows": "INTEGER", "error": "VARCHAR", "fetched_until": "TIMESTAMP", "feed": "VARCHAR",
}
STATUS_OK, STATUS_PARTIAL, STATUS_ERROR = "ok", "partial", "error"
SESSION_CRYPTO, SESSION_CLOSED = "crypto", "closed"
RESAMPLED_COLUMNS: list[str] = [*SCHEMA, "ts_close"]
_API_COLUMNS = {"t": "ts", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume", "vw": "vwap",
                "n": "trade_count"}


def is_crypto(symbol: str) -> bool:
    return "/" in symbol


# =========================================================================================== sessions
def _utc(ts: pd.Series) -> pd.Series:
    return pd.to_datetime(ts, utc=True)


def _bounds(ts: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """(New York midnight as naive wall time, session open UTC, session close UTC) for each UTC minute; open and
    close are NaT on days the exchange is shut."""
    day = ts.dt.tz_convert(TZ).dt.tz_localize(None).dt.normalize()
    if day.empty:
        return day, ts, ts
    sched = schedule(day.min().date(), day.max().date())
    idx = pd.to_datetime(sched.index)
    opens = pd.Series(sched["market_open"].dt.tz_convert("UTC").to_numpy(), index=idx)
    closes = pd.Series(sched["market_close"].dt.tz_convert("UTC").to_numpy(), index=idx)
    return day, _utc(day.map(opens)), _utc(day.map(closes))


def label_sessions(symbol: pd.Series, ts: pd.Series) -> pd.Series:
    """'crypto' for pairs; else 'pre' (before the open), 'rth' ([open, close), early closes respected), 'post'."""
    ts = _utc(ts)
    _, open_, close = _bounds(ts)
    out = pd.Series("post", index=ts.index, dtype=object)
    out[ts < open_] = "pre"
    out[(ts >= open_) & (ts < close)] = "rth"
    out[open_.isna()] = SESSION_CLOSED
    out[symbol.str.contains("/", regex=False)] = SESSION_CRYPTO
    return out


# ============================================================================================ parsing
def parse_bars_page(payload: dict[str, Any]) -> pd.DataFrame:
    """`bars_1m` rows (with session labels) from one API page."""
    frames = [pd.DataFrame(rows).assign(symbol=sym) for sym, rows in (payload.get("bars") or {}).items() if rows]
    if not frames:
        return pd.DataFrame(columns=list(SCHEMA))
    df = pd.concat(frames, ignore_index=True).rename(columns=_API_COLUMNS)
    df["ts"] = _utc(df["ts"])
    df["session"] = label_sessions(df["symbol"], df["ts"])
    return df.reindex(columns=list(SCHEMA))


# ============================================================================================= client
class AlpacaMinuteBars:
    """Thin REST client for stock (SIP, split-adjusted) and crypto 1-minute bars; keys go in headers only."""

    def __init__(self, api_key: str, secret_key: str, *, http: Http | None = None,
                 calls_per_min: float = CALLS_PER_MIN, feed: str = STOCK_FEED) -> None:
        if http is None and not (api_key and secret_key):
            raise ValueError("alpaca bars: ALPACA_API_KEY / ALPACA_SECRET_KEY are required")
        self.feed = feed
        self.http = http or Http(rate_per_min=calls_per_min, headers={
            "APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key})

    def page(self, symbol: str, start: datetime, end: datetime, token: str | None = None) -> dict[str, Any]:
        """Bars with start <= ts < end, oldest first (the API's `end` is inclusive, so one second is taken off)."""
        params: dict[str, Any] = {
            "symbols": symbol, "timeframe": "1Min", "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": (end - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ"), "limit": PAGE_LIMIT, "sort": "asc",
        }
        if not is_crypto(symbol):
            params |= {"feed": self.feed, "adjustment": "split"}
        if token:
            params["page_token"] = token
        return self.http.get_json(CRYPTO_BARS_URL if is_crypto(symbol) else STOCK_BARS_URL, params=params)


# ============================================================================================= ingest
def run_intraday_ingest(
    store: Store,
    client: Any,
    *,
    symbols: Iterable[str] | None = None,
    start: date = STOCK_FIRST_DAY,
    months: int | None = None,
    now: datetime | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Fetch every (symbol, month) from `start` not yet ingested OK (at most `months` per symbol this run) into
    `bars_1m`. Rows are written page by page, so an interrupted month keeps what it fetched and is redone (upsert)
    next run; a finished month is never fetched again; the current month is 'partial' and refreshed every run."""
    now_utc = (now or datetime.now(UTC).replace(tzinfo=None)) - SIP_DELAY
    meta = store.read_table(META_TABLE)
    done = set() if meta.empty else {
        (r.symbol, r.month) for r in meta.itertuples() if r.status == STATUS_OK}
    totals = {"months": 0, "pages": 0, "rows": 0, "failed": 0}
    errors: dict[str, str] = {}
    for sym in [s.upper().strip() for s in (symbols or DEFAULT_SYMBOLS)]:
        first = max(start, CRYPTO_FIRST_DAY if is_crypto(sym) else STOCK_FIRST_DAY)
        todo = [mo for mo in month_list(first, now_utc.date()) if (sym, mo) not in done]
        if months is not None:
            todo = todo[: max(0, int(months))]
        if progress:
            progress(f"intraday: {sym} {len(todo)} months to fetch")
        for mo in todo:
            lo, hi = _month_bounds(mo)
            hi_eff = min(hi, now_utc)
            row: dict[str, Any] = {"symbol": sym, "month": mo, "fetched_on": now_utc.date(), "pages": 0, "rows": 0,
                                   "error": None, "fetched_until": hi_eff, "feed": None if is_crypto(sym) else getattr(client, "feed", None)}
            try:
                token: str | None = None
                while True:
                    payload = client.page(sym, lo, hi_eff, token)
                    row["pages"] += 1
                    row["rows"] += store.write_table(TABLE, parse_bars_page(payload), KEYS, schema=SCHEMA)
                    token = payload.get("next_page_token")
                    if not token:
                        break
                row["status"] = STATUS_OK if hi <= now_utc else STATUS_PARTIAL
                totals["months"] += 1
            except Exception as exc:  # one bad month must not stop the run; it is retried next time
                row["status"], row["error"] = STATUS_ERROR, str(exc)[:500]
                totals["failed"] += 1
                errors[f"{sym} {mo}"] = row["error"]
                log.warning("intraday_ingest_month_failed", symbol=sym, month=mo, error=row["error"])
            totals["pages"] += row["pages"]
            totals["rows"] += row["rows"]
            store.write_table(META_TABLE, pd.DataFrame([row], columns=list(META_SCHEMA)), META_KEYS,
                              schema=META_SCHEMA)
            if progress:
                progress(f"intraday: {sym} {mo} {row['status']} {row['pages']} pages {row['rows']} rows")
    log.info("intraday_ingest_done", **totals)
    return {**totals, "months_done_before": len(done), "errors": errors}


# =========================================================================================== resample
def _instant(value: date | datetime | str | pd.Timestamp) -> pd.Timestamp:
    t = pd.Timestamp(value)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def resample(
    bars_1m: pd.DataFrame, timeframe: str, *, as_of: datetime | pd.Timestamp | None = None
) -> pd.DataFrame:
    """Aggregate `bars_1m` rows to `timeframe` (see TIMEFRAMES and the module docstring for the anchoring). Returns
    the `bars_1m` columns plus `ts_close`; only bars with ts_close <= as_of (default: each symbol's last minute +
    1 minute), so a bar never contains or waits on a minute after its own close."""
    if timeframe not in TIMEFRAMES:
        raise ValueError(f"unknown timeframe {timeframe!r}; expected one of {list(TIMEFRAMES)}")
    if bars_1m is None or bars_1m.empty:
        return pd.DataFrame(columns=RESAMPLED_COLUMNS)
    tf = pd.Timedelta(minutes=TIMEFRAMES[timeframe])
    df = bars_1m.assign(ts=_utc(bars_1m["ts"])).sort_values(["symbol", "ts"]).reset_index(drop=True)
    ts, session = df["ts"], df["session"]
    day, open_, close = _bounds(ts)
    wall = ts.dt.tz_convert(TZ).dt.tz_localize(None)
    etf_start = ts - ((wall - day - RTH_ANCHOR) % tf)  # bucket open, counted from 09:30 New York
    crypto = session == SESSION_CRYPTO
    bucket = etf_start.where(~crypto, ts.dt.floor(tf))
    start, end = bucket.copy(), bucket + tf
    rth, pre, post = session == "rth", session == "pre", session == "post"
    start[rth] = start[rth].where(start[rth] >= open_[rth], open_[rth])
    end[rth] = end[rth].where(end[rth] <= close[rth], close[rth])
    end[pre] = end[pre].where(end[pre] <= open_[pre], open_[pre])
    start[post] = start[post].where(start[post] >= close[post], close[post])
    ext = ts + (day + EXT_CLOSE - wall)  # 20:00 New York of the bar's day
    end[post] = end[post].where((end[post] <= ext[post]) | (ts[post] >= ext[post]), ext[post])
    df["bar"], df["ts_close"] = start, end
    df["pv"] = df["vwap"].fillna(df["close"]) * df["volume"]
    out = df.groupby(["symbol", "bar"], sort=True).agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
        volume=("volume", "sum"), pv=("pv", "sum"), trade_count=("trade_count", "sum"), session=("session", "first"),
        ts_close=("ts_close", "first"), last_minute=("ts", "last"),
    ).reset_index().rename(columns={"bar": "ts"})
    out["vwap"] = (out["pv"] / out["volume"]).where(out["volume"] > 0, out["close"])
    limit = (out.groupby("symbol")["last_minute"].transform("max") + ONE_MINUTE) if as_of is None else _instant(as_of)
    return out[out["ts_close"] <= limit][RESAMPLED_COLUMNS].reset_index(drop=True)


def read_bars(
    store: Store, symbol: str, timeframe: str,
    start: date | datetime | str | pd.Timestamp, end: date | datetime | str | pd.Timestamp,
) -> pd.DataFrame:
    """Complete `timeframe` bars of `symbol` with start <= ts < end (naive values are UTC), resampled on read from
    `bars_1m`. Completeness is judged against the symbol's last stored minute."""
    # ponytail: resamples on every read (a month of minutes takes milliseconds); add cached `bars_<tf>` tables
    # only if the replay shows this is the bottleneck.
    lo, hi = _instant(start), _instant(end)
    tf = pd.Timedelta(minutes=TIMEFRAMES[timeframe])
    sym = symbol.upper().strip()
    rows = store.read_table(TABLE, "symbol = ? AND ts >= ? AND ts < ?",
                            [sym, (lo - tf).to_pydatetime(), (hi + tf).to_pydatetime()], order_by="ts")
    if rows.empty:
        return pd.DataFrame(columns=RESAMPLED_COLUMNS)
    last = store.sql(f"SELECT max(ts) AS m FROM {TABLE} WHERE symbol = ?", [sym])["m"].iloc[0]
    out = resample(rows, timeframe, as_of=_instant(last) + ONE_MINUTE)
    return out[(out["ts"] >= lo) & (out["ts"] < hi)].reset_index(drop=True)


__all__ = [
    "TABLE", "META_TABLE", "TIMEFRAMES", "DEFAULT_SYMBOLS", "AlpacaMinuteBars", "parse_bars_page", "label_sessions",
    "run_intraday_ingest", "resample", "read_bars",
]
