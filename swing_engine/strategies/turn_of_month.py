"""Turn-of-the-month window (long), docs/strategies/turn_of_month.md (catalog E33; card's `tom_index` comparison).

Academic window: own the market from the last trading day of a month (day -1) through the 3rd trading day of the
next (day +3), on NYSE trading days (published calendar, `_catalog3.month_offsets`). The engine fills at the next
open, so the signal is the close of day `signal_tom_day` (-2: entry at the open of day -1) and the time exit after
`max_hold_days` 4 sessions is the close of day +3. The QS index rule (buy the close of day -5, sell day +3) is
`signal_tom_day: -6, max_hold_days: 8`. Disaster stop 3 x atr_14, no target (card). Trades
`symbols` (default SPY, the card's index replay); None scans every symbol as a single-stock timing tilt.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy, finite
from ._catalog3 import month_offsets, session_day

NAME = "turn_of_month"


@register("strategy", NAME)
class TurnOfMonth(PanelStrategy):
    name = NAME
    description = "Hold SPY from the open of month-end day -1 to the close of day +3; 3 ATR disaster stop."
    default_params: dict[str, Any] = {
        "signal_tom_day": -2,  # card: academic window -1..+3; next-open fill => signal at the close of day -2
        "symbols": ["SPY"],  # card: `tom_index` replay on SPY; None = every scanned symbol
        "stop_atr_mult": 3.0,  # card: stop 3 x atr_14 as a disaster stop only
        "max_hold_days": 4,  # card: hold days -1, +1, +2, +3 (QS variant: 8, card's max_hold_days)
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: overlay, no regime gate in the index replay
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["atr_14"]
    engine_trail = False  # calendar hold; the card exits by time only

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        rows = c1.rows(self, panel, as_of)
        syms = self.params.get("symbols")
        if syms:
            rows = rows.loc[rows[SYMBOL].isin([str(s) for s in syms])]
        day = session_day(rows)
        k = int(self.params["signal_tom_day"])
        if day is None or k not in month_offsets(day):
            return []
        mult = float(self.params["stop_atr_mult"])
        out: list[Signal] = []
        for _, row in rows.iterrows():
            atr, close = row["atr_14"], float(row["close"])
            if not finite(atr):
                continue
            sig = self.build_signal(row, as_of, entry=close, stop=close - mult * float(atr), target=None, score=0.0,
                                    features={"tom_day": k, "max_hold_days": self.params["max_hold_days"]},
                                    notes=f"turn of month: signal on day {k}, time exit after "
                                    f"{int(self.params['max_hold_days'])} sessions")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
