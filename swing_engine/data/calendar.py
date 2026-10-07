"""NYSE trading calendar helpers on top of pandas_market_calendars (holidays and early closes included).

All instants are tz-aware America/New_York; naive datetimes are interpreted as New York local time.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import lru_cache

import pandas as pd
import pandas_market_calendars as pmc

from ._common import TZ, as_date

CALENDAR_NAME = "NYSE"
_SCHEDULE_CACHE_SIZE = 64
_MAX_SEARCH_DAYS = 14  # longest gap between sessions (holiday + weekend) with generous margin


@lru_cache(maxsize=8)
def _calendar(name: str = CALENDAR_NAME) -> pmc.MarketCalendar:
    return pmc.get_calendar(name)


@lru_cache(maxsize=_SCHEDULE_CACHE_SIZE)
def _year_schedule(name: str, year: int) -> pd.DataFrame:
    sched = _calendar(name).schedule(start_date=f"{year}-01-01", end_date=f"{year}-12-31")
    sched = sched.copy()
    for c in sched.columns:
        sched[c] = sched[c].dt.tz_convert(TZ)
    sched.index = pd.to_datetime(sched.index).date
    return sched


def schedule(start: date | datetime | str, end: date | datetime | str, name: str = CALENDAR_NAME) -> pd.DataFrame:
    """Session table indexed by date with tz-aware `market_open` / `market_close` columns."""
    s, e = as_date(start), as_date(end)
    if e < s:
        return _year_schedule(name, s.year).iloc[0:0]
    parts = [_year_schedule(name, y) for y in range(s.year, e.year + 1)]
    sched = pd.concat(parts)
    return sched[(sched.index >= s) & (sched.index <= e)]


def trading_days(start: date | datetime | str, end: date | datetime | str, name: str = CALENDAR_NAME) -> list[date]:
    """Session dates in [start, end] inclusive."""
    return list(schedule(start, end, name).index)


def is_trading_day(d: date | datetime | str, name: str = CALENDAR_NAME) -> bool:
    dd = as_date(d)
    return dd in _year_schedule(name, dd.year).index


def _localize(dt: datetime | pd.Timestamp) -> pd.Timestamp:
    ts = pd.Timestamp(dt)
    return ts.tz_localize(TZ) if ts.tzinfo is None else ts.tz_convert(TZ)


def session_bounds(d: date | datetime | str, name: str = CALENDAR_NAME) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """(open, close) for session date `d`, or None when the market is closed that day."""
    dd = as_date(d)
    sched = _year_schedule(name, dd.year)
    if dd not in sched.index:
        return None
    row = sched.loc[dd]
    return row["market_open"], row["market_close"]


def is_open(dt: datetime | pd.Timestamp, name: str = CALENDAR_NAME) -> bool:
    """True when the regular session is in progress at instant `dt` (open inclusive, close exclusive)."""
    ts = _localize(dt)
    bounds = session_bounds(ts.date(), name)
    if bounds is None:
        return False
    open_, close = bounds
    return bool(open_ <= ts < close)


def next_open(dt: datetime | pd.Timestamp, name: str = CALENDAR_NAME) -> pd.Timestamp:
    """The first regular-session open strictly after `dt` (tz-aware America/New_York)."""
    ts = _localize(dt)
    d = ts.date()
    for _ in range(_MAX_SEARCH_DAYS):
        bounds = session_bounds(d, name)
        if bounds is not None and bounds[0] > ts:
            return bounds[0]
        d += timedelta(days=1)
    raise RuntimeError(f"no session found within {_MAX_SEARCH_DAYS} days after {dt}")  # pragma: no cover


def prev_trading_day(d: date | datetime | str, name: str = CALENDAR_NAME) -> date:
    """The last session date strictly before `d`."""
    dd = as_date(d) - timedelta(days=1)
    for _ in range(_MAX_SEARCH_DAYS):
        if is_trading_day(dd, name):
            return dd
        dd -= timedelta(days=1)
    raise RuntimeError(f"no session found within {_MAX_SEARCH_DAYS} days before {d}")  # pragma: no cover


def next_trading_day(d: date | datetime | str, name: str = CALENDAR_NAME) -> date:
    """The first session date strictly after `d`."""
    dd = as_date(d) + timedelta(days=1)
    for _ in range(_MAX_SEARCH_DAYS):
        if is_trading_day(dd, name):
            return dd
        dd += timedelta(days=1)
    raise RuntimeError(f"no session found within {_MAX_SEARCH_DAYS} days after {d}")  # pragma: no cover


def last_trading_day_on_or_before(d: date | datetime | str, name: str = CALENDAR_NAME) -> date:
    dd = as_date(d)
    return dd if is_trading_day(dd, name) else prev_trading_day(dd, name)
