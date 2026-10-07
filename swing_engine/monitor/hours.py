"""Market-hours helpers in America/New_York. Self-contained (no calendar vendor) so the monitor can run with a
minimal dependency set; a holiday set can be injected by the caller.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .constants import (
    AFTERHOURS_CLOSE,
    EARLY_AFTERHOURS_CLOSE,
    EARLY_REGULAR_CLOSE,
    MINUTES_IN_SESSION,
    PREMARKET_OPEN,
    REGULAR_CLOSE,
    REGULAR_OPEN,
)

ET = ZoneInfo("America/New_York")

# Observed NYSE full-day closures for the current cycle. Keep in sync with data/calendar when that lands.
NYSE_HOLIDAYS_2026: frozenset[date] = frozenset(
    {
        date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3), date(2026, 5, 25),
        date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7), date(2026, 11, 26), date(2026, 12, 25),
    }
)
NYSE_HOLIDAYS_2027: frozenset[date] = frozenset(
    {
        date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15), date(2027, 3, 26), date(2027, 5, 31),
        date(2027, 6, 18), date(2027, 7, 5), date(2027, 9, 6), date(2027, 11, 25), date(2027, 12, 24),
    }
)
DEFAULT_HOLIDAYS: frozenset[date] = NYSE_HOLIDAYS_2026 | NYSE_HOLIDAYS_2027
# 13:00 ET closes: the day after Thanksgiving and Christmas Eve when it falls on a weekday (2027-12-24 is the
# observed Christmas holiday, so only Black Friday that year). Keep in sync with data/calendar.
NYSE_EARLY_CLOSES: frozenset[date] = frozenset({date(2026, 11, 27), date(2026, 12, 24), date(2027, 11, 26)})
SATURDAY = 5
MINUTES_PER_HOUR = 60


def now_utc() -> datetime:
    return datetime.now(UTC)


def to_et(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(ET)


def is_trading_day(d: date, holidays: frozenset[date] | set[date] = DEFAULT_HOLIDAYS) -> bool:
    return d.weekday() < SATURDAY and d not in holidays


def is_early_close(d: date, early_closes: frozenset[date] | set[date] = NYSE_EARLY_CLOSES) -> bool:
    return d in early_closes


def session_bounds(d: date, early_closes: frozenset[date] | set[date] = NYSE_EARLY_CLOSES) -> tuple[time, time]:
    """(regular close, extended-hours close) for the session dated ``d``."""
    if is_early_close(d, early_closes):
        return EARLY_REGULAR_CLOSE, EARLY_AFTERHOURS_CLOSE
    return REGULAR_CLOSE, AFTERHOURS_CLOSE


def session_end(dt: datetime, early_closes: frozenset[date] | set[date] = NYSE_EARLY_CLOSES) -> datetime:
    """Extended-hours close (tz-aware, ET) of the session that contains ``dt``'s ET date."""
    et = to_et(dt)
    _, ah_close = session_bounds(et.date(), early_closes)
    return datetime.combine(et.date(), ah_close, tzinfo=ET)


def session_phase(
    dt: datetime,
    holidays: frozenset[date] | set[date] = DEFAULT_HOLIDAYS,
    early_closes: frozenset[date] | set[date] = NYSE_EARLY_CLOSES,
) -> str:
    """closed | premarket | regular | afterhours (America/New_York), early closes included."""
    et = to_et(dt)
    if not is_trading_day(et.date(), holidays):
        return "closed"
    regular_close, afterhours_close = session_bounds(et.date(), early_closes)
    t = et.time()
    if PREMARKET_OPEN <= t < REGULAR_OPEN:
        return "premarket"
    if REGULAR_OPEN <= t < regular_close:
        return "regular"
    if regular_close <= t < afterhours_close:
        return "afterhours"
    return "closed"


def is_market_hours(dt: datetime, extended: bool = True, holidays: frozenset[date] | set[date] = DEFAULT_HOLIDAYS) -> bool:
    phase = session_phase(dt, holidays)
    if extended:
        return phase != "closed"
    return phase == "regular"


def session_minutes(d: date, early_closes: frozenset[date] | set[date] = NYSE_EARLY_CLOSES) -> int:
    """Length of the regular session in minutes (390, or 210 on an early-close day)."""
    regular_close, _ = session_bounds(d, early_closes)
    length = datetime.combine(d, regular_close) - datetime.combine(d, REGULAR_OPEN)
    return int(length / timedelta(minutes=1))


def minute_of_session(dt: datetime) -> int:
    """Minutes elapsed since the 09:30 open, clipped to [0, session length] (390 on a normal day)."""
    et = to_et(dt)
    elapsed = (et.hour - REGULAR_OPEN.hour) * MINUTES_PER_HOUR + (et.minute - REGULAR_OPEN.minute)
    return max(0, min(min(MINUTES_IN_SESSION, session_minutes(et.date())), elapsed))


def et_time_at_or_after(dt: datetime, hhmm: time) -> bool:
    return to_et(dt).time() >= hhmm


def parse_hhmm(value: str) -> time:
    hh, mm = value.split(":")
    return time(int(hh), int(mm))
