"""Calendar helpers shared by the catalog batch-3 strategy modules. Not a registered strategy.

Both read only the published NYSE schedule (`data.calendar`), never market data, so they are known in advance.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from swing_engine.data.calendar import trading_days
from swing_engine.features.patterns2 import local_day

WEEK = "W-FRI"
MONTH_PAD_DAYS = 40
WEEK_PAD_DAYS = 10


def session_day(rows: pd.DataFrame) -> date | None:
    """The as-of session of ``rows`` (one row per symbol from ``rows_as_of`` / ``as_of_view``)."""
    return None if rows.empty else local_day(rows["ts"]).max().date()


def month_offsets(day: date) -> tuple[int, int]:
    """(k, -m): ``day`` is the k-th NYSE session of its month and the m-th from its end (last session = -1);
    (0, 0) when ``day`` is not an NYSE session."""
    first = day.replace(day=1)
    nxt = (first + timedelta(days=MONTH_PAD_DAYS)).replace(day=1)
    sessions = trading_days(first, nxt - timedelta(days=1))
    if day not in sessions:
        return 0, 0
    i = sessions.index(day)
    return i + 1, i - len(sessions)


def is_week_end(day: date) -> bool:
    """True when the next NYSE session falls in a later W-FRI week than ``day``."""
    nxt = trading_days(day + timedelta(days=1), day + timedelta(days=WEEK_PAD_DAYS))
    return bool(nxt) and pd.Period(nxt[0], WEEK) != pd.Period(day, WEEK)
