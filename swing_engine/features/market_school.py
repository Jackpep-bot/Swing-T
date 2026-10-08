"""IBD Market School-style market state (the CAN SLIM "M" rule) on one index's daily bars, point-in-time.

Rules: docs/methods/07-canslim-ibd-market-school.md "Market filter" and its implementation table; catalog item
``ibd_market_school_ftd_dd`` (docs/catalog/catalog.json); the M line of docs/strategies/canslim.md. IBD's own
rule book is proprietary; this is a reconstruction.

- **Distribution day (DD)**: close down >= ``dd_min_loss`` (0.2%, no rounding) on volume above the prior
  session's. A DD expires ``dd_window`` (25) sessions later, or once a later session's high is ``dd_expiry_rally``
  (6%, IBD 2 Mar 2012; some reconstructions use 5%) above the DD's close. A follow-through day clears the count.
- **Rally attempt**: in a correction, Day 1 is the first higher close; the attempt keeps counting sessions until a
  low undercuts the rally low (the lowest low of the decline), which restarts it.
- **Follow-through day (FTD)**: Day ``ftd_min_day`` (4) or later of the attempt, close up >= ``ftd_min_gain``
  (1.25%) on volume above the prior session's -> confirmed uptrend.
- **State**: ``confirmed_uptrend`` after an FTD; ``under_pressure`` while the live DD count >= ``dd_pressure`` (5,
  "5+ = full distribution"); ``correction`` from the start of the history (an uptrend must be confirmed by an
  FTD), on a close below the FTD's low (Market School S1), or at ``dd_correction`` (7) live DDs ("could probably
  withstand six or seven").

Columns (index ``session``, one row per bar)::

    ms_dd          1 on a distribution day
    ms_dd_count    live (unexpired) distribution days, today's included
    ms_rally_day   day number of the current rally attempt (0 = none / not in a correction)
    ms_ftd         1 on a follow-through day
    ms_state       confirmed_uptrend / under_pressure / correction

Every row on session T reads only bars dated on or before T (a forward loop). Volume is the ETF's (SPY) as a
labelled proxy for exchange volume (doc 07 implementation table). NaN volume never makes a DD or an FTD.
"""

from __future__ import annotations

import math

import pandas as pd

from ._common import CLOSE, HIGH, LOW, TS_COL, VOLUME, require_columns, session_key

DD_MIN_LOSS = 0.002
DD_WINDOW = 25
DD_EXPIRY_RALLY = 0.06
FTD_MIN_DAY = 4
FTD_MIN_GAIN = 0.0125
DD_PRESSURE = 5
DD_CORRECTION = 7

CONFIRMED = "confirmed_uptrend"
UNDER_PRESSURE = "under_pressure"
CORRECTION = "correction"
MS_COLUMNS: tuple[str, ...] = ("ms_dd", "ms_dd_count", "ms_rally_day", "ms_ftd", "ms_state")


def market_school(
    bars: pd.DataFrame,
    *,
    dd_min_loss: float = DD_MIN_LOSS,
    dd_window: int = DD_WINDOW,
    dd_expiry_rally: float = DD_EXPIRY_RALLY,
    ftd_min_day: int = FTD_MIN_DAY,
    ftd_min_gain: float = FTD_MIN_GAIN,
    dd_pressure: int = DD_PRESSURE,
    dd_correction: int = DD_CORRECTION,
) -> pd.DataFrame:
    """Market School columns (module docstring) for one index's bars (``ts, high, low, close, volume``)."""
    require_columns(bars, (TS_COL, HIGH, LOW, CLOSE, VOLUME), "market_school")
    b = bars.sort_values(TS_COL, kind="mergesort")
    high, low, close, vol = (b[c].astype("float64").to_numpy() for c in (HIGH, LOW, CLOSE, VOLUME))
    rows: list[tuple[int, int, int, int, str]] = []
    dds: list[tuple[int, float]] = []  # (bar index, close) of live distribution days
    state, rally_day, rally_low, ftd_low = CORRECTION, 0, math.inf, math.nan
    for t in range(len(b)):
        prev_c = close[t - 1] if t else math.nan
        prev_v = vol[t - 1] if t else math.nan
        ret = close[t] / prev_c - 1.0 if prev_c > 0 else math.nan
        higher_vol = vol[t] > prev_v  # False on any NaN
        dds = [(i, c) for i, c in dds if t - i < dd_window and not high[t] >= c * (1.0 + dd_expiry_rally)]
        is_dd = ret <= -dd_min_loss and higher_vol
        if is_dd:
            dds.append((t, close[t]))
        is_ftd = False
        if state == CORRECTION:
            if rally_day and low[t] < rally_low:  # undercut: the attempt fails, the count restarts
                rally_day = 0
            if rally_day:
                rally_day += 1
            else:
                rally_low = min(rally_low, low[t])
                rally_day = 1 if ret > 0 else 0
            if rally_day >= ftd_min_day and ret >= ftd_min_gain and higher_vol:
                is_ftd, state, ftd_low, rally_day, dds = True, CONFIRMED, low[t], 0, []
        elif close[t] < ftd_low or len(dds) >= dd_correction:
            state, rally_day, rally_low, ftd_low = CORRECTION, 0, low[t], math.nan
        else:
            state = UNDER_PRESSURE if len(dds) >= dd_pressure else CONFIRMED
        rows.append((int(is_dd), len(dds), rally_day, int(is_ftd), state))
    out = pd.DataFrame(rows, columns=list(MS_COLUMNS), index=pd.DatetimeIndex(session_key(b[TS_COL]), name="session"))
    return out.astype({"ms_dd": "int64", "ms_dd_count": "int64", "ms_rally_day": "int64", "ms_ftd": "int64"})


__all__ = ["CONFIRMED", "CORRECTION", "MS_COLUMNS", "UNDER_PRESSURE", "market_school"]
