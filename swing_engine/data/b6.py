"""Batch-6 panel columns (docs/proposals/swing-methods-2026-10/batch6/), from tables the batch-6 research store
holds (scripts/build_b6_store.py). No new data source.

`join_b6(store, panel)` does nothing unless the store has the `sic` table, which only that research store has, so
every other replay, the CLI and the nightly are untouched. With it:
* `sic2` (data.sic.join_sic): two-digit SIC, the same on every row of a symbol (EDGAR's current code).
* `etf_mkt`, `etf_smb`, `etf_hml` (card residual_reversal_ff3_etf): daily factor proxies from the store's own ETF
  bars, the same on every symbol's row of a session: SPY's close-to-close return, IWM's minus SPY's, IWD's minus
  IWF's. NaN on a session where one of the four has no bar or no previous bar.

Point-in-time: each factor value uses that session's close and the one before it, so it is known at its row's close
(the Kenneth French files, by contrast, arrive one to two months late: data.market_series).
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import pandas as pd
import structlog

from ._common import TZ
from .sic import TABLE as SIC_TABLE
from .sic import join_sic

log = structlog.get_logger(__name__)

MKT, SMALL, VALUE, GROWTH = "SPY", "IWM", "IWD", "IWF"  # card: MKT = SPY, SMB = IWM - SPY, HML = IWD - IWF
FACTOR_COLUMNS: list[str] = ["etf_mkt", "etf_smb", "etf_hml"]
LOOKBACK_PAD_DAYS = 7  # calendar days of ETF bars read before the panel's first session (the previous close)


def _sessions(ts: pd.Series) -> pd.Series:
    t = pd.to_datetime(ts)
    if t.dt.tz is not None:
        t = t.dt.tz_convert(TZ).dt.tz_localize(None)
    return t.dt.normalize()


def etf_factors(bars: pd.DataFrame) -> pd.DataFrame:
    """FACTOR_COLUMNS indexed by session from daily bars (symbol, ts, close) of the four ETFs."""
    if bars is None or bars.empty:
        return pd.DataFrame(columns=FACTOR_COLUMNS)
    close = bars.assign(day=_sessions(bars["ts"])).pivot_table(index="day", columns="symbol", values="close", aggfunc="last")
    ret = close.reindex(columns=[MKT, SMALL, VALUE, GROWTH]).astype(float).pct_change(fill_method=None)
    return pd.DataFrame({"etf_mkt": ret[MKT], "etf_smb": ret[SMALL] - ret[MKT], "etf_hml": ret[VALUE] - ret[GROWTH]})


def join_etf_factors(store: Any, panel: pd.DataFrame) -> pd.DataFrame:
    """``panel`` plus FACTOR_COLUMNS by session. Unchanged when the panel already carries them."""
    if panel is None or panel.empty or all(c in panel.columns for c in FACTOR_COLUMNS):
        return panel
    day = _sessions(panel["ts"])
    bars = store.read_bars([MKT, SMALL, VALUE, GROWTH], (day.min() - timedelta(days=LOOKBACK_PAD_DAYS)).date(),
                           day.max().date())
    factors = etf_factors(bars)
    log.info("b6_etf_factor_join", sessions=int(factors.notna().all(axis=1).sum()))
    return panel.assign(**{c: day.map(factors[c]).astype(float).to_numpy() for c in FACTOR_COLUMNS})


def join_b6(store: Any, panel: pd.DataFrame) -> pd.DataFrame:
    """``panel`` plus `sic2` and FACTOR_COLUMNS when the store is the batch-6 research store (has `sic`)."""
    has = getattr(store, "has_table", None)
    if panel is None or panel.empty or not callable(has) or not has(SIC_TABLE):
        return panel
    return join_etf_factors(store, join_sic(store, panel))


__all__ = ["FACTOR_COLUMNS", "etf_factors", "join_etf_factors", "join_b6"]
