"""Santa Claus rally window (long SPY): docs/strategies/santa_claus_rally.md (Hirsch, Stock Trader's Almanac).

Window = the last 5 December sessions plus the first 2 January sessions. The card's replay variant enters at the open
of the first window session, so the signal fires at the close of the 6th-to-last December session (found from the
published NYSE calendar, `data.calendar.trading_days`), exits by time after 7 sessions (`max_hold_days`, the 2nd
January close) and carries the card's catastrophic stop of 3 x atr_14. No target.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.data.calendar import trading_days

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_FLAT, TS, PanelStrategy, finite

NAME = "santa_claus_rally"
DECEMBER = 12
LAST_DAY = 31


@register("strategy", NAME)
class SantaClausRally(PanelStrategy):
    name = NAME
    description = "Long SPY at the close before the last 5 December sessions; out at the 2nd January close."
    default_params: dict[str, Any] = {
        "symbols": ["SPY"],  # card: instrument is the S&P 500 (SPY)
        "dec_sessions": 5,  # card: window covers the last 5 December sessions ...
        "max_hold_days": 7,  # ... plus the first 2 January sessions (7 sessions, exit at the 2nd January close)
        "stop_atr_mult": 3.0,  # card: catastrophic stop 3 x atr_14
        P_MIN_MARKET_TREND: TREND_FLAT,  # card router note: tie-breaker only, never overrides a correction
        P_MIN_RR: 0.0,  # time exit, no target
    }
    features_required = ["atr_14"]

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        rows = self.rows_as_of(panel, as_of)
        if rows.empty:
            return []
        session = pd.Timestamp(rows[TS].iloc[0]).date()
        dec_end = date(session.year, DECEMBER, LAST_DAY)
        n = int(self.params["dec_sessions"])
        if session.month != DECEMBER or len(trading_days(session + timedelta(days=1), dec_end)) != n:
            return []
        out: list[Signal] = []
        symbols = set(self.params["symbols"] or [])
        for _, row in rows.iterrows():
            atr = row["atr_14"]
            if (symbols and str(row[SYMBOL]) not in symbols) or not finite(atr):
                continue
            close = float(row["close"])
            sig = self.build_signal(
                row, as_of, entry=close, stop=close - float(self.params["stop_atr_mult"]) * float(atr), target=None,
                score=1.0, features={"atr_14": atr, "max_hold_days": self.params["max_hold_days"]},
                notes=f"Santa Claus window starts next session ({n} December + 2 January sessions)",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
