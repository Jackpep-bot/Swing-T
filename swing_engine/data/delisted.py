"""Delisted US common stocks 2017-2024 under distinct entity keys (docs/proposals/delisted-history-spike-2026-10.md).

Alpaca keys bar history by ticker, so a dead company and a later company that reuses its ticker share one series.
Every dead entity is therefore stored under its own key ``TICKER~YYYYMMDD`` (ticker + date of its last traded bar);
the live company keeps the plain ticker. The ``~`` keys are research-only: the live paths (nightly, broker) refuse
them (``is_entity_key``).

Tables written:
* ``delisted_candidates``: the enumeration (Massive inactive tickers + Alpha Vantage dated delisted lists), one row
  per (ticker, delist_date) with a fetch ``status`` (pending | ok | no_bars | skipped_rename) so the ingest resumes.
* ``listings``: one row per stored entity key: ticker, cik, figi, name, first_bar, last_bar, delist_date,
  delist_reason (performance | merger), reason_source, source.
* ``symbols``: a reference row per key (listed_at = first bar, delisted_at = day after the last bar) so
  ``data.universe.build_universe`` admits the key only on dates it traded.
* ``bars``: the entity's Alpaca SIP split-adjusted bars, cut at the delisting, zero-volume rows dropped.

Delisting cause: no free source before 2020, so it is a heuristic on the last bars (``classify_delisting``).
``delisting_returns`` turns it into the exit multiplier the backtest/replay apply when a held key stops trading.
"""
from __future__ import annotations

import io
import math
import re
from collections.abc import Callable, Iterable, Mapping
from datetime import date, timedelta
from typing import Any

import pandas as pd
import structlog

from ._common import as_date
from .calendar import trading_days

log = structlog.get_logger(__name__)

#: Version of the rules below (key scheme, cut thresholds, cause heuristic). Bump when any of them changes.
DELISTED_RULES_VERSION = "2026-10-08"
ENTITY_SEP = "~"
KEY_DATE_FORMAT = "%Y%m%d"

WINDOW_START = date(2017, 1, 1)
#: First session of the Massive grouped-daily window; before it the store holds the Alpaca extension.
MASSIVE_WINDOW_START = date(2024, 10, 7)
ALPACA_HISTORY_START = date(2016, 1, 4)  # documented floor of Alpaca SIP daily history
#: A gap of more than this many calendar days between traded bars is an entity boundary (spike: ticker reuse,
#: bankrupt-then-relisted). About 20 sessions.
ENTITY_GAP_CALENDAR_DAYS = 30
#: Bars are kept up to this many sessions after the vendor's delisting date (vendor dates are a few days off).
DELIST_TRUNCATE_SESSIONS = 3
#: An Alpha Vantage row within this many days of a Massive row for the same ticker is the same entity.
AV_MATCH_DAYS = 45

# cause heuristic (performance = bankruptcy / failure / exchange delisting; otherwise merger or going private)
PERFORMANCE_LAST_CLOSE = 1.0  # last close below $1
PERFORMANCE_RET_60 = -0.50  # or the last 60 sessions lost half
PERFORMANCE_RET_5 = -0.30  # or the last 5 sessions lost 30% (sudden bank failures: SIVB)
PERFORMANCE = "performance"
MERGER = "merger"
PERFORMANCE_REASONS = frozenset({PERFORMANCE, "bankruptcy", "failure"})
#: Shumway (1997) delisting return for performance delistings; -1.0 is the conservative variant. The settings
#: param ``data.delist_return_performance`` overrides it.
DELIST_RETURN_PERFORMANCE = -0.30
DELIST_RETURN_CONSERVATIVE = -1.0

CANDIDATES_TABLE = "delisted_candidates"
LISTINGS_TABLE = "listings"
SYMBOLS_TABLE = "symbols"
LISTINGS_SCHEMA: dict[str, str] = {
    "key": "VARCHAR", "ticker": "VARCHAR", "cik": "VARCHAR", "composite_figi": "VARCHAR", "name": "VARCHAR",
    "first_bar": "DATE", "last_bar": "DATE", "delist_date": "DATE", "delist_reason": "VARCHAR",
    "reason_source": "VARCHAR", "source": "VARCHAR", "rules_version": "VARCHAR",
}
STATUS_PENDING, STATUS_OK, STATUS_NO_BARS, STATUS_RENAME = "pending", "ok", "no_bars", "skipped_rename"
FIGI = "composite_figi"
CANDIDATE_COLUMNS = ["ticker", "delist_date", "name", "cik", "composite_figi", "type", "exchange", "source"]

MASSIVE_TICKERS_PATH = "/v3/reference/tickers"
MASSIVE_STOCK_TYPES = ("CS", "ADRC")
MASSIVE_PAGE_LIMIT = 1000
MASSIVE_MAX_PAGES = 60
AV_URL = "https://www.alphavantage.co/query"
AV_CALLS_PER_MIN = 5  # free key: 5/min, 25/day; the 8 dated lists fit in one day
AV_YEAR_ENDS = tuple(date(y, 12, 31) for y in range(2017, 2025))
#: names that are not plain common stock (units, warrants, rights, preferreds, notes, pre-merger SPACs)
NON_COMMON = re.compile(
    r"\b(warrants?|units?|rights?|preferred|pfd|notes?|debentures?|when[- ]issued|depositary shares|"
    r"acquisition corp(oration)?|merger corp)\b", re.IGNORECASE,
)
BANKRUPT_SUFFIX = "Q"  # Alpaca sometimes keeps the full history under the bankruptcy ticker (YELLQ)
FETCH_CHUNK = 50  # candidates per Alpaca request (x2 symbols with the Q variant; Alpaca takes 100)


# ----------------------------------------------------------------------------------------------- key scheme


def entity_key(ticker: str, last_bar: date | str) -> str:
    return f"{ticker.upper().strip()}{ENTITY_SEP}{as_date(last_bar).strftime(KEY_DATE_FORMAT)}"


def is_entity_key(symbol: object) -> bool:
    return ENTITY_SEP in str(symbol)


def split_key(key: str) -> tuple[str, date | None]:
    """``TICKER~YYYYMMDD`` -> (ticker, last-bar date); a plain ticker -> (ticker, None)."""
    ticker, sep, stamp = str(key).partition(ENTITY_SEP)
    if not sep:
        return ticker, None
    return ticker, pd.to_datetime(stamp, format=KEY_DATE_FORMAT).date()


def drop_entity_keys(frame: pd.DataFrame, column: str = "symbol") -> pd.DataFrame:
    """Rows of ``frame`` whose ``column`` is a live ticker (the ticker-keyed live paths call this)."""
    if frame is None or len(frame) == 0 or column not in frame.columns:
        return frame
    return frame.loc[~frame[column].astype(str).str.contains(ENTITY_SEP, regex=False)]


# ----------------------------------------------------------------------------------------------- bar rules


def _days(bars: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(bars["ts"]).dt.date


def last_entity_segment(bars: pd.DataFrame, gap_days: int = ENTITY_GAP_CALENDAR_DAYS) -> pd.DataFrame:
    """Traded rows (volume > 0) of one symbol after its last gap longer than ``gap_days`` calendar days."""
    traded = bars.loc[pd.to_numeric(bars["volume"], errors="coerce").fillna(0) > 0].sort_values("ts")
    if traded.empty:
        return traded
    gaps = pd.to_datetime(traded["ts"]).diff().dt.days.fillna(0).to_numpy()
    starts = [i for i, g in enumerate(gaps) if g > gap_days]
    return traded.iloc[starts[-1] if starts else 0 :]


def cut_entity(bars: pd.DataFrame, delist_date: date, *, gap_days: int = ENTITY_GAP_CALENDAR_DAYS,
               truncate_sessions: int = DELIST_TRUNCATE_SESSIONS) -> pd.DataFrame:
    """The dead entity's bars inside one ticker's (possibly stitched) series: rows up to ``truncate_sessions``
    sessions after ``delist_date``, zero-volume filler dropped, and only the segment after the last long gap."""
    if bars.empty:
        return bars
    after = trading_days(delist_date + timedelta(days=1), delist_date + timedelta(days=3 * truncate_sessions + 10))
    cutoff = after[truncate_sessions - 1] if len(after) >= truncate_sessions else delist_date
    return last_entity_segment(bars.loc[_days(bars) <= cutoff], gap_days)


def classify_delisting(closes: Iterable[float]) -> str:
    """Heuristic cause from an entity's closes (oldest first): performance when the last close is below $1, or
    the last 60 sessions lost half, or the last 5 lost 30%; otherwise merger (acquired / taken private).
    ponytail: bars-only heuristic; Alpaca corporate actions (worthless_removal vs cash/stock_merger) can
    confirm it for 2020+ delistings."""
    c = [float(x) for x in closes if x is not None and math.isfinite(float(x))]
    if not c:
        return PERFORMANCE
    last = c[-1]

    def ret(n: int) -> float:
        base = c[-n - 1] if len(c) > n else c[0]
        return last / base - 1.0 if base > 0 else 0.0

    if last < PERFORMANCE_LAST_CLOSE or ret(60) <= PERFORMANCE_RET_60 or ret(5) <= PERFORMANCE_RET_5:
        return PERFORMANCE
    return MERGER


def listing_row(key: str, segment: pd.DataFrame, meta: Mapping[str, Any], source: str) -> dict[str, Any]:
    days = _days(segment)
    ticker, _ = split_key(key)
    return {
        "key": key, "ticker": ticker, "cik": meta.get("cik"), "composite_figi": meta.get("composite_figi"),
        "name": meta.get("name"), "first_bar": days.min(), "last_bar": days.max(),
        "delist_date": meta.get("delist_date"), "delist_reason": classify_delisting(segment["close"]),
        "reason_source": "heuristic", "source": source, "rules_version": DELISTED_RULES_VERSION,
    }


def symbols_row(listing: Mapping[str, Any], meta: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Reference row for ``data.universe``: admitted on [first_bar, last_bar] only."""
    meta = meta or {}
    return {
        "symbol": listing["key"], "name": listing.get("name"), "exchange": meta.get("exchange"),
        "type": meta.get("type"), "active": False, "listed_at": listing["first_bar"],
        "delisted_at": listing["last_bar"] + timedelta(days=1), "cik": listing.get("cik"),
        "composite_figi": listing.get("composite_figi"),
    }


def write_entities(store: Any, listings: list[dict[str, Any]], metas: list[Mapping[str, Any]]) -> None:
    if not listings:
        return
    from .ingest import write_symbols

    frame = pd.DataFrame(listings).reindex(columns=list(LISTINGS_SCHEMA))
    store.write_table(LISTINGS_TABLE, frame, ["key"], schema=LISTINGS_SCHEMA)
    write_symbols(store, pd.DataFrame([symbols_row(r, m) for r, m in zip(listings, metas, strict=True)]))


# ----------------------------------------------------------------------------------------------- delisting exit


def delisting_returns(store: Any, settings: Any = None) -> dict[str, float]:
    """``{entity key: exit price multiplier}`` for the keys whose listing says a performance delisting
    (1 + ``data.delist_return_performance``, default Shumway's -30%). Merger keys are absent (exit at the last
    close). Empty without a ``listings`` table."""
    if store is None or not callable(getattr(store, "has_table", None)) or not store.has_table(LISTINGS_TABLE):
        return {}
    frame = store.read_table(LISTINGS_TABLE)
    if frame.empty:
        return {}
    data = getattr(settings, "data", None)
    ret = float(getattr(data, "delist_return_performance", DELIST_RETURN_PERFORMANCE))
    hit = frame.loc[frame["delist_reason"].astype(str).str.lower().isin(PERFORMANCE_REASONS)]
    return {str(k).upper(): 1.0 + ret for k in hit["key"]}


# ----------------------------------------------------------------------------------------------- enumeration


def _is_common(name: object, ticker: object) -> bool:
    t = str(ticker or "")
    return bool(t) and not any(ch in t for ch in "-./ ") and not NON_COMMON.search(str(name or ""))


def massive_inactive(massive: Any, start: date = WINDOW_START, end: date = MASSIVE_WINDOW_START) -> pd.DataFrame:
    """Massive inactive CS/ADRC tickers delisted in [start, end). Pages the whole list by ticker (the
    delisted_utc filter is ignored by the API), cached per page so a re-run costs nothing."""
    rows: list[dict[str, Any]] = []
    for kind in MASSIVE_STOCK_TYPES:
        params = {"market": "stocks", "type": kind, "active": "false", "limit": MASSIVE_PAGE_LIMIT,
                  "sort": "ticker", "order": "asc"}
        for r in massive._paginate(MASSIVE_TICKERS_PATH, params, cache_salt=f"delisted_ingest:{kind}",
                                   max_pages=MASSIVE_MAX_PAGES):
            when = pd.to_datetime(r.get("delisted_utc"), errors="coerce", utc=True)
            if pd.isna(when) or not (start <= when.date() < end) or not _is_common(r.get("name"), r.get("ticker")):
                continue
            rows.append({"ticker": str(r["ticker"]).upper(), "delist_date": when.date(), "name": r.get("name"),
                         "cik": r.get("cik"), "composite_figi": r.get("composite_figi"), "type": kind,
                         "exchange": r.get("primary_exchange"), "source": "massive"})
    return pd.DataFrame(rows, columns=CANDIDATE_COLUMNS)


def parse_av_listing(text: str, start: date = WINDOW_START, end: date = MASSIVE_WINDOW_START) -> pd.DataFrame:
    """Alpha Vantage LISTING_STATUS CSV -> delisted common stocks in [start, end)."""
    if not text.strip() or text.lstrip().startswith("{"):
        return pd.DataFrame(columns=CANDIDATE_COLUMNS)
    df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    df = df.loc[df["assetType"].str.lower() == "stock"]
    when = pd.to_datetime(df["delistingDate"], errors="coerce").dt.date
    common = pd.Series([_is_common(n, t) for n, t in zip(df["name"], df["symbol"], strict=True)], index=df.index)
    keep = when.notna() & (when >= start) & (when < end) & common
    df, when = df.loc[keep], when.loc[keep]
    return pd.DataFrame({
        "ticker": df["symbol"].str.upper().str.strip(), "delist_date": when, "name": df["name"], "cik": None,
        "composite_figi": None, "type": "CS", "exchange": df["exchange"], "source": "alphavantage",
    }, columns=CANDIDATE_COLUMNS)


def av_delisted(http: Any, key: str, as_of: date) -> pd.DataFrame:
    """One LISTING_STATUS call (state=delisted, date=as_of), cached on disk by the Http client."""
    params = {"function": "LISTING_STATUS", "state": "delisted", "date": as_of.isoformat(), "apikey": key}
    text = http.get_text(AV_URL, params=params, cache_key=f"av_listing_delisted_{as_of:%Y%m%d}")
    return parse_av_listing(text)


def merge_candidates(massive_rows: pd.DataFrame, av_rows: pd.DataFrame, live: pd.DataFrame | None = None,
                     match_days: int = AV_MATCH_DAYS) -> pd.DataFrame:
    """Massive rows first; an AV row is added only when no Massive (or earlier AV) row has the same ticker
    within ``match_days`` (AV's dated lists recover earlier owners of reused tickers). Rows sharing a composite
    FIGI (persistent across ticker changes; a CIK is shared by share classes) keep the latest delisting. Candidates
    whose FIGI belongs to an active ``live`` symbol are renames whose history Alpaca keeps under the live ticker: status skipped_rename."""
    out: list[dict[str, Any]] = []
    seen: dict[str, list[date]] = {}
    for frame in (massive_rows, av_rows):
        for r in frame.sort_values(["ticker", "delist_date"]).to_dict("records"):
            dates = seen.setdefault(r["ticker"], [])
            if r["source"] != "massive" and any(abs((r["delist_date"] - d).days) <= match_days for d in dates):
                continue
            dates.append(r["delist_date"])
            out.append(r)
    df = pd.DataFrame(out, columns=CANDIDATE_COLUMNS)
    has = df[FIGI].notna() & (df[FIGI].astype(str) != "")
    latest = df.loc[has].sort_values("delist_date").drop_duplicates(FIGI, keep="last")
    df = pd.concat([df.loc[~has], latest]).sort_values(["ticker", "delist_date"]).reset_index(drop=True)
    df["status"] = STATUS_PENDING
    if live is not None and len(live) and FIGI in live.columns:
        act = live.loc[live["active"].fillna(False).astype(bool)] if "active" in live.columns else live
        ids = set(act[FIGI].dropna().astype(str)) - {""}
        df.loc[df[FIGI].astype(str).isin(ids), "status"] = STATUS_RENAME
    return df


# ----------------------------------------------------------------------------------------------- ingest


def _pick_series(bars: pd.DataFrame, ticker: str, delist: date) -> pd.DataFrame:
    """The longer cut entity of ``ticker`` and ``ticker+Q`` (renamed-in-bankruptcy histories)."""
    best = pd.DataFrame()
    for sym in (ticker, ticker + BANKRUPT_SUFFIX):
        seg = cut_entity(bars.loc[bars["symbol"] == sym], delist)
        if len(seg) > len(best):
            best = seg
    return best


def run_delisted_ingest(
    store: Any,
    alpaca: Any,
    *,
    massive: Any = None,
    av_http: Any = None,
    av_key: str | None = None,
    refresh: bool = False,
    limit: int | None = None,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Enumerate (once; ``refresh`` re-enumerates) and fetch every pending candidate. Resumable: each chunk's
    bars, listings, symbols rows and candidate statuses are written before the next request."""
    say = progress or (lambda _line: None)
    if av_http is None and av_key:
        from ._http import Http, default_cache_dir

        av_http = Http(rate_per_min=AV_CALLS_PER_MIN, cache_dir=default_cache_dir("alphavantage"))
    have = store.read_table(CANDIDATES_TABLE) if store.has_table(CANDIDATES_TABLE) else pd.DataFrame()
    if refresh or have.empty:
        if massive is None:
            raise ValueError("no delisted candidates in the store yet: a Massive client is required to enumerate")
        m_rows = massive_inactive(massive)
        a_rows = [av_delisted(av_http, av_key, d) for d in AV_YEAR_ENDS] if av_http is not None and av_key else []
        av_all = pd.concat(a_rows, ignore_index=True) if a_rows else pd.DataFrame(columns=CANDIDATE_COLUMNS)
        live = store.read_table(SYMBOLS_TABLE) if store.has_table(SYMBOLS_TABLE) else None
        cands = merge_candidates(m_rows, av_all, live)
        if not have.empty:  # keep the status of candidates already fetched
            done = have.set_index(["ticker", "delist_date"])["status"]
            idx = pd.MultiIndex.from_frame(cands[["ticker", "delist_date"]])
            prior = done.reindex(idx).to_numpy()
            cands["status"] = [p if isinstance(p, str) and p != STATUS_PENDING else s
                               for p, s in zip(prior, cands["status"], strict=True)]
        store.write_table(CANDIDATES_TABLE, cands, ["ticker", "delist_date"])
        say(f"enumerated {len(cands)} candidates (massive {len(m_rows)}, alphavantage {len(av_all)})")
    cands = store.read_table(CANDIDATES_TABLE)
    cands["delist_date"] = pd.to_datetime(cands["delist_date"]).dt.date
    pending = cands.loc[cands["status"] == STATUS_PENDING]
    if limit is not None:
        pending = pending.head(limit)
    stats = {"candidates": len(cands), "pending": len(pending), "ok": 0, "no_bars": 0, "bars": 0}
    for i in range(0, len(pending), FETCH_CHUNK):
        chunk = pending.iloc[i : i + FETCH_CHUNK]
        tickers = sorted({t for t in chunk["ticker"]} | {t + BANKRUPT_SUFFIX for t in chunk["ticker"]})
        bars = alpaca.daily_bars(tickers, ALPACA_HISTORY_START, max(chunk["delist_date"]) + timedelta(days=15))
        listings, metas, frames, status = [], [], [], []
        for cand in chunk.to_dict("records"):
            seg = _pick_series(bars, cand["ticker"], cand["delist_date"]) if not bars.empty else pd.DataFrame()
            if seg.empty:
                status.append({**cand, "status": STATUS_NO_BARS})
                continue
            key = entity_key(cand["ticker"], _days(seg).max())
            frames.append(seg.assign(symbol=key))
            listings.append(listing_row(key, seg, cand, cand["source"]))
            metas.append(cand)
            status.append({**cand, "status": STATUS_OK, "key": key})
        if frames:
            stats["bars"] += store.write_bars(pd.concat(frames, ignore_index=True))
        write_entities(store, listings, metas)
        store.write_table(CANDIDATES_TABLE, pd.DataFrame(status), ["ticker", "delist_date"])
        stats["ok"] += len(listings)
        stats["no_bars"] += len(status) - len(listings)
        say(f"delisted ingest: {min(i + FETCH_CHUNK, len(pending))}/{len(pending)} candidates, {stats['bars']} bars")
    store.write_table("ingest_meta", pd.DataFrame([{
        "key": "delisted_extension",
        "value": f"{stats['ok']} entities, {stats['bars']} bars this run; rules {DELISTED_RULES_VERSION}",
    }]), ["key"])
    return stats


__all__ = [
    "DELISTED_RULES_VERSION", "ENTITY_SEP", "classify_delisting", "cut_entity", "delisting_returns", "drop_entity_keys",
    "entity_key", "is_entity_key", "merge_candidates", "parse_av_listing", "run_delisted_ingest", "split_key",
]
