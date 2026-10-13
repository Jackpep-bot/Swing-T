"""Shared pieces of the batch-5 cards (docs/proposals/swing-methods-2026-10/batch5/README.md, "Shared definitions").

``smallmid(rows)``: the SMALLMID universe on one session's as-of rows: common stocks ranked 501-3,000 by ``mcap_pit``
(close x point-in-time EDGAR shares, data.fundamentals.join_share_issuance) among the rows that have one, close >=
$3 and ``med_dv_63`` >= $1M. The rank is taken over the rows the caller passes (the replay's screened universe, so
config/prereg_b5.yaml screens wide). Rows without ``mcap_pit`` (funds, ETFs, no filed share count) are never in it.
"""
from __future__ import annotations

import pandas as pd

MCAP, MED_DV = "mcap_pit", "med_dv_63"  # join_share_issuance column; features.extra name
RANK_FIRST, RANK_LAST = 501, 3000  # README: mcap ranks 501-3,000
MIN_CLOSE = 3.0  # README: close >= $3
MIN_MEDIAN_DOLLAR_VOLUME = 1_000_000.0  # README: med_dv_63 >= $1M


def mcap_rank(rows: pd.DataFrame) -> pd.Series:
    """1 = largest ``mcap_pit`` among ``rows`` (NaN where it is missing); all NaN without the column."""
    if MCAP not in rows.columns:
        return pd.Series(float("nan"), index=rows.index)
    return rows[MCAP].rank(ascending=False, method="first")


def smallmid(rows: pd.DataFrame, first: int = RANK_FIRST, last: int = RANK_LAST) -> pd.Series:
    """Boolean mask of ``rows`` in the SMALLMID universe (all False when ``mcap_pit`` or ``med_dv_63`` is absent)."""
    if MCAP not in rows.columns or MED_DV not in rows.columns:
        return pd.Series(False, index=rows.index)
    rank = mcap_rank(rows)
    return ((rank >= first) & (rank <= last) & (rows["close"] >= MIN_CLOSE)
            & (rows[MED_DV] >= MIN_MEDIAN_DOLLAR_VOLUME)).fillna(False)
