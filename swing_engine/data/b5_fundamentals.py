"""Point-in-time fundamentals columns for the batch-5 cards (docs/proposals/swing-methods-2026-10/batch5/:
piotroski_fscore8_small_value, shareholder_yield_smallmid, code33_trend_template).

``join_b5_fundamentals(store, panel)`` adds B5_COLUMNS per (symbol, ts):

* ``b5_fscore``: Piotroski score 0-8 (card: 8 of the 9 signals; no current ratio in the store). Seven points come
  from the latest filing, the eighth is ``net_share_issuance <= 0`` on the row (data.fundamentals
  .join_share_issuance). NaN when any input is missing: a firm without a gross profit is excluded, not scored 0.
* ``b5_book_to_market``: latest total equity / ``mcap_pit``; NaN when equity <= 0.
* ``b5_ocf_ttm``: trailing-twelve-month operating cash flow.
* ``b5_code33``: 1.0 when the latest filing shows year-over-year EPS growth, revenue growth and margin (EPS /
  revenue: the card's EPS x shares / revenue with the share count a common factor) each rising over the three
  latest quarters with the latest EPS and revenue growth positive, 0.0 when it does not, NaN when unknown.
* ``b5_div_yield``: regular (not special, not foreign) cash dividends with an ex-date in the last 252 sessions,
  split-adjusted (data.dividends.mapped), over the close. NaN where the feed does not cover the window.
* ``b5_buyback_yield``: -ln(adjusted shares now / 252 bars earlier), adjusted shares = ``mcap_pit`` / close (the
  split-adjusted count of data.fundamentals.share_issuance_features); NaN across a filing-to-filing change above
  +100% or below -50% (the same guard).

Point-in-time: a filing's values are usable from the session after its filed date (``fundamental_events.avail_ts``);
every value read for a filing comes from the latest filing filed on or before it (restatements filed later never
reach back); dividends count from their ex-date. Periods are keyed by fiscal-quarter index, not exact dates, so
52/53-week years line up. Trailing twelve months = year-to-date + previous fiscal year - the same year-to-date a
year earlier (the four-quarter sum; 10-Q cash flows are reported year-to-date only); "a year ago" is that sum four
quarters earlier. Net income is the card's proxy: TTM diluted EPS x the filing's cover-page share count (the same
count for the year-ago figure). EPS facts are put on one split basis with the ``splits`` table.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import numpy as np
import pandas as pd
import structlog

from .calendar import trading_days
from .dividends import TABLE as DIVIDENDS_TABLE
from .dividends import mapped
from .fundamentals import (
    EPS_DILUTED,
    EVENTS_TABLE,
    FUNDAMENTALS_TABLE,
    GROSS_PROFIT,
    NSI_MAX_STEP,
    NSI_MIN_STEP,
    OPERATING_CASH_FLOW,
    REVENUE,
    SPLITS_TABLE,
    TOTAL_ASSETS,
    TOTAL_EQUITY,
    _factor_after,
    _norm_ts,
    join_share_issuance,
)

log = structlog.get_logger(__name__)

FSCORE, BOOK_TO_MARKET, OCF_TTM, CODE33 = "b5_fscore", "b5_book_to_market", "b5_ocf_ttm", "b5_code33"
DIV_YIELD, BUYBACK_YIELD = "b5_div_yield", "b5_buyback_yield"
B5_COLUMNS: list[str] = [FSCORE, BOOK_TO_MARKET, OCF_TTM, CODE33, DIV_YIELD, BUYBACK_YIELD]
EVENT_COLUMNS: list[str] = ["f7", "equity", "ocf_ttm", "code33"]  # per filing, before the row-level parts
#: per filing, also returned by ``event_values`` for the batch-13 mispricing cards (research.b13_books): asset growth
#: (assets / assets four quarters earlier - 1), accruals ((TTM net income - TTM operating cash flow) / mean of the two),
#: gross profit / assets and ROA, each with the latest total assets; NaN where an input is missing or assets <= 0
MISPRICING_COLUMNS: list[str] = ["asset_growth", "accruals", "gp_assets", "roa", "assets"]

QUARTER_DAYS = 365.25 / 4
YEAR_QUARTERS = 4
YIELD_SESSIONS = 252  # shareholder_yield card: dividends of the last 252 sessions, shares against 252 sessions ago
CODE33_MIN_ABS_EPS = 0.05  # code33 card: skip the growth rate when |EPS a year ago| < $0.05
CODE33_QUARTERS = 3  # code33 card: the three latest quarters
FLOWS = (EPS_DILUTED, OPERATING_CASH_FLOW, GROSS_PROFIT, REVENUE)
CONCEPT_ID = {c: i for i, c in enumerate((*FLOWS, TOTAL_ASSETS, TOTAL_EQUITY))}


def _quarter(days: pd.Series) -> np.ndarray:
    """Quarter index of a period end: the nearest calendar quarter end, counted from 1969-12-31."""
    # ponytail: one global grid; a fiscal quarter ending within a week of mid-Feb/May/Aug/Nov can straddle two
    # bins and then reads NaN (excluded). Per-company phase from its fiscal year end if that ever matters.
    d = pd.to_datetime(days).to_numpy().astype("datetime64[D]").astype(np.int64)
    return np.rint((d + 1) / QUARTER_DAYS).astype(np.int64)


def _key(sym: Any, concept: str, quarter: Any, length: Any) -> Any:
    return ((np.asarray(sym, dtype=np.int64) * 8 + CONCEPT_ID[concept]) * 8 + length) * 4096 + quarter


def event_values(facts: pd.DataFrame, events: pd.DataFrame, splits: pd.DataFrame | None = None,
                 first: Any = None) -> pd.DataFrame:
    """EVENT_COLUMNS per (symbol, filed) of ``events`` (the ``fundamental_events`` table), each from ``facts``
    (``fundamentals`` rows: symbol, concept, period_end, duration_days, filed, value; ties on a filed date in
    accession order) filed on or before that date. ``first``: only the filings a panel starting that day can see
    (each symbol's last one before it and everything after) are computed."""
    ev = events[["symbol", "filed", "avail_ts", "shares_outstanding"]].copy()
    ev["symbol"] = ev["symbol"].astype(str).str.upper()
    ev["filed"] = pd.to_datetime(ev["filed"]).astype("datetime64[ns]")
    ev = ev.sort_values(["filed", "symbol"], kind="mergesort").reset_index(drop=True)
    ev["sym"], names = pd.factorize(ev["symbol"])

    f = facts.loc[facts["concept"].isin(list(CONCEPT_ID)), ["symbol", "concept", "period_end", "duration_days", "filed", "value"]]
    f = f.assign(sym=pd.Index(names).get_indexer(f["symbol"].astype(str).str.upper()),
                 filed=pd.to_datetime(f["filed"]).astype("datetime64[ns]"), quarter=_quarter(f["period_end"]),
                 length=np.rint(f["duration_days"].to_numpy(dtype=float) / QUARTER_DAYS).astype(np.int64))
    f = f.loc[(f["sym"] >= 0) & (f["length"] <= YEAR_QUARTERS)].sort_values("filed", kind="mergesort")
    f["value"] = f["value"].astype("float64")
    eps = (f["concept"] == EPS_DILUTED).to_numpy()
    # every EPS fact on today's split basis; multiplied back to the filing's own basis where dollars matter
    f.loc[eps, "value"] = f.loc[eps, "value"].to_numpy() / _factor_after(splits, f.loc[eps, "symbol"], f.loc[eps, "filed"])
    f["key"] = np.int64(0)
    for concept in CONCEPT_ID:
        m = (f["concept"] == concept).to_numpy()
        f.loc[m, "key"] = _key(f.loc[m, "sym"], concept, f.loc[m, "quarter"], f.loc[m, "length"])

    # the fiscal period a filing reports: the latest quarter end among its flow facts and the longest duration
    # ending there (the year-to-date length, 1-4 quarters); an amendment of an older period keeps the latest
    flow = f.loc[f["concept"].isin(FLOWS) & (f["length"] >= 1)]
    code = (flow["quarter"] * 8 + flow["length"]).groupby([flow["sym"], flow["filed"]]).max().rename("code")
    ev = ev.join(code, on=["sym", "filed"])
    ev["code"] = ev.groupby("sym", sort=False)["code"].cummax()
    ev["code"] = ev.groupby("sym", sort=False)["code"].ffill()
    if first is not None:
        old = ev["filed"] < pd.Timestamp(first)
        last_old = ev["filed"].where(old).groupby(ev["sym"], sort=False).transform("max")
        ev = ev.loc[~old | (ev["filed"] == last_old)]
    out = ev[["symbol", "filed", "avail_ts"]].assign(**{c: np.nan for c in (*EVENT_COLUMNS, *MISPRICING_COLUMNS)})
    ev = ev.loc[ev["code"].notna()]
    if ev.empty:
        return out.reset_index(drop=True)
    sym, filed = ev["sym"].to_numpy(), ev["filed"].to_numpy()
    q0, ytd = (ev["code"].to_numpy() // 8).astype(np.int64), (ev["code"].to_numpy() % 8).astype(np.int64)
    right = f[["key", "filed", "value"]]

    def known(slots: list[tuple[str, Any, Any]]) -> np.ndarray:
        """[slot, filing] values of (concept, quarters back from the reported one, quarters long; 0 = balance
        sheet) from the latest filing filed on or before each filing's date."""
        keys = np.concatenate([_key(sym, c, q0 - back, np.zeros_like(q0) + length) for c, back, length in slots])
        req = pd.DataFrame({"key": keys, "filed": np.tile(filed, len(slots)), "i": np.arange(len(keys))})
        hit = pd.merge_asof(req.sort_values("filed", kind="mergesort"), right, on="filed", by="key")
        got = np.full(len(keys), np.nan)
        got[hit["i"].to_numpy()] = hit["value"].to_numpy()
        return got.reshape(len(slots), -1)

    def ttm(c: str) -> tuple[np.ndarray, np.ndarray]:
        """(trailing twelve months, the same four quarters earlier)."""
        cur, ann, prev, ann2, prev2 = known([(c, 0, ytd), (c, ytd, YEAR_QUARTERS), (c, YEAR_QUARTERS, ytd),
                                             (c, ytd + YEAR_QUARTERS, YEAR_QUARTERS), (c, 2 * YEAR_QUARTERS, ytd)])
        full = ytd == YEAR_QUARTERS
        return np.where(full, cur, cur + ann - prev), np.where(full, prev, prev + ann2 - prev2)

    def quarters(c: str) -> np.ndarray:
        """[quarters back, filing] single-quarter values; a fiscal Q4 given only as the annual figure is the
        annual minus the three quarters before it (data.fundamentals.quarterly_values)."""
        n = CODE33_QUARTERS + YEAR_QUARTERS
        q = known([(c, k, 1) for k in range(n + CODE33_QUARTERS)])
        a = known([(c, k, YEAR_QUARTERS) for k in range(n)])
        return np.where(np.isnan(q[:n]), a - q[1:n + 1] - q[2:n + 2] - q[3:n + 3], q[:n])

    basis = _factor_after(splits, ev["symbol"], ev["filed"])  # today's split basis -> the filing's own
    shares = ev["shares_outstanding"].to_numpy(dtype=float) * basis
    shares = np.where(shares > 0, shares, np.nan)
    (eps_t, eps_1), (ocf, _), (gp, gp_1), (rev, rev_1) = (ttm(c) for c in FLOWS)
    assets, assets_1, equity, equity_1 = known([(TOTAL_ASSETS, 0, 0), (TOTAL_ASSETS, YEAR_QUARTERS, 0),
                                                (TOTAL_EQUITY, 0, 0), (TOTAL_EQUITY, YEAR_QUARTERS, 0)])
    ni, ni_1 = eps_t * shares, eps_1 * shares
    e, r = quarters(EPS_DILUTED), quarters(REVENUE)
    with np.errstate(divide="ignore", invalid="ignore"):
        points = [ni / assets > 0,  # 1 ROA > 0
                  ocf > 0,  # 2 CFO > 0
                  ni / assets > ni_1 / assets_1,  # 3 ROA up
                  ocf > ni,  # 4 CFO > net income
                  equity / assets > equity_1 / assets_1,  # 5 equity / assets up (card proxy for falling leverage)
                  gp / rev > gp_1 / rev_1,  # 8 gross margin up
                  rev / assets > rev_1 / assets_1]  # 9 asset turnover up
        ok = (np.isfinite([ni, ni_1, ocf, gp, gp_1, rev, rev_1, assets, assets_1, equity, equity_1]).all(axis=0)
              & (assets > 0) & (assets_1 > 0) & (rev > 0) & (rev_1 > 0))
        k3 = range(CODE33_QUARTERS)
        year_ago = [e[k + YEAR_QUARTERS] for k in k3]
        g_eps = [np.where(np.abs(year_ago[k] * basis) >= CODE33_MIN_ABS_EPS, (e[k] - year_ago[k]) / np.abs(year_ago[k]),
                          np.nan) for k in k3]
        g_rev = [np.where(r[k + YEAR_QUARTERS] > 0, r[k] / r[k + YEAR_QUARTERS] - 1.0, np.nan) for k in k3]
        margin = [np.where(r[k] > 0, e[k] / r[k], np.nan) for k in k3]
        rising = np.all([x[k] > x[k + 1] for x in (g_eps, g_rev, margin) for k in range(CODE33_QUARTERS - 1)], axis=0)
        code33 = rising & (g_eps[0] > 0) & (g_rev[0] > 0)
        seen = np.isfinite([*g_eps, *g_rev, *margin]).all(axis=0)
    out.loc[ev.index, "f7"] = np.where(ok, np.sum(points, axis=0), np.nan)
    out.loc[ev.index, "equity"] = equity
    out.loc[ev.index, "ocf_ttm"] = ocf
    out.loc[ev.index, "code33"] = np.where(seen, code33.astype(float), np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        pos, pos_1 = assets > 0, (assets > 0) & (assets_1 > 0)
        out.loc[ev.index, "assets"] = np.where(pos, assets, np.nan)
        out.loc[ev.index, "asset_growth"] = np.where(pos_1, assets / assets_1 - 1.0, np.nan)
        out.loc[ev.index, "accruals"] = np.where(pos_1, (ni - ocf) / ((assets + assets_1) / 2.0), np.nan)
        out.loc[ev.index, "gp_assets"] = np.where(pos, gp / assets, np.nan)
        out.loc[ev.index, "roa"] = np.where(pos, ni / assets, np.nan)
    return out.reset_index(drop=True)


def dividend_yield(div: pd.DataFrame, symbol: pd.Series, day: pd.Series, close: pd.Series) -> np.ndarray:
    """Sum of the regular dividends' ``rate_adj`` with an ex-date in the YIELD_SESSIONS sessions ending on each
    row's day (``div`` = data.dividends.mapped), over the close. NaN where the window starts before the feed."""
    out = np.full(len(symbol), np.nan)
    flag = lambda c: div[c].fillna(False).astype(bool)  # noqa: E731
    reg = div.loc[~flag("special") & ~flag("foreign")]
    if reg.empty or not len(symbol):
        return out
    d = pd.DataFrame({"symbol": reg["store_symbol"].astype(str).to_numpy(),
                      "ex": pd.to_datetime(reg["ex_date"]).dt.as_unit("us").to_numpy(),
                      "rate": reg["rate_adj"].astype(float).to_numpy()}).sort_values(["symbol", "ex"])
    d["cum"] = d.groupby("symbol", sort=False)["rate"].cumsum()
    d = d.sort_values("ex", kind="mergesort")[["symbol", "ex", "cum"]]
    days = pd.to_datetime(day).dt.as_unit("us").reset_index(drop=True)
    sessions = pd.DatetimeIndex(pd.to_datetime(trading_days(
        days.min().date() - timedelta(days=2 * YIELD_SESSIONS), days.max().date()))).as_unit("us")
    pos = np.searchsorted(sessions.to_numpy(), days.to_numpy(), side="right") - 1
    start = pd.Series(sessions[np.maximum(pos - YIELD_SESSIONS, 0)])

    def paid(at: pd.Series) -> np.ndarray:  # cumulative dividends with ex-date <= at
        left = pd.DataFrame({"symbol": symbol.astype(str).to_numpy(), "at": at.to_numpy(),
                             "_row": np.arange(len(at))}).sort_values("at", kind="mergesort")
        hit = pd.merge_asof(left, d, left_on="at", right_on="ex", by="symbol").sort_values("_row")
        return hit["cum"].fillna(0.0).to_numpy()

    covered = (pos >= YIELD_SESSIONS) & (start >= d["ex"].min()).to_numpy()
    px = pd.to_numeric(close, errors="coerce").to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(covered & (px > 0), (paid(days) - paid(start)) / px, np.nan)


def buyback_yield(symbol: pd.Series, ts: pd.Series, adj_shares: pd.Series) -> np.ndarray:
    """-ln(adjusted shares / adjusted shares YIELD_SESSIONS bars earlier) per symbol; NaN when a bar-to-bar change
    of the count (a new filing) between the two is above NSI_MAX_STEP or below NSI_MIN_STEP."""
    g = pd.DataFrame({"symbol": symbol.to_numpy(), "ts": ts.to_numpy(), "adj": adj_shares.to_numpy(dtype=float)})
    g = g.sort_values(["symbol", "ts"], kind="mergesort")
    by = g.groupby("symbol", sort=False)
    step = g["adj"] / by["adj"].shift(1)
    n_bad = ((step > NSI_MAX_STEP) | (step < NSI_MIN_STEP)).groupby(g["symbol"], sort=False).cumsum()
    same = n_bad == n_bad.groupby(g["symbol"], sort=False).shift(YIELD_SESSIONS)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = (-np.log(g["adj"] / by["adj"].shift(YIELD_SESSIONS))).where(same & (g["adj"] > 0))
    return out.sort_index().to_numpy()


def _read_facts(store: Any, symbols: list[str]) -> pd.DataFrame:
    where, params = "symbol IN (SELECT unnest(?)) AND concept IN (SELECT unnest(?))", [symbols, list(CONCEPT_ID)]
    con = getattr(store, "_con", None)
    if con is None:
        return store.read_table(FUNDAMENTALS_TABLE, where, params, order_by="filed, accession")
    return con.execute(f"SELECT symbol, concept, period_end, duration_days, filed, value FROM {FUNDAMENTALS_TABLE} "
                       f"WHERE {where} ORDER BY filed, accession", params).df()  # 6 of 13 columns: the table is millions of rows


def join_b5_fundamentals(store: Any, panel: pd.DataFrame) -> pd.DataFrame:
    """``panel`` plus B5_COLUMNS. Unchanged when the panel already carries them or the store has no
    ``fundamentals`` / ``fundamental_events`` tables; the dividend column is NaN without a ``dividends`` table.
    Reads ``mcap_pit`` / ``net_share_issuance`` from the panel, running ``join_share_issuance`` itself when the
    caller has not."""
    has = getattr(store, "has_table", None)
    if panel is None or panel.empty or all(c in panel.columns for c in B5_COLUMNS):
        return panel
    if not callable(has) or not (has(EVENTS_TABLE) and has(FUNDAMENTALS_TABLE)):
        return panel
    shares = join_share_issuance(store, panel)
    sym = panel["symbol"].astype(str).str.upper().reset_index(drop=True)
    ts = _norm_ts(panel["ts"]).reset_index(drop=True)
    day = ts.dt.tz_localize(None).dt.normalize()
    close = pd.to_numeric(panel["close"], errors="coerce").reset_index(drop=True).astype("float64")
    mcap = shares["mcap_pit"].reset_index(drop=True).astype("float64")
    nsi = shares["net_share_issuance"].reset_index(drop=True).astype("float64")
    symbols = sorted(set(sym))
    splits = store.read_table(SPLITS_TABLE) if has(SPLITS_TABLE) else None
    events = store.read_table(EVENTS_TABLE, "symbol IN (SELECT unnest(?))", [symbols])
    vals = event_values(_read_facts(store, symbols), events, splits, first=day.min()) if len(events) else None
    cols: dict[str, np.ndarray] = {c: np.full(len(panel), np.nan) for c in B5_COLUMNS}
    if vals is not None and len(vals):
        right = vals.assign(avail_ts=_norm_ts(vals["avail_ts"])).sort_values("avail_ts")
        left = pd.DataFrame({"symbol": sym, "ts": ts, "_row": np.arange(len(sym))}).sort_values("ts")
        hit = pd.merge_asof(left, right[["symbol", "avail_ts", *EVENT_COLUMNS]], left_on="ts", right_on="avail_ts",
                            by="symbol").sort_values("_row").reset_index(drop=True)
        cols[FSCORE] = (hit["f7"] + (nsi <= 0).astype(float)).where(nsi.notna()).to_numpy()
        cols[BOOK_TO_MARKET] = (hit["equity"] / mcap).where((hit["equity"] > 0) & (mcap > 0)).to_numpy()
        cols[OCF_TTM] = hit["ocf_ttm"].to_numpy()
        cols[CODE33] = hit["code33"].to_numpy()
    if has(DIVIDENDS_TABLE):
        cols[DIV_YIELD] = dividend_yield(mapped(store), sym, day, close)
    cols[BUYBACK_YIELD] = buyback_yield(sym, ts, mcap / close.where(close > 0))
    log.info("b5_fundamentals_join", symbols=len(symbols), filings=0 if vals is None else len(vals),
             **{c: int(np.isfinite(v).sum()) for c, v in cols.items()})
    return panel.assign(**cols)


__all__ = ["B5_COLUMNS", "MISPRICING_COLUMNS", "event_values", "dividend_yield", "buyback_yield", "join_b5_fundamentals"]
