"""FOMC-cycle even weeks (Cieslak, Morse & Vissing-Jorgensen, JF 2019): docs/proposals/swing-methods-2026-10/batch2/
fomc_cycle_even_weeks.md, pre-registered in docs/preregistration/2026-10-10-batch2.md.

Hold SPY on every "even-week" session of the cycle that starts at each scheduled FOMC announcement day (day 0):
sessions -1..3, 9..13, 19..23 and 29..33, counted in NYSE sessions. For a session, k_next = sessions to the next day
0 (negative) and k_prev = sessions since the latest day 0; k = k_next when -6 <= k_next <= -1, else k_prev. The
engine fills at the open, so the entry signal is the close of a non-even session whose next session is even, and
`should_exit` fires at the close of an even session whose next session is not (fill next open): each even session is
held open to next open. No stop in the card; the engine needs one to size, so a catastrophe stop sits `stop_pct`
below the signal close (a full-size position: the book's position cap binds, not the stop). No target, no regime
gate, `engine_trail = False`.

Calendar: `FOMC_DAY0` is the second day of each scheduled meeting as published by the Federal Reserve
(https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm and .../fomchistorical2016.htm ..
fomchistorical2020.htm; 2021-2027 re-read 2026-10-10). Scheduled dates are announced about a year ahead, so the
table is point-in-time; the 2020-03-18 meeting (replaced by the unscheduled 2020-03-15 one) stays as scheduled, and
unscheduled meetings and notation votes are not in it. Extend the table when the next year's schedule is published:
sessions more than 33 after the last listed day 0 are never even.
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import PositionContext, Signal
from swing_engine.core.registry import register
from swing_engine.data.calendar import next_trading_day, trading_days

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy
from ._catalog3 import session_day

NAME = "fomc_cycle_even_weeks"
FOMC_CALENDAR_VERSION = "2026.10.10"
_D0: dict[int, tuple[tuple[int, int], ...]] = {
    2016: ((1, 27), (3, 16), (4, 27), (6, 15), (7, 27), (9, 21), (11, 2), (12, 14)),
    2017: ((2, 1), (3, 15), (5, 3), (6, 14), (7, 26), (9, 20), (11, 1), (12, 13)),
    2018: ((1, 31), (3, 21), (5, 2), (6, 13), (8, 1), (9, 26), (11, 8), (12, 19)),
    2019: ((1, 30), (3, 20), (5, 1), (6, 19), (7, 31), (9, 18), (10, 30), (12, 11)),
    2020: ((1, 29), (3, 18), (4, 29), (6, 10), (7, 29), (9, 16), (11, 5), (12, 16)),  # Mar 18 scheduled, cancelled
    2021: ((1, 27), (3, 17), (4, 28), (6, 16), (7, 28), (9, 22), (11, 3), (12, 15)),
    2022: ((1, 26), (3, 16), (5, 4), (6, 15), (7, 27), (9, 21), (11, 2), (12, 14)),
    2023: ((2, 1), (3, 22), (5, 3), (6, 14), (7, 26), (9, 20), (11, 1), (12, 13)),
    2024: ((1, 31), (3, 20), (5, 1), (6, 12), (7, 31), (9, 18), (11, 7), (12, 18)),
    2025: ((1, 29), (3, 19), (5, 7), (6, 18), (7, 30), (9, 17), (10, 29), (12, 10)),
    2026: ((1, 28), (3, 18), (4, 29), (6, 17), (7, 29), (9, 16), (10, 28), (12, 9)),
    2027: ((1, 27), (3, 17), (4, 28), (6, 9), (7, 28), (9, 15), (10, 27), (12, 8)),
}
#: scheduled FOMC announcement days (day 0), ascending
FOMC_DAY0: tuple[date, ...] = tuple(date(y, m, d) for y, md in sorted(_D0.items()) for m, d in md)
#: card rule 2: weeks 0, 2, 4, 6 in sessions relative to day 0
EVEN_WEEK_DAYS: frozenset[int] = frozenset({-1, 0, 1, 2, 3, *range(9, 14), *range(19, 24), *range(29, 34)})
PRE_MEETING_SESSIONS = 6  # card: -6 <= k_next <= -1 counts from the next meeting (weeks -1 and the start of week 0)
CALENDAR_PAD_DAYS = 60


@lru_cache(maxsize=1)
def even_week_sessions() -> frozenset[date]:
    """Every NYSE session that is an even-week session of the FOMC cycle (published calendars only)."""
    sessions = trading_days(FOMC_DAY0[0] - timedelta(days=CALENDAR_PAD_DAYS), FOMC_DAY0[-1] + timedelta(days=CALENDAR_PAD_DAYS))
    pos = {d: i for i, d in enumerate(sessions)}
    zeros = np.array([pos[d] for d in FOMC_DAY0])  # KeyError: a listed day 0 is not an NYSE session
    out: set[date] = set()
    for i, d in enumerate(sessions):
        j = int(np.searchsorted(zeros, i, side="right"))  # day 0s on or before this session
        k_next = i - int(zeros[j]) if j < len(zeros) else None
        if k_next is not None and -PRE_MEETING_SESSIONS <= k_next <= -1:
            k = k_next
        elif j > 0:
            k = i - int(zeros[j - 1])
        else:
            continue
        if k in EVEN_WEEK_DAYS:
            out.add(d)
    return frozenset(out)


def _row_day(row: pd.Series) -> date | None:
    """Session date of a panel row (live: a `ts` field; run_backtest: the (ts, symbol) index)."""
    ts = row.get("ts")
    if ts is None and isinstance(row.name, tuple):
        ts = row.name[0]
    return None if ts is None or pd.isna(ts) else pd.Timestamp(ts).date()


@register("strategy", NAME)
class FomcCycleEvenWeeks(PanelStrategy):
    name = NAME
    description = "Long SPY only in even weeks (0, 2, 4, 6) of the scheduled FOMC cycle; cash otherwise."
    default_params: dict[str, Any] = {
        "symbols": ["SPY"],  # card: SPY only
        "stop_pct": 0.15,  # engine choice (card: no stop): catastrophe stop, not reachable in a normal even week
        "max_hold_days": 10_000,  # the calendar is the exit (finite so the 20-bar backtest default never applies)
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: no regime gate
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required: list[str] = []
    prior_columns: list[str] = []
    engine_trail = False  # calendar hold

    def should_exit(self, row: pd.Series, bars_held: int, position: PositionContext | None = None) -> bool:
        """At the close of a session whose next session is not an even-week session (fill next open)."""
        day = _row_day(row)
        return day is not None and next_trading_day(day) not in even_week_sessions()

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        rows = self.rows_as_of(panel, as_of)
        rows = rows.loc[rows[SYMBOL].isin([str(s) for s in self.params["symbols"]])]
        day = session_day(rows)
        even = even_week_sessions()
        if day is None or day in even or next_trading_day(day) not in even:
            return []
        out: list[Signal] = []
        for _, row in rows.iterrows():
            close = float(row["close"])
            sig = self.build_signal(row, as_of, entry=close, stop=close * (1.0 - float(self.params["stop_pct"])),
                                    target=None, score=0.0, notes="next session starts an FOMC even week")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
