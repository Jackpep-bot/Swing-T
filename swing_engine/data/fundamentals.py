"""Free point-in-time fundamentals from SEC EDGAR (docs/catalog/CATALOG.md "Cross-cutting work" item 2 and
"What cannot be done with free data"; catalog slugs `earnings_dates_point_in_time`, `pead_sue`,
`revenue_surprise`, `gross_cash_profitability`, `quality_minus_junk`, `ibd_eps_rating`, `ibd_smr_rating`,
`high_turnover_short_term_momentum`, `historical_earnings_reaction_stats` in docs/catalog/catalog.json).

Two store tables, both written by `run_edgar_ingest` (`swing ingest-edgar`):

* `earnings_dates` (symbol, cik, accepted_at, filing_date, accession, form, session): 8-K filings carrying
  Item 2.02, stamped with the EDGAR acceptance datetime. `session` is the first session whose close can react
  (`data.edgar.earnings_session`: accepted after the close maps to the next session).
* `fundamentals` (symbol, cik, concept, period_end, fp, form, filed, value, ...): XBRL companyfacts values
  from 10-Q / 10-K filings, stamped with the filing's `filed` date.

Point-in-time: every `*_asof(day)` helper uses only rows with `filed <= day` (earnings: `session <= day`).
`fundamental_features` (the panel join) is stricter: companyfacts `filed` has no time of day, so a filing
becomes usable from the session *after* its filed date. Every number here is read from a filing or computed
by this code, never by the LLM.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
import structlog

from ._common import TZ, as_date, session_ts
from .calendar import next_trading_day, trading_days
from .edgar import CIK_WIDTH, EARNINGS_COLUMNS, Edgar
from .store import Store

log = structlog.get_logger(__name__)

FUNDAMENTALS_VERSION = "2026.10.07"

# ---- tables ------------------------------------------------------------------------------------------------
EARNINGS_TABLE = "earnings_dates"
EARNINGS_KEYS: list[str] = ["symbol", "accession"]
EARNINGS_SCHEMA: dict[str, str] = {
    "symbol": "VARCHAR",
    "cik": "VARCHAR",
    "accepted_at": "TIMESTAMPTZ",
    "filing_date": "DATE",
    "accession": "VARCHAR",
    "form": "VARCHAR",
    "session": "DATE",
}
FUNDAMENTALS_TABLE = "fundamentals"
FUNDAMENTALS_COLUMNS: list[str] = [
    "symbol", "cik", "concept", "period_end", "fp", "form", "filed", "value",
    "period_start", "duration_days", "fy", "tag", "accession",
]
FUNDAMENTALS_KEYS: list[str] = ["symbol", "concept", "period_end", "duration_days", "accession"]
FUNDAMENTALS_SCHEMA: dict[str, str] = {
    "symbol": "VARCHAR",
    "cik": "VARCHAR",
    "concept": "VARCHAR",
    "period_end": "DATE",
    "fp": "VARCHAR",
    "form": "VARCHAR",
    "filed": "DATE",
    "value": "DOUBLE",
    "period_start": "DATE",
    "duration_days": "INTEGER",  # 0 for instants (balance sheet, share counts)
    "fy": "INTEGER",
    "tag": "VARCHAR",
    "accession": "VARCHAR",
}
META_TABLE = "edgar_ingest_meta"
#: `fundamental_events` cached per (symbol, filed): rebuilt after each ingest so panel joins are a merge_asof.
EVENTS_TABLE = "fundamental_events"
EVENTS_KEYS: list[str] = ["symbol", "filed"]
META_KEYS: list[str] = ["cik"]
EIGHTK_META_TABLE = "eightk_ingest_meta"  # resume table of `swing ingest-edgar --8k-only` (same schema)
META_SCHEMA: dict[str, str] = {
    "cik": "VARCHAR",
    "symbols": "VARCHAR",
    "fetched_on": "DATE",
    "status": "VARCHAR",
    "earnings_rows": "INTEGER",
    "fundamentals_rows": "INTEGER",
    "error": "VARCHAR",
}
STATUS_OK = "ok"
STATUS_ERROR = "error"
#: a CIK fetched successfully within this many calendar days is skipped by the next ingest (resumable runs).
DEFAULT_REFRESH_DAYS = 7
PROGRESS_EVERY = 25  # CIKs between progress lines
SEC_TICKER_CLASS_SEP = "-"  # SEC writes BRK-B; bar vendors write BRK.B
STORE_TICKER_CLASS_SEP = "."

# ---- XBRL concepts: canonical name -> (taxonomy, tag, unit) in priority order --------------------------------
EPS_DILUTED = "eps_diluted"
REVENUE = "revenue"
GROSS_PROFIT = "gross_profit"
OPERATING_CASH_FLOW = "operating_cash_flow"  # 10-Q values are year-to-date durations, stored as reported
TOTAL_ASSETS = "total_assets"
TOTAL_EQUITY = "total_equity"
SHARES_OUTSTANDING = "shares_outstanding"
CONCEPT_TAGS: dict[str, tuple[tuple[str, str, str], ...]] = {
    EPS_DILUTED: (("us-gaap", "EarningsPerShareDiluted", "USD/shares"),),
    REVENUE: (
        ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax", "USD"),
        ("us-gaap", "Revenues", "USD"),
        ("us-gaap", "SalesRevenueNet", "USD"),
        ("us-gaap", "RevenueFromContractWithCustomerIncludingAssessedTax", "USD"),
    ),
    GROSS_PROFIT: (("us-gaap", "GrossProfit", "USD"),),
    OPERATING_CASH_FLOW: (("us-gaap", "NetCashProvidedByUsedInOperatingActivities", "USD"),),
    TOTAL_ASSETS: (("us-gaap", "Assets", "USD"),),
    TOTAL_EQUITY: (
        ("us-gaap", "StockholdersEquity", "USD"),
        ("us-gaap", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest", "USD"),
    ),
    SHARES_OUTSTANDING: (("dei", "EntityCommonStockSharesOutstanding", "shares"),),
}
#: concepts reported once per share class on the cover page: entries sharing (end, accn) are summed.
SUMMED_CONCEPTS: frozenset[str] = frozenset({SHARES_OUTSTANDING})
FUNDAMENTAL_FORMS: frozenset[str] = frozenset({"10-Q", "10-K", "10-Q/A", "10-K/A"})

# ---- period arithmetic ---------------------------------------------------------------------------------------
QUARTER_MIN_DAYS = 80  # a 13-week quarter is 91 days, 52/53-week fiscal years shift it by a week
QUARTER_MAX_DAYS = 100
ANNUAL_MIN_DAYS = 350
ANNUAL_MAX_DAYS = 380
QUARTERS_PER_YEAR = 4
YEAR_AGO_MIN_DAYS = 350  # the seasonal lag (q-4) must end 350..380 days before q
YEAR_AGO_MAX_DAYS = 380
TTM_MAX_SPAN_DAYS = 300  # first-to-last period_end of a TTM window of 4 consecutive quarters (~273 days)

# ---- surprise (seasonal random walk; Foster-Olsen-Shevlin 1984, Livnat-Mendenhall 2006) ------------------------
SURPRISE_STD_QUARTERS = 8  # std of (X_q - X_{q-4}) over the preceding 8 quarters
SURPRISE_MIN_QUARTERS = 4  # fewer valid preceding differences => NaN
SURPRISE_STD_DDOF = 1

# ---- earnings-calendar features ----------------------------------------------------------------------------------
EARNINGS_WINDOW_SESSIONS = 2  # announcement session and the next one

# ---- earnings seasonality (Chang, Hartzmark, Solomon & Soltes 2017; docs/strategies/earnings_seasonality.md) -----
SEASON_WINDOW = 20  # quarters t-23 .. t-4 are ranked
SEASON_SKIP = 3  # the latest three known quarters (t-3 .. t-1) are not in the ranked window
SEASON_STEP = 4  # same fiscal quarter: t-4, t-8, ..., t-20
EXPECTED_LAG_DAYS = 364  # expected announcement = the announcement 52 weeks earlier (keeps the weekday)
QUARTER_DAYS = 91  # end of the upcoming quarter ~ latest known quarter end + 91 days
MAX_REPORT_LAG_DAYS = 90  # the expected announcement must fall 0..90 days after the upcoming quarter's end

FEATURE_COLUMNS: list[str] = [
    "sue", "rev_surprise", "gross_prof", "shares_outstanding", "turnover", "days_since_earnings",
    "is_earnings_window", "days_since_filing", "earn_season", "sessions_to_expected_earnings",
]
#: per-filing values cached in EVENTS_TABLE (`fundamental_events`)
EVENT_VALUE_COLUMNS: list[str] = ["sue", "rev_surprise", "gross_prof", "shares_outstanding", "earn_season",
                                  "eps_last_q_end"]


# =================================================================================================== parsing
def parse_companyfacts(payload: Mapping[str, Any] | None, symbols: Iterable[str], cik: str | None = None) -> pd.DataFrame:
    """Long `fundamentals` rows for the concepts in CONCEPT_TAGS from one companyfacts payload (10-Q/10-K only),
    one copy per symbol sharing the CIK. Per (period, duration, accession) the highest-priority tag wins."""
    syms = sorted({s.upper().strip() for s in symbols if s})
    if not payload or not syms:
        return pd.DataFrame(columns=FUNDAMENTALS_COLUMNS)
    cik_s = str(cik if cik is not None else payload.get("cik", "")).zfill(CIK_WIDTH)
    facts = payload.get("facts") or {}
    rows: list[dict[str, Any]] = []
    for concept, tags in CONCEPT_TAGS.items():
        chosen: dict[tuple[Any, ...], dict[str, Any]] = {}
        for priority, (taxonomy, tag, unit) in enumerate(tags):
            try:
                entries = facts[taxonomy][tag]["units"][unit]
            except (KeyError, TypeError):
                continue
            summed: dict[tuple[Any, ...], dict[str, Any]] = {}
            seen: set[tuple[Any, ...]] = set()
            for e in entries:
                if not isinstance(e, dict) or e.get("val") is None or not e.get("end") or not e.get("filed"):
                    continue
                if str(e.get("form", "")) not in FUNDAMENTAL_FORMS:
                    continue
                end = as_date(e["end"])
                start = as_date(e["start"]) if e.get("start") else None
                duration = (end - start).days + 1 if start is not None else 0
                key = (end, duration, str(e.get("accn", "")))
                sig = (*key, e.get("val"), e.get("fp"), e.get("fy"))
                if sig in seen:  # exact duplicate (frame re-statement of the same fact)
                    continue
                seen.add(sig)
                row = {
                    "concept": concept, "period_end": end, "fp": e.get("fp"), "form": e.get("form"),
                    "filed": as_date(e["filed"]), "value": float(e["val"]), "period_start": start,
                    "duration_days": duration, "fy": e.get("fy"), "tag": f"{taxonomy}:{tag}", "accession": key[2],
                    "_priority": priority,
                }
                if key in summed and concept in SUMMED_CONCEPTS:
                    summed[key]["value"] += row["value"]
                else:
                    summed[key] = row
            for key, row in summed.items():
                if key not in chosen or row["_priority"] < chosen[key]["_priority"]:
                    chosen[key] = row
        for row in chosen.values():
            row.pop("_priority")
            for sym in syms:
                rows.append({**row, "symbol": sym, "cik": cik_s})
    df = pd.DataFrame(rows, columns=FUNDAMENTALS_COLUMNS)
    if df.empty:
        return df
    return df.sort_values(["symbol", "concept", "period_end", "filed"], kind="mergesort").reset_index(drop=True)


# ============================================================================================ store readers
def _symbols_where(symbols: Iterable[str] | None) -> tuple[str | None, list[Any]]:
    if symbols is None:
        return None, []
    return "symbol IN (SELECT unnest(?))", [sorted({s.upper().strip() for s in symbols})]


def _dates(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.date


def read_earnings(store: Store, symbols: Iterable[str] | None = None) -> pd.DataFrame:
    where, params = _symbols_where(symbols)
    df = store.read_table(EARNINGS_TABLE, where, params, order_by="symbol, accepted_at")
    if df.empty:
        return pd.DataFrame(columns=EARNINGS_COLUMNS)
    df["accepted_at"] = pd.to_datetime(df["accepted_at"], utc=True).dt.tz_convert(TZ)
    df["session"] = _dates(df["session"])
    df["filing_date"] = _dates(df["filing_date"])
    return df


def read_fundamentals(store: Store, symbols: Iterable[str] | None = None) -> pd.DataFrame:
    where, params = _symbols_where(symbols)
    df = store.read_table(FUNDAMENTALS_TABLE, where, params, order_by="symbol, concept, period_end, filed")
    if df.empty:
        return pd.DataFrame(columns=FUNDAMENTALS_COLUMNS)
    for c in ("period_end", "filed", "period_start"):
        df[c] = _dates(df[c])
    return df


def earnings_dates_asof(store: Store, symbols: Iterable[str] | None, day: date | str) -> pd.DataFrame:
    """Earnings announcements known by the close of `day`: reaction session on or before `day` (an 8-K accepted
    after the close of `day`, or any later filing, is invisible)."""
    d = as_date(day)
    df = read_earnings(store, symbols)
    return df[df["session"] <= d].reset_index(drop=True)


# =============================================================================== point-in-time computations
def _visible(fund: pd.DataFrame, symbol: str, concept: str, day: date) -> pd.DataFrame:
    """Rows for one symbol/concept filed on or before `day`; per (period_end, duration) the latest filing wins
    (the most recent value known on `day`, restatements included)."""
    rows = fund[(fund["symbol"] == symbol.upper()) & (fund["concept"] == concept)]
    rows = rows[pd.Series([f <= day for f in rows["filed"]], index=rows.index, dtype=bool)]
    if rows.empty:
        return rows
    rows = rows.sort_values(["filed", "accession"], kind="mergesort")
    return rows.drop_duplicates(subset=["period_end", "duration_days"], keep="last")


def quarterly_values(fund: pd.DataFrame, symbol: str, concept: str, day: date | str) -> pd.Series:
    """Fiscal-quarter values of a flow concept known on `day`, indexed by period_end (ascending). Q4 is derived
    as annual minus the three reported quarters of that fiscal year when the 10-K gives only the annual figure."""
    d = as_date(day)
    rows = _visible(fund, symbol, concept, d)
    if rows.empty:
        return pd.Series(dtype="float64")
    dur = rows["duration_days"].astype(int)
    q = rows[(dur >= QUARTER_MIN_DAYS) & (dur <= QUARTER_MAX_DAYS)]
    quarters: dict[date, float] = {r.period_end: float(r.value) for r in q.itertuples()}
    annual = rows[(dur >= ANNUAL_MIN_DAYS) & (dur <= ANNUAL_MAX_DAYS)]
    for a in annual.itertuples():
        if a.period_end in quarters or a.period_start is None:
            continue
        inside = [e for e in quarters if a.period_start < e <= a.period_end - timedelta(days=QUARTER_MIN_DAYS)]
        if len(inside) == QUARTERS_PER_YEAR - 1:
            quarters[a.period_end] = float(a.value) - sum(quarters[e] for e in inside)
    return pd.Series(quarters, dtype="float64").sort_index()


def _year_ago(index: list[date], end: date) -> date | None:
    for e in reversed(index):
        gap = (end - e).days
        if YEAR_AGO_MIN_DAYS <= gap <= YEAR_AGO_MAX_DAYS:
            return e
    return None


def seasonal_surprise(values: pd.Series) -> float:
    """Standardized unexpected value of the latest quarter under a seasonal random walk:
    (X_q - X_{q-4}) / std(X_i - X_{i-4}) over the SURPRISE_STD_QUARTERS quarters preceding q. NaN when the
    year-ago quarter is missing, fewer than SURPRISE_MIN_QUARTERS differences exist, or the std is zero."""
    if values.empty:
        return float("nan")
    idx = list(values.index)
    diffs: dict[date, float] = {}
    for e in idx:
        prior = _year_ago([p for p in idx if p < e], e)
        if prior is not None:
            diffs[e] = float(values[e] - values[prior])
    latest = idx[-1]
    if latest not in diffs:
        return float("nan")
    preceding = [diffs[e] for e in idx[:-1][-SURPRISE_STD_QUARTERS:] if e in diffs]
    if len(preceding) < SURPRISE_MIN_QUARTERS:
        return float("nan")
    std = float(np.std(preceding, ddof=SURPRISE_STD_DDOF))
    if not np.isfinite(std) or std <= 0:
        return float("nan")
    return diffs[latest] / std


def earnings_seasonality(values: pd.Series) -> float:
    """Chang-Hartzmark-Solomon-Soltes EarnRank for the quarter after the latest one in ``values`` (quarter t, with
    t-1 the latest known): rank the 20 quarters t-23 .. t-4 from largest (1) to smallest and average the ranks of
    t-4, t-8, t-12, t-16, t-20. Low = the upcoming fiscal quarter is historically strong. NaN unless the latest
    23 quarters are consecutive (each quarter end QUARTER_MIN_DAYS..QUARTER_MAX_DAYS after the previous)."""
    need = SEASON_WINDOW + SEASON_SKIP
    if len(values) < need:
        return float("nan")
    last = values.iloc[-need:]
    gaps = np.diff(np.array(last.index, dtype="datetime64[D]")).astype(int)
    if ((gaps < QUARTER_MIN_DAYS) | (gaps > QUARTER_MAX_DAYS)).any():
        return float("nan")
    ranks = last.iloc[:SEASON_WINDOW].rank(ascending=False).to_numpy()
    return float(ranks[SEASON_WINDOW - 1::-SEASON_STEP].mean())


def sue_asof(fund: pd.DataFrame, symbol: str, day: date | str) -> float:
    """SUE on diluted EPS for the latest quarter filed on or before `day` (catalog `pead_sue`)."""
    return seasonal_surprise(quarterly_values(fund, symbol, EPS_DILUTED, day))


def revenue_surprise_asof(fund: pd.DataFrame, symbol: str, day: date | str) -> float:
    """Standardized unexpected revenue, same seasonal random walk (catalog `revenue_surprise`)."""
    return seasonal_surprise(quarterly_values(fund, symbol, REVENUE, day))


def _latest_instant(fund: pd.DataFrame, symbol: str, concept: str, day: date) -> float:
    rows = _visible(fund, symbol, concept, day)
    rows = rows[rows["duration_days"].astype(int) == 0] if not rows.empty else rows
    if rows.empty:
        return float("nan")
    return float(rows.sort_values(["period_end", "filed"], kind="mergesort").iloc[-1]["value"])


def gross_profitability_asof(fund: pd.DataFrame, symbol: str, day: date | str) -> float:
    """TTM gross profit (last 4 quarters) / latest total assets, both filed on or before `day`
    (Novy-Marx 2013; catalog `gross_cash_profitability`)."""
    d = as_date(day)
    gp = quarterly_values(fund, symbol, GROSS_PROFIT, d)
    if len(gp) < QUARTERS_PER_YEAR:
        return float("nan")
    last = gp.iloc[-QUARTERS_PER_YEAR:]
    if (last.index[-1] - last.index[0]).days > TTM_MAX_SPAN_DAYS:
        return float("nan")
    assets = _latest_instant(fund, symbol, TOTAL_ASSETS, d)
    if not np.isfinite(assets) or assets <= 0:
        return float("nan")
    return float(last.sum()) / assets


def shares_outstanding_asof(fund: pd.DataFrame, symbol: str, day: date | str) -> float:
    """Cover-page shares outstanding (all classes summed) from the latest 10-Q/10-K filed on or before `day`."""
    return _latest_instant(fund, symbol, SHARES_OUTSTANDING, as_date(day))


def turnover_asof(fund: pd.DataFrame, symbol: str, day: date | str, volume: float) -> float:
    """Share turnover = `volume` / shares outstanding as of `day` (catalog `high_turnover_short_term_momentum`)."""
    shares = shares_outstanding_asof(fund, symbol, day)
    if not np.isfinite(shares) or shares <= 0:
        return float("nan")
    return float(volume) / shares


# ====================================================================================== panel-ready frames
def _norm_ts(values: pd.Series) -> pd.Series:
    ts = pd.to_datetime(values)
    if ts.dt.tz is None:
        ts = ts.dt.tz_localize(TZ)
    return ts.dt.tz_convert(TZ).dt.as_unit("us")


def _session_ordinals(start: date, end: date) -> np.ndarray:
    return np.array(trading_days(start, end), dtype="datetime64[D]")


def _sessions_since(ts: pd.Series, event_ts: pd.Series) -> pd.Series:
    """NYSE sessions from each row's `event_ts` session to its `ts` (0 on the event session); NaN without one."""
    out = pd.Series(np.nan, index=ts.index, dtype="float64")
    has = event_ts.notna()
    if has.any():
        def days(s: pd.Series) -> np.ndarray:
            return s.dt.tz_convert(TZ).dt.tz_localize(None).values.astype("datetime64[D]")

        ts_days, ev_days = days(ts[has]), days(event_ts[has])
        sessions = _session_ordinals(min(ev_days.min(), ts_days.min()).astype(date),
                                     max(ts_days.max(), ev_days.max()).astype(date))
        ts_ord = np.searchsorted(sessions, ts_days, side="right") - 1
        out[has] = (ts_ord - np.searchsorted(sessions, ev_days, side="left")).astype("float64")
    return out


def earnings_calendar_features(earnings: pd.DataFrame, index: pd.DataFrame) -> pd.DataFrame:
    """Per (symbol, ts) of `index`: `days_since_earnings` (sessions since the latest announcement session on or
    before ts; 0 on it), `is_earnings_window` (announcement session or the next one), `expected_earnings` (the
    earliest announcement session in the EXPECTED_LAG_DAYS calendar days up to ts, plus EXPECTED_LAG_DAYS, rolled
    to the next session; naive date) and `sessions_to_expected_earnings` (sessions from ts to it). NaN/False/NaT
    without a known announcement."""
    out = index[["symbol", "ts"]].reset_index(drop=True).copy()
    out["ts"] = _norm_ts(out["ts"])
    out["days_since_earnings"] = np.nan
    out["is_earnings_window"] = False
    out["expected_earnings"] = pd.NaT
    out["sessions_to_expected_earnings"] = np.nan
    if out.empty or earnings is None or earnings.empty:
        return out.reset_index(drop=True)
    ev = earnings[["symbol", "session"]].dropna().drop_duplicates()
    ev = ev.assign(ann_ts=[session_ts(s) for s in ev["session"]]).sort_values("ann_ts")
    left = out.reset_index(drop=True).reset_index(names="_row").sort_values("ts")
    merged = pd.merge_asof(left, ev[["symbol", "ann_ts"]], left_on="ts", right_on="ann_ts", by="symbol")
    merged = merged.sort_values("_row").reset_index(drop=True)
    days = _sessions_since(merged["ts"], merged["ann_ts"])
    merged["days_since_earnings"] = days
    merged["is_earnings_window"] = ((days >= 0) & (days < EARNINGS_WINDOW_SESSIONS)).astype(bool)
    exp = _expected_earnings(ev, merged)
    merged = merged.drop(columns=list(exp.columns)).join(exp)
    return merged[["symbol", "ts", "days_since_earnings", "is_earnings_window", "expected_earnings",
                   "sessions_to_expected_earnings"]]


def _expected_earnings(ev: pd.DataFrame, rows: pd.DataFrame) -> pd.DataFrame:
    """`expected_earnings` / `sessions_to_expected_earnings` for `rows` (symbol, ts) from announcement sessions `ev`
    (symbol, session): only announcements on or before each row's day are read."""
    lag = np.timedelta64(EXPECTED_LAG_DAYS, "D")
    day = rows["ts"].dt.tz_convert(TZ).dt.tz_localize(None).values.astype("datetime64[D]")
    expected = np.full(len(rows), np.datetime64("NaT", "D"), dtype="datetime64[D]")
    by_sym = {s: np.sort(np.array(g, dtype="datetime64[D]")) for s, g in ev.groupby("symbol")["session"]}
    for sym, idx in rows.groupby("symbol", sort=False).indices.items():
        ann = by_sym.get(sym)
        if ann is None:
            continue
        d = day[idx]
        j = np.searchsorted(ann, d - lag + np.timedelta64(1, "D"), side="left")  # earliest announcement a with a > d - 364 days
        ok = j < len(ann)
        a = ann[np.minimum(j, len(ann) - 1)]
        ok &= a <= d
        expected[idx[ok]] = a[ok] + lag
    out = pd.DataFrame({"expected_earnings": pd.to_datetime(expected),
                        "sessions_to_expected_earnings": np.nan}, index=rows.index)
    has = ~np.isnat(expected)
    if has.any():
        sessions = _session_ordinals(day.min().astype(date), expected[has].max().astype(date) + timedelta(days=10))
        to = np.searchsorted(sessions, expected[has], side="left") - np.searchsorted(sessions, day[has], side="left")
        out.loc[has, "sessions_to_expected_earnings"] = to.astype(float)
    return out


def fundamental_events(fund: pd.DataFrame, symbols: Iterable[str] | None = None) -> pd.DataFrame:
    """One row per (symbol, filed date): EVENT_VALUE_COLUMNS as known on that date (`earn_season` is the
    seasonality of the quarter after `eps_last_q_end`, the latest known EPS quarter end), plus `avail_ts` = the
    first session after the filed date (when the values become usable at a close)."""
    cols = ["symbol", "filed", "avail_ts", *EVENT_VALUE_COLUMNS]
    if fund is None or fund.empty:
        return pd.DataFrame(columns=cols)
    wanted = None if symbols is None else {s.upper() for s in symbols}
    rows: list[dict[str, Any]] = []
    for sym, sub in fund.groupby("symbol", sort=True):  # one pass over the table, not one scan per symbol
        if wanted is not None and sym not in wanted:
            continue
        for filed in sorted(set(sub["filed"])):
            eps = quarterly_values(sub, sym, EPS_DILUTED, filed)
            rows.append(
                {
                    "symbol": sym,
                    "filed": filed,
                    "avail_ts": session_ts(next_trading_day(filed)),
                    "sue": seasonal_surprise(eps),
                    "rev_surprise": revenue_surprise_asof(sub, sym, filed),
                    "gross_prof": gross_profitability_asof(sub, sym, filed),
                    "shares_outstanding": shares_outstanding_asof(sub, sym, filed),
                    "earn_season": earnings_seasonality(eps),
                    "eps_last_q_end": pd.Timestamp(eps.index[-1]) if len(eps) else pd.NaT,
                }
            )
    return pd.DataFrame(rows, columns=cols)


def fundamental_features(
    fund: pd.DataFrame, earnings: pd.DataFrame, index: pd.DataFrame, events: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Panel-ready frame keyed (symbol, ts) like `index` (which needs symbol, ts and, for turnover, volume):
    FEATURE_COLUMNS. Fundamentals become visible the session after their filed date; `days_since_filing` counts
    sessions from that first usable session (0 on it), so a gate on it keeps a stale quarter's `sue` out while
    `days_since_earnings` (8-K clock) already shows the new release; earnings-calendar columns follow
    `earnings_calendar_features`. ``events`` (a cached `fundamental_events` frame) skips recomputing them."""
    base = index[["symbol", "ts"]].reset_index(drop=True).copy()
    if base.empty:
        return base.assign(**{c: pd.Series(dtype="float64") for c in FEATURE_COLUMNS})
    base["ts"] = _norm_ts(base["ts"])
    volume = index["volume"].reset_index(drop=True) if "volume" in index.columns else pd.Series(np.nan, index=base.index)
    ev = fundamental_events(fund, base["symbol"].unique()) if events is None else events
    stale = [c for c in EVENT_VALUE_COLUMNS if c not in ev.columns]
    if stale and not ev.empty:  # an EVENTS_TABLE cached before these columns existed
        log.warning("edgar_events_cache_stale", missing=stale, fix="data.fundamentals.build_fundamental_events(store)")
    ev = ev.assign(**{c: np.nan for c in stale})
    value_cols = EVENT_VALUE_COLUMNS
    left = base.reset_index(names="_row").sort_values("ts")
    if ev.empty:
        merged = left.assign(avail_ts=pd.NaT, **{c: np.nan for c in value_cols})
    else:
        right = ev.assign(avail_ts=pd.to_datetime(ev["avail_ts"]).dt.as_unit("us")).sort_values("avail_ts")
        merged = pd.merge_asof(left, right[["symbol", "avail_ts", *value_cols]], left_on="ts", right_on="avail_ts", by="symbol")
    merged = merged.sort_values("_row").reset_index(drop=True)
    shares = merged["shares_outstanding"].astype("float64")
    merged["turnover"] = pd.to_numeric(volume, errors="coerce").astype("float64") / shares.where(shares > 0)
    cal = earnings_calendar_features(earnings, base)
    merged["days_since_earnings"] = cal["days_since_earnings"].values
    merged["is_earnings_window"] = cal["is_earnings_window"].values
    merged["days_since_filing"] = _sessions_since(merged["ts"], merged["avail_ts"]).values
    merged["sessions_to_expected_earnings"] = cal["sessions_to_expected_earnings"].values
    # earn_season ranks the quarter after eps_last_q_end: keep it only when the expected announcement is the one
    # that reports that quarter (0..MAX_REPORT_LAG_DAYS after its estimated end)
    lag = (pd.to_datetime(cal["expected_earnings"]).values
           - (pd.to_datetime(merged["eps_last_q_end"]) + pd.Timedelta(days=QUARTER_DAYS)).values)
    lag_days = pd.Series(lag).dt.days
    merged["earn_season"] = merged["earn_season"].where((lag_days >= 0) & (lag_days <= MAX_REPORT_LAG_DAYS))
    return merged[["symbol", "ts", *FEATURE_COLUMNS]]


def edgar_panel_features(store: Store, index: pd.DataFrame) -> pd.DataFrame:
    """`fundamental_features` reading the `fundamentals` / `earnings_dates` tables for the symbols in `index`."""
    syms = sorted(set(index["symbol"])) if len(index) else []
    return fundamental_features(read_fundamentals(store, syms), read_earnings(store, syms), index)


def build_fundamental_events(store: Store) -> int:
    """Recompute `fundamental_events` for every symbol in `fundamentals` and replace `EVENTS_TABLE`; rows written."""
    fund = read_fundamentals(store)
    events = fundamental_events(fund)
    if events.empty:
        return 0
    events = events.assign(avail_ts=pd.to_datetime(events["avail_ts"]))
    store.delete(EVENTS_TABLE, "TRUE")  # full rebuild: drop events of restated or removed filings
    return store.write_table(EVENTS_TABLE, events, EVENTS_KEYS)


def join_edgar(store: Store, panel: pd.DataFrame) -> pd.DataFrame:
    """``panel`` plus FEATURE_COLUMNS from the store's EDGAR tables (point-in-time: fundamentals from the session
    after their filed date, earnings from their reaction session). Unchanged when the store has no EDGAR data or
    the panel already carries the columns; uses the cached `fundamental_events` table when present. Also adds the
    Form 4 columns (`data.insiders.join_insiders`), the 8-K / 13D columns (`data.filings.join_filings`) and the news
    columns (`data.news.join_news`), so every join_edgar call site (replay, CLI, nightly) gets them."""
    from .filings import join_filings
    from .insiders import join_insiders
    from .news import join_news

    panel = join_news(store, join_filings(store, join_insiders(store, panel)))
    if panel is None or panel.empty or all(c in panel.columns for c in FEATURE_COLUMNS):
        return panel
    has = getattr(store, "has_table", None)
    if not callable(has) or not (has(EARNINGS_TABLE) or has(FUNDAMENTALS_TABLE)):
        return panel
    syms = sorted(set(panel["symbol"].astype(str)))
    events = None
    if has(EVENTS_TABLE):
        events = store.read_table(EVENTS_TABLE)
        events = events.loc[events["symbol"].isin(syms)] if not events.empty else events
    fund = read_fundamentals(store, syms) if events is None else None
    feats = fundamental_features(fund, read_earnings(store, syms), panel, events=events)
    missing = [c for c in FEATURE_COLUMNS if c not in panel.columns]
    log.info("edgar_join", symbols=len(syms), columns=missing, cached_events=events is not None)
    return panel.assign(**{c: feats[c].to_numpy() for c in missing})


# ===================================================================================== share issuance (batch 2)
#: columns of `join_share_issuance` (docs/preregistration/2026-10-10-batch2.md, card large_cap_net_repurchasers)
SHARE_COLUMNS: list[str] = ["mcap_pit", "close_as_traded", "net_share_issuance"]
NSI_NEAR_SESSIONS = 126  # Chen-Zimmermann ShareIss1Y: shares at t-6 months ...
NSI_FAR_SESSIONS = 378  # ... over shares at t-18 months
NSI_MAX_STEP = 2.0  # card data-error guard: a filing-to-filing change above +100% ...
NSI_MIN_STEP = 0.5  # ... or below -50% voids the signal
SPLITS_TABLE = "splits"  # data.universe.SPLITS_TABLE: symbol, ex_date, ratio (= split_to / split_from)


def _factor_after(splits: pd.DataFrame | None, symbol: pd.Series, day: pd.Series) -> np.ndarray:
    """Per row: the product of ``ratio`` over the symbol's splits with ex_date strictly after ``day`` (1.0 when
    none). A bar dated on the ex_date already trades post-split (data.universe.as_traded)."""
    out = np.ones(len(symbol), dtype="float64")
    if splits is None or len(splits) == 0 or len(symbol) == 0:
        return out
    sp = pd.DataFrame({"symbol": splits["symbol"].astype(str).str.upper(),
                       "ex_date": pd.to_datetime(splits["ex_date"]).dt.tz_localize(None).dt.normalize().dt.as_unit("us"),
                       "ratio": pd.to_numeric(splits["ratio"], errors="coerce")})
    sp = sp.loc[sp["ratio"] > 0].drop_duplicates(["symbol", "ex_date"]).sort_values(["symbol", "ex_date"])
    if sp.empty:
        return out
    log_ratio = np.log(sp["ratio"])
    sp["after"] = np.exp(log_ratio.iloc[::-1].groupby(sp["symbol"].iloc[::-1], sort=False).cumsum().iloc[::-1])
    left = pd.DataFrame({"symbol": symbol.astype(str).str.upper().to_numpy(),
                         "day": pd.to_datetime(day).dt.tz_localize(None).dt.normalize().dt.as_unit("us").to_numpy(),
                         "_row": np.arange(len(symbol))}).sort_values("day")
    hit = pd.merge_asof(left, sp.sort_values("ex_date")[["symbol", "ex_date", "after"]], left_on="day",
                        right_on="ex_date", by="symbol", direction="forward", allow_exact_matches=False)
    out[hit["_row"].to_numpy()] = hit["after"].fillna(1.0).to_numpy()
    return out


def share_issuance_features(events: pd.DataFrame, splits: pd.DataFrame | None, index: pd.DataFrame) -> pd.DataFrame:
    """SHARE_COLUMNS for the rows of ``index`` (symbol, ts, close), point-in-time.

    Adjusted shares of a filing = its cover-page count x the product of the split ratios with ex_date after the
    filed date, i.e. the count in the units of the store's split-adjusted bars. Then
    ``mcap_pit`` = close x adjusted shares of the latest filing usable at the bar (= as-traded close x as-traded
    shares: the later splits cancel), ``close_as_traded`` = close x the split ratios after the bar, and
    ``net_share_issuance`` = ln(adjusted shares usable 126 sessions earlier / usable 378 sessions earlier) (later
    splits cancel in the ratio, so only splits known by then enter). A filing is usable from the session after
    its filed date (`fundamental_events.avail_ts`). NaN when either count is missing or a filing-to-filing change
    of adjusted shares between the two dates is above +100% or below -50% (card guard)."""
    out = pd.DataFrame(np.nan, index=index.index, columns=SHARE_COLUMNS)
    if index.empty:
        return out
    sym = index["symbol"].astype(str).str.upper().reset_index(drop=True)
    ts = _norm_ts(index["ts"]).reset_index(drop=True)
    close = pd.to_numeric(index["close"], errors="coerce").reset_index(drop=True).astype("float64")
    bar_day = ts.dt.tz_localize(None)
    out["close_as_traded"] = (close * _factor_after(splits, sym, bar_day)).to_numpy()
    ev = events.loc[events["shares_outstanding"] > 0, ["symbol", "filed", "avail_ts", "shares_outstanding"]] if len(events) else events
    if ev is None or ev.empty:
        return out
    ev = ev.assign(symbol=ev["symbol"].astype(str).str.upper(), avail_ts=_norm_ts(ev["avail_ts"]))
    ev["adj"] = ev["shares_outstanding"].astype("float64") * _factor_after(splits, ev["symbol"], pd.to_datetime(ev["filed"]))
    ev = ev.sort_values(["symbol", "avail_ts"], kind="mergesort")
    step = ev["adj"] / ev.groupby("symbol", sort=False)["adj"].shift(1)
    bad = (step > NSI_MAX_STEP) | (step < NSI_MIN_STEP)
    ev["n_bad"] = bad.groupby(ev["symbol"], sort=False).cumsum().astype("float64")
    log.info("share_issuance_guard", flagged_filings=int(bad.sum()), flagged_symbols=int(ev.loc[bad, "symbol"].nunique()),
             symbols=int(ev["symbol"].nunique()))
    right = ev.sort_values("avail_ts")[["symbol", "avail_ts", "adj", "n_bad"]]

    days = bar_day.dt.normalize()
    sessions = trading_days(days.min().date() - timedelta(days=2 * NSI_FAR_SESSIONS), days.max().date())
    pos = np.searchsorted(np.array(sessions, dtype="datetime64[D]"), days.to_numpy().astype("datetime64[D]"), side="right") - 1

    session_stamps = pd.DatetimeIndex(pd.to_datetime(sessions)).tz_localize(TZ).as_unit("us")

    def asof(lag: int) -> pd.DataFrame:
        at = pd.Series(session_stamps[np.maximum(pos - lag, 0)]) if lag else ts
        left = pd.DataFrame({"symbol": sym, "at": at, "_row": np.arange(len(sym))}).sort_values("at")
        hit = pd.merge_asof(left, right, left_on="at", right_on="avail_ts", by="symbol")
        return hit.sort_values("_row").reset_index(drop=True)

    now, near, far = asof(0), asof(NSI_NEAR_SESSIONS), asof(NSI_FAR_SESSIONS)
    out["mcap_pit"] = (close * now["adj"]).to_numpy()
    nsi = np.log(near["adj"] / far["adj"]).where(near["n_bad"] == far["n_bad"])
    out["net_share_issuance"] = nsi.to_numpy()
    return out


def join_share_issuance(store: Store, panel: pd.DataFrame) -> pd.DataFrame:
    """``panel`` plus SHARE_COLUMNS from the cached `fundamental_events` table and the `splits` table. Unchanged
    when the store has no events table or the panel already carries the columns. Without a splits table the
    counts are used as filed (logged; every split then looks like an issuance)."""
    has = getattr(store, "has_table", None)
    if panel is None or panel.empty or all(c in panel.columns for c in SHARE_COLUMNS):
        return panel
    if not callable(has) or not has(EVENTS_TABLE):
        return panel
    events = store.read_table(EVENTS_TABLE)
    splits = store.read_table(SPLITS_TABLE) if has(SPLITS_TABLE) else None
    if splits is None or len(splits) == 0:
        log.warning("share_issuance_no_splits_table")
    feats = share_issuance_features(events, splits, panel)
    return panel.assign(**{c: feats[c].to_numpy() for c in SHARE_COLUMNS})


# ================================================================================================= ingest
def _cik_map(tickers: pd.DataFrame) -> dict[str, str]:
    out: dict[str, str] = {}
    for sym, cik in zip(tickers["symbol"], tickers["cik"], strict=False):
        s = str(sym).upper()
        out.setdefault(s, cik)
        out.setdefault(s.replace(SEC_TICKER_CLASS_SEP, STORE_TICKER_CLASS_SEP), cik)
    return out


def _fresh_ciks(store: Store, today: date, refresh_days: int, table: str = META_TABLE) -> set[str]:
    meta = store.read_table(table)
    if meta.empty:
        return set()
    cutoff = today - timedelta(days=refresh_days)
    fetched = _dates(meta["fetched_on"])
    ok = (meta["status"] == STATUS_OK) & pd.Series([f is not None and f >= cutoff for f in fetched], index=meta.index)
    return set(meta.loc[ok, "cik"].astype(str))


def run_edgar_ingest(
    store: Store,
    edgar: Edgar,
    symbols: Iterable[str] | None = None,
    *,
    limit: int | None = None,
    refresh_days: int = DEFAULT_REFRESH_DAYS,
    today: date | None = None,
    progress: Callable[[str], None] | None = None,
    eightk_only: bool = False,
) -> dict[str, Any]:
    """Fetch 8-K Item 2.02 earnings dates and XBRL fundamentals for `symbols` (default: every symbol in the
    store) into `earnings_dates` / `fundamentals`. Ticker -> CIK via company_tickers.json; one fetch per CIK
    (share classes share it). Resumable: CIKs fetched OK within `refresh_days` are skipped (`edgar_ingest_meta`).
    A failing CIK is logged and recorded, never fails the run. Rate limiting is the Edgar client's bucket.
    The same submissions fetch also fills `eightk_items` and `sched13d` (data.filings). ``eightk_only`` skips
    companyfacts and keeps its own resume table (`EIGHTK_META_TABLE`), so it runs even when every CIK is fresh."""
    from .edgar import submission_tables
    from .filings import EIGHTK_SCHEMA, EIGHTK_TABLE, KEYS, SCHED13D_SCHEMA, SCHED13D_TABLE

    meta_table = EIGHTK_META_TABLE if eightk_only else META_TABLE
    day = today or date.today()
    universe = sorted({s.upper().strip() for s in (symbols if symbols is not None else store.symbols()) if s})
    cik_map = _cik_map(edgar.company_tickers())
    by_cik: dict[str, list[str]] = {}
    no_cik: list[str] = []
    for sym in universe:
        cik = cik_map.get(sym)
        if cik is None:
            no_cik.append(sym)
        else:
            by_cik.setdefault(cik, []).append(sym)
    fresh = _fresh_ciks(store, day, refresh_days, meta_table)
    todo = [c for c in sorted(by_cik) if c not in fresh]
    skipped = len(by_cik) - len(todo)
    if limit is not None:
        todo = todo[: max(0, int(limit))]
    if progress:
        progress(f"edgar: {len(universe)} symbols, {len(by_cik)} CIKs, {skipped} fresh, {len(todo)} to fetch")
    totals = {"earnings_rows": 0, "fundamentals_rows": 0, "eightk_rows": 0, "sched13d_rows": 0}
    errors: dict[str, str] = {}
    for n, cik in enumerate(todo, start=1):
        syms = by_cik[cik]
        meta: dict[str, Any] = {"cik": cik, "symbols": ",".join(syms), "fetched_on": day, "earnings_rows": 0,
                                "fundamentals_rows": 0, "error": None}
        try:
            earnings, eightk, sched = submission_tables(edgar.submissions(cik), cik, syms)
            fund = None if eightk_only else parse_companyfacts(edgar.companyfacts(cik), syms, cik)
            meta["earnings_rows"] = store.write_table(EARNINGS_TABLE, earnings, EARNINGS_KEYS, schema=EARNINGS_SCHEMA)
            if fund is not None:
                meta["fundamentals_rows"] = store.write_table(
                    FUNDAMENTALS_TABLE, fund, FUNDAMENTALS_KEYS, schema=FUNDAMENTALS_SCHEMA
                )
            totals["eightk_rows"] += store.write_table(EIGHTK_TABLE, eightk, KEYS, schema=EIGHTK_SCHEMA)
            totals["sched13d_rows"] += store.write_table(SCHED13D_TABLE, sched, KEYS, schema=SCHED13D_SCHEMA)
            meta["status"] = STATUS_OK
            totals["earnings_rows"] += meta["earnings_rows"]
            totals["fundamentals_rows"] += meta["fundamentals_rows"]
        except Exception as exc:  # one bad CIK (HTTP, malformed JSON) must not fail the whole run
            meta["status"] = STATUS_ERROR
            meta["error"] = str(exc)[:500]
            errors[cik] = meta["error"]
            log.warning("edgar_ingest_cik_failed", cik=cik, symbols=syms, error=meta["error"])
        store.write_table(meta_table, pd.DataFrame([meta], columns=list(META_SCHEMA)), META_KEYS, schema=META_SCHEMA)
        if progress and n % PROGRESS_EVERY == 0:
            progress(f"edgar: {n}/{len(todo)} CIKs")
    result = {
        "symbols": len(universe),
        "ciks": len(by_cik),
        "fetched": len(todo) - len(errors),
        "skipped_fresh": skipped,
        "failed": len(errors),
        "no_cik": len(no_cik),
        **totals,
    }
    if totals["fundamentals_rows"]:
        result["events_rows"] = build_fundamental_events(store)
    log.info("edgar_ingest_done", **result)
    return {**result, "errors": errors, "no_cik_symbols": no_cik}


__all__ = [
    "EARNINGS_TABLE", "FUNDAMENTALS_TABLE", "META_TABLE", "FEATURE_COLUMNS", "parse_companyfacts", "read_earnings",
    "read_fundamentals", "earnings_dates_asof", "quarterly_values", "seasonal_surprise", "sue_asof",
    "revenue_surprise_asof", "gross_profitability_asof", "earnings_seasonality", "shares_outstanding_asof", "turnover_asof",
    "earnings_calendar_features", "fundamental_events", "fundamental_features", "edgar_panel_features",
    "EVENTS_TABLE", "build_fundamental_events", "join_edgar", "SHARE_COLUMNS", "share_issuance_features",
    "join_share_issuance",
    "run_edgar_ingest",
]
