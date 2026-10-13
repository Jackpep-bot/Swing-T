"""Shared pieces of the batch-6 cards (docs/proposals/swing-methods-2026-10/batch6/README.md). Not a strategy.

``avoid(rows)``: `event_avoid_filters` rules 1-3 as batch 5 applied them (tax_loss_loser_rebound): a reverse split in
the last 252 sessions, an 8-K Item 1.03 / 3.01 in the last 126, an 8-K Item 5.02 in the last 63 with no earnings
reaction session in those 63. A column the panel lacks excludes nothing.

``MonthEndLoserBook``: the monthly book of the two reversal cards. A subclass gives ``scores(panel, as_of, rows)``
(low = most oversold, NaN = not eligible). On a month's last NYSE session: buy the `buy_count` lowest scores at the
next open (never a name inside ``avoid``); a held name is sold at the next open when it is not among the
`hold_count` lowest. Catastrophe stop `stop_pct` below the signal close; no target, no trail, no regime gate. Equal
weight and the name cap come from the book.

Deviation from the cards, as in batch 5's monthly books: the engine asks `should_exit` at a close before `signals`
sees that session, so the hold zone is the one `signals` measured at the previous close (kept on the instance): buys
rank on the month's last close, sells on the close before it. Without that zone (live: another process) nothing is
sold on rank. Scores are computed on those two sessions of a month only.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.data.calendar import next_trading_day, prev_trading_day

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, TS, PanelStrategy

SPLIT, DISTRESS, LEFT = "days_since_reverse_split", "days_since_8k_distress", "days_since_8k_502"  # data.b5_events
SINCE_EARNINGS = "days_since_earnings"  # data.fundamentals.join_edgar
AVOID_SPLIT_SESSIONS, AVOID_DISTRESS_SESSIONS, AVOID_502_SESSIONS = 252, 126, 63  # event_avoid_filters rules 1-3
SCORE = "score"


def _col(rows: pd.DataFrame, name: str) -> pd.Series:
    return rows[name].astype(float) if name in rows.columns else pd.Series(float("nan"), index=rows.index)


def avoid(rows: pd.DataFrame) -> pd.Series:
    """Boolean mask of ``rows`` inside `event_avoid_filters` rules 1-3 (False where a column is missing or NaN)."""
    left = (_col(rows, LEFT) <= AVOID_502_SESSIONS) & ~(_col(rows, SINCE_EARNINGS) <= AVOID_502_SESSIONS)
    return (_col(rows, SPLIT) <= AVOID_SPLIT_SESSIONS) | (_col(rows, DISTRESS) <= AVOID_DISTRESS_SESSIONS) | left


def is_month_end(day: date) -> bool:
    """True on the last NYSE session of a month (published calendar)."""
    return next_trading_day(day).month != day.month


def row_key(row: pd.Series) -> tuple[date | None, str | None]:
    """(session date, symbol) of a panel row (replay / live: `ts` and `symbol` fields; run_backtest: the index)."""
    ts, sym = row.get(TS), row.get(SYMBOL)
    if (ts is None or sym is None) and isinstance(row.name, tuple):
        ts, sym = row.name[0], row.name[1]
    return (None if ts is None or pd.isna(ts) else pd.Timestamp(ts).date()), (None if sym is None else str(sym))


class MonthEndLoserBook(PanelStrategy):
    BOOK_PARAMS: dict[str, Any] = {
        "buy_count": 50,  # cards: buy the 50 lowest scores
        "hold_count": 100,  # cards: keep a holding while it ranks in the lowest 100
        "stop_pct": 20.0,  # cards: catastrophe stop 20% from entry
        "max_hold_days": 10_000,  # the rank is the exit (finite so the 20-bar backtest default never applies)
        P_MIN_MARKET_TREND: TREND_DOWN,  # cards: no regime gate
        P_MIN_RR: 0.0,  # cards: no target
    }
    prior_columns: list[str] = []
    engine_trail = False  # rank exit only

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        self._zone: tuple[date, frozenset[str]] | None = None  # (session, symbols in the hold zone at its close)

    def scores(self, panel: pd.DataFrame, as_of: date, rows: pd.DataFrame) -> pd.Series:
        """Score per row of ``rows`` (index ``rows.index``): low = buy, NaN = not eligible."""
        raise NotImplementedError

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        """On a month's last session: sell a name that was outside the hold zone at the previous close."""
        day, sym = row_key(row)
        zone = self._zone
        if day is None or zone is None or not is_month_end(day):
            return False
        return zone[0] == prev_trading_day(day) and sym not in zone[1]

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        today = is_month_end(as_of)
        if not today and not is_month_end(next_trading_day(as_of)):
            return []
        rows = c1.rows(self, panel, as_of)
        if rows.empty:
            return []
        p = self.params
        score = self.scores(panel, as_of, rows).astype(float)
        order = score.dropna().sort_values(kind="mergesort")
        self._zone = (as_of, frozenset(rows.loc[order.index[: int(p["hold_count"])], SYMBOL].astype(str)))
        if not today:
            return []
        out: list[Signal] = []
        blocked = avoid(rows)
        for rank, idx in enumerate(order.index[: int(p["buy_count"])], 1):
            if bool(blocked[idx]):
                continue
            row, close = rows.loc[idx], float(rows.at[idx, "close"])
            sig = self.build_signal(row, as_of, entry=close, stop=close * (1.0 - float(p["stop_pct"]) / 100.0),
                                    target=None, score=-float(order[idx]), features={SCORE: order[idx], "rank": rank},
                                    notes=f"score {float(order[idx]):+.2f}, rank {rank} of {len(order)}")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
