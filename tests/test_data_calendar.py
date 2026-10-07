from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from swing_engine.data import calendar as cal


def test_trading_days_skip_weekends_and_holidays() -> None:
    days = cal.trading_days(date(2024, 7, 1), date(2024, 7, 8))
    assert days == [date(2024, 7, 1), date(2024, 7, 2), date(2024, 7, 3), date(2024, 7, 5), date(2024, 7, 8)]
    assert cal.trading_days("2024-07-06", "2024-07-07") == []
    assert cal.trading_days(date(2024, 7, 8), date(2024, 7, 1)) == []
    # spans a year boundary
    assert date(2024, 1, 1) not in cal.trading_days(date(2023, 12, 29), date(2024, 1, 3))


def test_is_open_respects_session_hours_and_early_close() -> None:
    assert cal.is_open(datetime(2024, 7, 3, 12, 0))  # naive -> New York
    assert not cal.is_open(datetime(2024, 7, 3, 13, 30))  # July 3 closes 13:00
    assert not cal.is_open(datetime(2024, 7, 4, 12, 0))  # holiday
    assert cal.is_open(pd.Timestamp("2024-07-05 09:30", tz="America/New_York"))
    assert not cal.is_open(pd.Timestamp("2024-07-05 16:00", tz="America/New_York"))
    assert cal.is_open(pd.Timestamp("2024-07-05 14:00", tz="UTC"))  # 10:00 New York


def test_next_open_and_neighbours() -> None:
    nxt = cal.next_open(datetime(2024, 7, 3, 13, 30))
    assert nxt == pd.Timestamp("2024-07-05 09:30", tz="America/New_York")
    assert cal.next_open(datetime(2024, 7, 5, 8, 0)) == pd.Timestamp("2024-07-05 09:30", tz="America/New_York")
    assert cal.prev_trading_day(date(2024, 7, 5)) == date(2024, 7, 3)
    assert cal.prev_trading_day(date(2024, 7, 8)) == date(2024, 7, 5)
    assert cal.next_trading_day(date(2024, 7, 3)) == date(2024, 7, 5)
    assert cal.is_trading_day(date(2024, 7, 5)) and not cal.is_trading_day(date(2024, 7, 4))
    assert cal.last_trading_day_on_or_before(date(2024, 7, 4)) == date(2024, 7, 3)


def test_session_bounds_tz_aware() -> None:
    bounds = cal.session_bounds(date(2024, 11, 29))
    assert bounds is not None
    open_, close = bounds
    assert str(open_.tz) == "America/New_York"
    assert (open_.hour, open_.minute) == (9, 30) and (close.hour, close.minute) == (13, 0)
    assert cal.session_bounds(date(2024, 11, 28)) is None
