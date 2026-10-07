"""Time-of-day relative volume (RVOL) profile for the live monitor.

RVOL is *time-of-day adjusted*: today's cumulative volume at clock minute ``m`` divided by the average
cumulative volume at the same minute over the last ``days`` sessions (default 20). Minutes are counted from
midnight New York time (``09:30`` = 570), so the profile naturally includes pre-market prints when the
intraday feed carries them. Thresholds (``>= 2`` notable, ``>= 3`` significant, ``>= 5`` strong) live in
``settings.yaml`` (``monitor.rvol_gate``, ``monitor.smallcap.rvol_min``), not here.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ._common import NY_TZ, SYMBOL_COL, TS_COL, VOLUME, require_columns

MINUTES_PER_DAY = 24 * 60
MINUTES_PER_HOUR = 60
DEFAULT_PROFILE_DAYS = 20
MINUTE_COL = "minute_of_day"
AVG_CUM_COL = "avg_cum_volume"
N_SESSIONS_COL = "n_sessions"
PROFILE_COLUMNS: tuple[str, ...] = (SYMBOL_COL, MINUTE_COL, AVG_CUM_COL, N_SESSIONS_COL)
_SESSION = "_session"
_CUM = "_cum"


def _local(ts: pd.Series) -> pd.Series:
    return ts.dt.tz_convert(NY_TZ) if ts.dt.tz is not None else ts


def minute_of_day(ts: pd.Series) -> pd.Series:
    """Minutes since midnight New York time: ``hour * 60 + minute`` (``09:30`` -> 570, ``16:00`` -> 960)."""
    local = _local(ts)
    return (local.dt.hour * MINUTES_PER_HOUR + local.dt.minute).astype(np.int64)


def build_rvol_profile(intraday_bars: pd.DataFrame, days: int = DEFAULT_PROFILE_DAYS) -> pd.DataFrame:
    """Average cumulative volume by clock minute over each symbol's last ``days`` sessions.

    ``intraday_bars`` is long format with at least ``symbol, ts, volume`` (minute bars, ``ts`` tz-aware).
    Within a session the cumulative volume is carried forward across minutes without a bar and is 0 before the
    first bar, so every minute 0..1439 has a value. Returns a long frame with columns
    ``symbol, minute_of_day, avg_cum_volume, n_sessions`` (``n_sessions <= days`` is how many sessions were
    averaged). Pass it through :func:`profile_lookup` once for fast :func:`rvol_now` calls.
    """
    require_columns(intraday_bars, (SYMBOL_COL, TS_COL, VOLUME), "build_rvol_profile")
    if days <= 0:
        raise ValueError("days must be positive")
    if len(intraday_bars) == 0:
        return pd.DataFrame({c: pd.Series(dtype="float64") for c in PROFILE_COLUMNS})
    local = _local(intraday_bars[TS_COL])
    d = pd.DataFrame(
        {
            SYMBOL_COL: intraday_bars[SYMBOL_COL].to_numpy(),
            _SESSION: local.dt.tz_localize(None).dt.normalize().to_numpy()
            if local.dt.tz is not None
            else local.dt.normalize().to_numpy(),
            MINUTE_COL: minute_of_day(intraday_bars[TS_COL]).to_numpy(),
            VOLUME: intraday_bars[VOLUME].astype("float64").to_numpy(),
        }
    )
    sessions = d[[SYMBOL_COL, _SESSION]].drop_duplicates().sort_values([SYMBOL_COL, _SESSION])
    keep = sessions.groupby(SYMBOL_COL, sort=False).tail(days)
    d = d.merge(keep, on=[SYMBOL_COL, _SESSION], how="inner")
    d = d.sort_values([SYMBOL_COL, _SESSION, MINUTE_COL], kind="mergesort")
    d[_CUM] = d.groupby([SYMBOL_COL, _SESSION], sort=False)[VOLUME].cumsum()
    grid = d.groupby([SYMBOL_COL, _SESSION, MINUTE_COL], sort=True)[_CUM].last().unstack(MINUTE_COL)
    grid = grid.reindex(columns=range(MINUTES_PER_DAY)).ffill(axis=1).fillna(0.0)
    by_symbol = grid.groupby(level=SYMBOL_COL, sort=False)
    avg = by_symbol.mean()
    n_sessions = by_symbol.size()
    long = avg.stack().rename(AVG_CUM_COL).reset_index()
    long.columns = [SYMBOL_COL, MINUTE_COL, AVG_CUM_COL]
    long[MINUTE_COL] = long[MINUTE_COL].astype(np.int64)
    long[N_SESSIONS_COL] = long[SYMBOL_COL].map(n_sessions).astype(np.int64)
    return long.reset_index(drop=True)


def profile_lookup(profile: pd.DataFrame) -> dict[str, np.ndarray]:
    """``{symbol: array of 1440 average cumulative volumes}`` for O(1) lookups in the monitor hot path."""
    require_columns(profile, (SYMBOL_COL, MINUTE_COL, AVG_CUM_COL), "profile_lookup")
    out: dict[str, np.ndarray] = {}
    for sym, grp in profile.groupby(SYMBOL_COL, sort=False):
        arr = np.zeros(MINUTES_PER_DAY, dtype=float)
        arr[grp[MINUTE_COL].to_numpy(dtype=np.int64)] = grp[AVG_CUM_COL].to_numpy(dtype=float)
        out[str(sym)] = arr
    return out


def rvol_now(
    symbol: str, cum_volume: float, minute_of_day: int, profile: pd.DataFrame | dict[str, np.ndarray]
) -> float:
    """``cum_volume / avg_cum_volume[symbol, minute_of_day]``; NaN when the symbol is missing from the profile or
    the average is zero. ``profile`` is the frame from :func:`build_rvol_profile` or the dict from
    :func:`profile_lookup` (preferred for repeated calls).
    """
    minute = int(min(max(minute_of_day, 0), MINUTES_PER_DAY - 1))
    if isinstance(profile, dict):
        arr = profile.get(symbol)
        if arr is None:
            return float("nan")
        base = float(arr[minute])
    else:
        rows = profile[(profile[SYMBOL_COL] == symbol) & (profile[MINUTE_COL] == minute)]
        if len(rows) == 0:
            return float("nan")
        base = float(rows[AVG_CUM_COL].iloc[0])
    if not base > 0:
        return float("nan")
    return float(cum_volume) / base
