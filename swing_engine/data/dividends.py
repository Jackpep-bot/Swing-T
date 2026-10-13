"""Cash dividends from Alpaca's free corporate-actions feed, the dividend-month signal and a total-return store.

Spike, real calls with the paper key on the Basic (free) plan, 2026-10-13:
* `GET data.alpaca.markets/v1/corporate-actions?types=cash_dividend&start=&end=` serves every symbol's cash
  dividends back to 2016-01 without a `symbols` filter (2019-03-01: 269 rows, one page at limit 1000); 200 calls/min.
* `rate` is dollars per share **as paid**: AAPL 0.82 on 2020-08-07 and 0.205 on 2020-11-06, either side of its
  4:1 split. The store's bars are split-adjusted, so a rate is divided by every later split ratio (`splits` table).
* `symbol` is the ticker **on the ex-date**: BK paid under BK until its May 2026 rename, and the 2025 rows under
  BNY belong to the bond fund that held that ticker then. `mapped` moves each row to the store's key for that
  security on that day (rename merges and dropped ticker-holders from `repairs`, delisted keys from `listings`).

Tables (in the market store): `dividends` (id, symbol, ex_date, rate, special, foreign, process / payable / record
date), as reported and never rewritten; `dividend_ingest_meta` marks each finished month.

Signal (`join_dividends` -> `div_season`, the Chen-Zimmermann `DivSeason` rule after Hartzmark & Solomon 2013): on a
month's last session, a common stock is a predicted payer for the next month when it went ex-dividend 3, 6, 9 or 12
months before that month (quarterly payers), 6 or 12 (semi-annual) or 12 (annual). Frequency is read from the
regular dividends of the trailing 12 months: 6 or more ex-months = monthly payer, left out.

Total return (`total_return_adjust`): research copies only. The engine has no dividend cash, so on the ex-day the
price drop would be scored as a loss; a copy of the store with dividend-back-adjusted bars makes a replay's P&L
(and SPY's, the benchmark) total return with no engine change.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import structlog

from ._http import Http
from .calendar import trading_days
from .delisted import ENTITY_SEP, LISTINGS_TABLE, SYMBOLS_TABLE, split_key
from .news import _month_bounds, month_list
from .store import Store

log = structlog.get_logger(__name__)

URL = "https://data.alpaca.markets/v1/corporate-actions"
PAGE_LIMIT = 1000  # API maximum per page
CALLS_PER_MIN = 180  # Basic plan: 200/min
FIRST_DAY = date(2016, 1, 1)  # floor of the feed (and of the store's bars)
TABLE, META_TABLE = "dividends", "dividend_ingest_meta"
SYMBOL_COL, TS_COL = "symbol", "ts"
SCHEMA: dict[str, str] = {
    "id": "VARCHAR", "symbol": "VARCHAR", "ex_date": "DATE", "rate": "DOUBLE", "special": "BOOLEAN",
    "foreign": "BOOLEAN", "process_date": "DATE", "payable_date": "DATE", "record_date": "DATE",
}
META_SCHEMA: dict[str, str] = {"month": "VARCHAR", "status": "VARCHAR", "rows": "BIGINT", "pages": "INTEGER",
                               "fetched_at": "TIMESTAMP", "error": "VARCHAR"}
STATUS_OK, STATUS_PARTIAL, STATUS_ERROR = "ok", "partial", "error"
REPAIRS_TABLE, SPLITS_TABLE, ADJUSTED_TABLE = "repairs", "splits", "total_return_adjusted"
MERGE = "merge_duplicate"  # data.repair action
COMMON_STOCK = "CS"  # symbols.type of a US common stock (Chen-Zimmermann: CRSP share codes 10 and 11)
DIV_SEASON = "div_season"
LOOKBACK_MONTHS = 12
MONTHLY_MIN_EX_MONTHS = 6  # this many ex-months in the trailing 12: a monthly payer, left out
#: months before the target month in which a payer of each frequency went ex (frequency = ex-months in the last 12)
SEASON_LAGS = {1: (12,), 2: (6, 12), 3: (3, 6, 9, 12), 4: (3, 6, 9, 12), 5: (3, 6, 9, 12)}
#: A dividend worth this share of the previous close or more is not applied to the total-return bars (a bad rate,
#: or a liquidating payment): counted and logged.
MAX_YIELD_PER_DIVIDEND = 0.25
MAX_EX_LAG_DAYS = 7


class AlpacaDividends:
    """Thin REST client for the cash-dividend corporate actions; keys go in headers only."""

    def __init__(self, api_key: str, secret_key: str, *, http: Http | None = None,
                 calls_per_min: float = CALLS_PER_MIN) -> None:
        if http is None and not (api_key and secret_key):
            raise ValueError("alpaca dividends: ALPACA_API_KEY / ALPACA_SECRET_KEY are required")
        self.http = http or Http(rate_per_min=calls_per_min, headers={
            "APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key})

    def page(self, start: date, end: date, token: str | None = None) -> dict[str, Any]:
        """Cash dividends of every symbol with start <= ex_date <= end."""
        params: dict[str, Any] = {"types": "cash_dividend", "start": start.isoformat(), "end": end.isoformat(),
                                  "limit": PAGE_LIMIT, "sort": "asc"}
        if token:
            params["page_token"] = token
        return self.http.get_json(URL, params=params)


def parse_page(payload: dict[str, Any]) -> pd.DataFrame:
    rows = ((payload or {}).get("corporate_actions") or {}).get("cash_dividends") or []
    frame = pd.DataFrame(rows).reindex(columns=list(SCHEMA))
    for col in ("ex_date", "process_date", "payable_date", "record_date"):
        frame[col] = pd.to_datetime(frame[col], errors="coerce").dt.date
    frame["rate"] = pd.to_numeric(frame["rate"], errors="coerce")
    frame["symbol"] = frame["symbol"].astype(str).str.upper().str.strip()
    return frame.loc[frame["id"].notna() & frame["ex_date"].notna() & (frame["rate"] > 0)]


def run_dividend_ingest(store: Store, client: Any, *, start: date = FIRST_DAY, today: date | None = None,
                        progress: Callable[[str], None] | None = None) -> dict[str, Any]:
    """Fetch every month from ``start`` not yet ingested OK into ``dividends`` (upsert on the feed's id). A
    finished month is never fetched again; the current month is 'partial' and refetched every run."""
    today = today or datetime.now(UTC).date()
    meta = store.read_table(META_TABLE)
    done = set() if meta.empty else set(meta.loc[meta["status"] == STATUS_OK, "month"])
    totals = {"months": 0, "pages": 0, "rows": 0, "failed": 0}
    for mo in [m for m in month_list(start, today) if m not in done]:
        lo, hi = _month_bounds(mo)
        last = min((hi - timedelta(days=1)).date(), today)
        row: dict[str, Any] = {"month": mo, "rows": 0, "pages": 0, "error": None,
                               "fetched_at": datetime.now(UTC).replace(tzinfo=None)}
        try:
            token: str | None = None
            while True:
                payload = client.page(lo.date(), last, token)
                row["pages"] += 1
                row["rows"] += store.write_table(TABLE, parse_page(payload), ["id"], schema=SCHEMA)
                token = payload.get("next_page_token")
                if not token:
                    break
            row["status"] = STATUS_OK if hi.date() <= today else STATUS_PARTIAL
            totals["months"] += 1
        except Exception as exc:  # noqa: BLE001 - one bad month must not stop the run; it is retried next time
            row["status"], row["error"] = STATUS_ERROR, str(exc)[:500]
            totals["failed"] += 1
            log.warning("dividend_ingest_month_failed", month=mo, error=row["error"])
        totals["pages"] += row["pages"]
        totals["rows"] += row["rows"]
        store.write_table(META_TABLE, pd.DataFrame([row], columns=list(META_SCHEMA)), ["month"], schema=META_SCHEMA)
        if progress:
            progress(f"dividends: {mo} {row['status']} {row['pages']} pages {row['rows']} rows")
    log.info("dividend_ingest_done", **totals)
    return {**totals, "months_done_before": len(done)}


# ============================================================================================== mapping
def store_symbols(div: pd.DataFrame, repairs: pd.DataFrame | None = None,
                  listings: pd.DataFrame | None = None) -> pd.Series:
    """The store key that holds each dividend's security on its ex-date (None = no such series: dropped).

    A delisted key ``TICKER~YYYYMMDD`` when the ex-date falls inside that entity's bars. A rename merged by
    ``data.repair.merge_duplicates`` moves the old ticker's rows (or the rows of a merged key's ticker) up to the
    merge's last day to the surviving symbol, repeatedly for a chain; rows reported under the surviving ticker up
    to that day are dropped, because the ticker was not this security yet (BNY was a bond fund until 2026-05-20)."""
    sym = div["symbol"].astype(str).to_numpy(dtype=object)
    day = pd.to_datetime(div["ex_date"]).dt.date.to_numpy()
    out = sym.copy()
    spans: dict[str, list[tuple[date, date, str]]] = {}
    for r in (listings.itertuples(index=False) if listings is not None else ()):
        if ENTITY_SEP in str(r.key) and not pd.isna(r.first_bar) and not pd.isna(r.last_bar):
            spans.setdefault(str(r.ticker), []).append(
                (pd.Timestamp(r.first_bar).date(), pd.Timestamp(r.last_bar).date(), str(r.key)))
    moves: dict[str, list[tuple[date, str]]] = {}
    blocked: dict[str, date] = {}
    if repairs is not None and len(repairs):
        live = repairs.loc[(repairs["action"] == MERGE) & ~repairs["reverted"].fillna(False).astype(bool)]
        for r in live.itertuples(index=False):
            end, old, new = pd.Timestamp(r.date_to).date(), str(r.symbol), str(r.new_symbol)
            for name in {old, split_key(old)[0]}:
                moves.setdefault(name, []).append((end, new))
            if split_key(old)[0] != new:
                blocked[new] = max(end, blocked.get(new, end))
    for i, (s, d) in enumerate(zip(sym, day, strict=True)):
        if s in blocked and d <= blocked[s]:
            out[i] = None
            continue
        out[i] = next((key for lo, hi, key in spans.get(s, ()) if lo <= d <= hi), s)
        for _ in range(4):  # a chain of renames is short
            hit = next((new for end, new in moves.get(out[i], ()) if d <= end and new != out[i]), None)
            if hit is None:
                break
            out[i] = hit
    return pd.Series(out, index=div.index, dtype=object)


def split_adjusted_rates(div: pd.DataFrame, splits: pd.DataFrame | None, symbol_col: str = "store_symbol") -> pd.Series:
    """``rate`` divided by the ratio of every split of the same symbol after the ex-date (the bars' own basis)."""
    rate = div["rate"].astype(float).copy()
    if splits is None or not len(splits):
        return rate
    by: dict[str, list[tuple[date, float]]] = {}
    for r in splits.itertuples(index=False):
        if r.ratio and np.isfinite(r.ratio) and r.ratio > 0:
            by.setdefault(str(r.symbol), []).append((pd.Timestamp(r.ex_date).date(), float(r.ratio)))
    days = pd.to_datetime(div["ex_date"]).dt.date
    for i, (s, d) in zip(div.index, zip(div[symbol_col], days, strict=True), strict=True):
        for split_day, ratio in by.get(str(s), ()):
            if split_day > d:
                rate.at[i] /= ratio
    return rate


def mapped(store: Any) -> pd.DataFrame:
    """``dividends`` with ``store_symbol`` (rows without one dropped) and the split-adjusted ``rate_adj``."""
    if not store.has_table(TABLE):
        return pd.DataFrame(columns=[*SCHEMA, "store_symbol", "rate_adj"])
    div = store.read_table(TABLE)
    read = lambda name: store.read_table(name) if store.has_table(name) else None  # noqa: E731
    div["store_symbol"] = store_symbols(div, read(REPAIRS_TABLE), read(LISTINGS_TABLE))
    div = div.loc[div["store_symbol"].notna()].reset_index(drop=True)
    div["rate_adj"] = split_adjusted_rates(div, read(SPLITS_TABLE))
    return div


# ============================================================================================== signal
def _month_index(days: pd.Series) -> pd.Series:
    d = pd.to_datetime(days)
    return d.dt.year * 12 + d.dt.month - 1


def season_table(div: pd.DataFrame, symbol_col: str = "store_symbol") -> pd.DataFrame:
    """``symbol, month`` (year x 12 + month - 1) pairs for which the symbol is a predicted payer, where ``month``
    is the month the prediction is made in (its last session); the predicted ex-month is ``month + 1``. Regular
    dividends only; only ex-months up to ``month`` are read."""
    reg = div.loc[~div["special"].fillna(False).astype(bool)]
    pairs = pd.DataFrame({"symbol": reg[symbol_col].astype(str), "m": _month_index(reg["ex_date"])}).drop_duplicates()
    out = []
    for sym, months in pairs.groupby("symbol", sort=False)["m"]:
        have = set(months.tolist())
        for m in range(min(have), max(have) + LOOKBACK_MONTHS + 1):  # m = the month the prediction is made in
            n = sum((m - k) in have for k in range(LOOKBACK_MONTHS))
            lags = SEASON_LAGS.get(n)
            if lags and any((m + 1 - lag) in have for lag in lags):
                out.append((sym, m))
    return pd.DataFrame(out, columns=["symbol", "month"])


def month_end_sessions(first: date, last: date) -> set[date]:
    """The last NYSE session of every calendar month that ends inside ``first..last``'s months (calendar, not data)."""
    lo = date(first.year, first.month, 1)
    hi = (pd.Timestamp(last) + pd.offsets.MonthEnd(0)).date()
    days = pd.Series(trading_days(lo, hi))
    return set(days.groupby([days.map(lambda d: (d.year, d.month))]).max().tolist())


def join_dividends(store: Any, panel: pd.DataFrame) -> pd.DataFrame:
    """``panel`` plus ``div_season``: 1.0 on a month's last NYSE session for a common stock that the rule predicts
    will go ex-dividend next month, 0.0 on that session otherwise, NaN on every other row (mid-month the month's
    ex-dates are not all known yet). Unchanged when the store has no ``dividends`` table."""
    has = getattr(store, "has_table", None)
    if panel is None or panel.empty or DIV_SEASON in panel.columns or not callable(has) or not has(TABLE):
        return panel
    div = mapped(store)
    common: set[str] | None = None
    if has(SYMBOLS_TABLE):
        syms = store.read_table(SYMBOLS_TABLE)
        common = set(syms.loc[syms["type"] == COMMON_STOCK, "symbol"].astype(str))
    season = season_table(div)
    keys = set(zip(season["symbol"], season["month"], strict=True))
    ts = pd.to_datetime(panel[TS_COL])
    days = (ts.dt.tz_localize(None) if ts.dt.tz is not None else ts).dt.normalize()  # the bar's own (New York) day
    ends = month_end_sessions(days.min().date(), days.max().date())
    at_end = days.dt.date.isin(ends).to_numpy()
    out = np.full(len(panel), np.nan)
    sym = panel[SYMBOL_COL].astype(str).to_numpy()
    month = _month_index(days).to_numpy()
    idx = np.flatnonzero(at_end)
    out[idx] = [float((sym[i], int(month[i])) in keys and (common is None or sym[i] in common)) for i in idx]
    return panel.assign(**{DIV_SEASON: out})


# ============================================================================================== total return
def total_return_adjust(store: Any, live_path: str | None = None) -> dict[str, Any]:
    """Back-adjust every bar of ``store`` for the cash dividends that went ex after it: open, high, low, close,
    vwap and adj_close are multiplied by the product of ``1 - rate / previous close`` over the later ex-dates
    (the ex-day itself is not adjusted), so close-to-close returns are total returns. A dividend is applied on the
    first bar on or after its ex-date. Research copies only: refuses ``live_path`` and a store already adjusted."""
    path = str(getattr(store, "path", "") or "")
    if live_path and path and str(live_path) == path:
        raise ValueError("total_return_adjust: refusing to rewrite the live store's bars")
    if store.has_table(ADJUSTED_TABLE):
        raise ValueError("total_return_adjust: this store's bars are already total-return adjusted")
    div = mapped(store)[["store_symbol", "ex_date", "rate_adj"]].rename(columns={"store_symbol": "symbol"})
    con = store._con
    con.register("_div", div)
    con.execute("BEGIN TRANSACTION")
    try:
        # each dividend lands on the symbol's first bar on or after its ex-date (within MAX_EX_LAG_DAYS: a later
        # bar is across a halt or a change of ticker owner), with the close of the bar before it
        con.execute(
            "CREATE TEMP TABLE _f AS WITH b AS (SELECT symbol, ts, ts::DATE AS day, lag(close) OVER (PARTITION BY symbol "
            "ORDER BY ts) AS prev FROM bars WHERE symbol IN (SELECT DISTINCT symbol FROM _div)) "
            "SELECT d.symbol, b.ts, sum(d.rate_adj) AS rate, any_value(b.prev) AS prev FROM _div d ASOF JOIN b "
            "ON d.symbol = b.symbol AND d.ex_date <= b.day WHERE b.prev > 0 AND date_diff('day', d.ex_date, b.day) <= ? "
            "GROUP BY d.symbol, b.ts", [MAX_EX_LAG_DAYS])
        skipped = int(con.execute("SELECT count(*) FROM _f WHERE rate / prev >= ?", [MAX_YIELD_PER_DIVIDEND]).fetchone()[0])
        con.execute("DELETE FROM _f WHERE rate / prev >= ?", [MAX_YIELD_PER_DIVIDEND])
        applied = int(con.execute("SELECT count(*) FROM _f").fetchone()[0])
        con.execute(
            "CREATE TEMP TABLE _adj AS SELECT b.symbol, b.ts, exp(sum(coalesce(ln(1 - f.rate / f.prev), 0)) OVER "
            "(PARTITION BY b.symbol) - sum(coalesce(ln(1 - f.rate / f.prev), 0)) OVER (PARTITION BY b.symbol ORDER BY b.ts "
            "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) AS k FROM bars b LEFT JOIN _f f ON f.symbol = b.symbol "
            "AND f.ts = b.ts WHERE b.symbol IN (SELECT DISTINCT symbol FROM _f)")
        con.execute("UPDATE bars SET open = open * a.k, high = high * a.k, low = low * a.k, close = close * a.k, "
                    "vwap = vwap * a.k, adj_close = adj_close * a.k FROM _adj a WHERE bars.symbol = a.symbol "
                    "AND bars.ts = a.ts AND a.k < 1")
        con.execute(f"CREATE TABLE {ADJUSTED_TABLE} AS SELECT now() AS applied_at, ?::BIGINT AS dividends, "
                    "?::BIGINT AS skipped", [applied, skipped])
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.unregister("_div")
    log.info("total_return_adjusted", dividends=applied, skipped=skipped)
    return {"dividends": applied, "skipped": skipped, "dividend_rows": len(div)}


__all__ = ["AlpacaDividends", "DIV_SEASON", "TABLE", "join_dividends", "mapped", "parse_page", "run_dividend_ingest",
           "season_table", "split_adjusted_rates", "store_symbols", "total_return_adjust"]
