"""Batch-5 event columns (docs/proposals/swing-methods-2026-10/batch5/: `ceo_cfo_buy_5day`, the exclusions of
`russell_recon_deletion_rebound` and `tax_loss_loser_rebound`, rules 1-3 of `event_avoid_filters`) from tables the
store already holds. No new data source.

`join_b5_events(store, panel)` adds, for each table that exists:
* `insider_trades` -> `ceo_cfo_buy_value`: dollar value of open-market purchases (code P) by an officer whose title
  matches CEO or CFO and who is not a Cohen-Malloy-Pomorski routine trader, summed per (symbol, filing date), on the
  first session after that filing date and 0 elsewhere (two filing dates landing on one session: the larger sum, so
  the card's per-filing-date threshold is tested as written). `ceo_buy_value` / `cfo_buy_value`: the same filing's
  split by role (a "CEO and CFO" title counts in both).
* `eightk_items` -> `days_since_8k_distress` (original 8-Ks carrying Item 1.03 bankruptcy or 3.01 delisting notice)
  and `days_since_8k_502` (Item 5.02 officer departure): sessions since the latest reaction session, 0 on it, NaN
  before the first. 8-K/A amendments are not events.
* `splits` -> `days_since_reverse_split`: sessions since the latest split with ratio < 1 (ex-date), NaN when none.

Point-in-time: Form 4 from the session after its filing date (never the transaction date), 8-K from its reaction
session, splits from the ex-date; the CMP label of year Y uses only trades filed before Jan 1 of Y (data.insiders).
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import structlog

from ._common import TZ
from .calendar import trading_days
from .filings import EIGHTK_TABLE, ORIGINAL_8K, has_item
from .fundamentals import SPLITS_TABLE, earnings_calendar_features
from .insiders import BUY, ROUTINE, TRADES_TABLE, label_trades
from .store import Store

log = structlog.get_logger(__name__)

CEO_PATTERN = r"chief executive|\bceo\b"  # card ceo_cfo_buy_5day: officer_title match, case-insensitive
CFO_PATTERN = r"chief financial|\bcfo\b"
ITEMS_DISTRESS = ("1.03", "3.01")  # event_avoid_filters rule 2: bankruptcy, delisting notice
ITEM_OFFICER_DEPARTURE = "5.02"  # event_avoid_filters rule 3
CALENDAR_PAD_DAYS = 10  # sessions fetched beyond the last filing date (a filing is visible the next session)

INSIDER_COLUMNS: list[str] = ["ceo_cfo_buy_value", "ceo_buy_value", "cfo_buy_value"]
EIGHTK_FEATURES: list[str] = ["days_since_8k_distress", "days_since_8k_502"]
SPLIT_COLUMNS: list[str] = ["days_since_reverse_split"]
FEATURE_COLUMNS: list[str] = [*INSIDER_COLUMNS, *EIGHTK_FEATURES, *SPLIT_COLUMNS]


def _days(values: pd.Series) -> np.ndarray:
    ts = pd.to_datetime(values)
    if getattr(ts.dt, "tz", None) is not None:
        ts = ts.dt.tz_convert(TZ).dt.tz_localize(None)
    return ts.to_numpy().astype("datetime64[D]")


def _sessions_since(events: pd.DataFrame, index: pd.DataFrame) -> np.ndarray:
    """Sessions since each (symbol, ts) row's latest event `session` (0 on it; NaN before the first)."""
    if events is None or events.empty:
        return np.full(len(index), np.nan)
    ev = events.assign(session=pd.to_datetime(events["session"]).dt.date)[["symbol", "session"]]
    return earnings_calendar_features(ev, index)["days_since_earnings"].to_numpy()


def ceo_cfo_features(trades: pd.DataFrame, index: pd.DataFrame, cmp_class: pd.Series | None = None) -> pd.DataFrame:
    """INSIDER_COLUMNS per (symbol, ts) row of `index` from `insider_trades` rows (`cmp_class` aligned with them;
    default: classified on `trades` alone). Zero where no qualifying filing becomes visible."""
    out = index[["symbol", "ts"]].reset_index(drop=True).assign(**{c: 0.0 for c in INSIDER_COLUMNS})
    if out.empty or trades is None or trades.empty:
        return out
    labels = label_trades(trades) if cmp_class is None else cmp_class
    title = trades["officer_title"].fillna("").astype(str)
    ceo = title.str.contains(CEO_PATTERN, case=False, regex=True)
    cfo = title.str.contains(CFO_PATTERN, case=False, regex=True)
    keep = (trades["code"] == BUY) & trades["is_officer"].eq(True) & (ceo | cfo) & (labels.to_numpy() != ROUTINE)
    value = pd.to_numeric(trades["value"], errors="coerce").fillna(0.0)
    t = trades.assign(ceo_cfo_buy_value=value, ceo_buy_value=value.where(ceo, 0.0), cfo_buy_value=value.where(cfo, 0.0))
    t = t.loc[keep].drop_duplicates(["accession", "trans_id"])  # one row per reporting owner: joint filers repeat
    if t.empty:
        return out
    filed, panel_days = _days(t["filing_date"]), _days(out["ts"])
    sessions = np.array(trading_days(filed.min().astype(date), filed.max().astype(date) + timedelta(days=CALENDAR_PAD_DAYS)),
                        dtype="datetime64[D]")
    t = t.assign(day=sessions[np.searchsorted(sessions, filed, side="right")])  # first session AFTER the filing date
    per_filing = t.groupby(["symbol", "filing_date", "day"], as_index=False)[INSIDER_COLUMNS].sum()
    per_day = per_filing.sort_values(INSIDER_COLUMNS[0]).drop_duplicates(["symbol", "day"], keep="last")
    hit = out[["symbol"]].assign(day=panel_days).merge(per_day[["symbol", "day", *INSIDER_COLUMNS]],
                                                       on=["symbol", "day"], how="left")
    return out.assign(**{c: hit[c].fillna(0.0).to_numpy() for c in INSIDER_COLUMNS})


def eightk_event_features(eightk: pd.DataFrame, index: pd.DataFrame) -> pd.DataFrame:
    """EIGHTK_FEATURES per (symbol, ts) row of `index` from `eightk_items` rows (original 8-Ks only)."""
    out = index[["symbol", "ts"]].reset_index(drop=True)
    ev = eightk.loc[eightk["form"] == ORIGINAL_8K] if eightk is not None and not eightk.empty else None
    if ev is None or ev.empty or out.empty:
        return out.assign(**{c: np.nan for c in EIGHTK_FEATURES})
    distress = np.logical_or.reduce([has_item(ev["items"], item).to_numpy() for item in ITEMS_DISTRESS])
    return out.assign(days_since_8k_distress=_sessions_since(ev.loc[distress], out),
                      days_since_8k_502=_sessions_since(ev.loc[has_item(ev["items"], ITEM_OFFICER_DEPARTURE)], out))


def reverse_split_features(splits: pd.DataFrame, index: pd.DataFrame) -> pd.DataFrame:
    """SPLIT_COLUMNS per (symbol, ts) row of `index` from `splits` rows (symbol, ex_date, ratio = to / from)."""
    out = index[["symbol", "ts"]].reset_index(drop=True)
    if splits is None or splits.empty or out.empty:
        return out.assign(days_since_reverse_split=np.nan)
    rev = splits.loc[pd.to_numeric(splits["ratio"], errors="coerce") < 1.0]
    ev = pd.DataFrame({"symbol": rev["symbol"].astype(str).str.upper(), "session": rev["ex_date"]})
    return out.assign(days_since_reverse_split=_sessions_since(ev, out))


def _insider_join(store: Store, syms: list[str], panel: pd.DataFrame) -> pd.DataFrame:
    buys = store.read_table(TRADES_TABLE, "code = ? AND is_officer AND symbol IN (SELECT unnest(?))", [BUY, syms])
    if buys.empty:
        return ceo_cfo_features(buys, panel)
    history = store.read_table(TRADES_TABLE, "owner_cik IN (SELECT unnest(?))", [sorted(set(buys["owner_cik"]))])
    return ceo_cfo_features(buys, panel, label_trades(buys, history))


def _eightk_join(store: Store, syms: list[str], panel: pd.DataFrame) -> pd.DataFrame:
    return eightk_event_features(
        store.read_table(EIGHTK_TABLE, "form = ? AND symbol IN (SELECT unnest(?))", [ORIGINAL_8K, syms]), panel)


def _split_join(store: Store, syms: list[str], panel: pd.DataFrame) -> pd.DataFrame:
    return reverse_split_features(store.read_table(SPLITS_TABLE, "ratio < 1"), panel)


def join_b5_events(store: Store, panel: pd.DataFrame) -> pd.DataFrame:
    """``panel`` plus FEATURE_COLUMNS, table by table. Unchanged when the store has none of the tables or the panel
    already carries the columns."""
    has = getattr(store, "has_table", None)
    if panel is None or panel.empty or not callable(has):
        return panel
    syms = sorted(set(panel["symbol"].astype(str)))
    for table, cols, fn in ((TRADES_TABLE, INSIDER_COLUMNS, _insider_join), (EIGHTK_TABLE, EIGHTK_FEATURES, _eightk_join),
                            (SPLITS_TABLE, SPLIT_COLUMNS, _split_join)):
        missing = [c for c in cols if c not in panel.columns]
        if not missing or not has(table):
            continue
        feats = fn(store, syms, panel)
        log.info("b5_events_join", table=table, symbols=len(syms), columns=missing)
        panel = panel.assign(**{c: feats[c].to_numpy() for c in missing})
    return panel


__all__ = ["FEATURE_COLUMNS", "INSIDER_COLUMNS", "EIGHTK_FEATURES", "SPLIT_COLUMNS", "ceo_cfo_features",
           "eightk_event_features", "reverse_split_features", "join_b5_events"]
