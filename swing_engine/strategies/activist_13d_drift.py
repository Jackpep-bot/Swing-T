"""Activist Schedule 13D drift (long): docs/strategies/activist_13d_drift.md (Brav, Jiang, Partnoy, Thomas 2008).

Signal on the first session whose close can react to an ORIGINAL Schedule 13D (`days_since_13d == 0`, from
`data.filings`, dated by EDGAR acceptance time); the engine buys the next open, i.e. the session after the filing
became public. Stop entry - `stop_atr_mult` x atr_14, no target, time exit after `max_hold_days` (card: 5-20).
Approximation: every original 13D counts, not only hedge-fund activists (the submissions JSON names no filer type),
which dilutes the published sample. No signals when the panel has no `days_since_13d` column.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, finite

NAME = "activist_13d_drift"
COL = "days_since_13d"


@register("strategy", NAME)
class Activist13DDrift(PanelStrategy):
    name = NAME
    description = "Buy the session after an original Schedule 13D is public; ATR stop, 10-session time exit."
    default_params: dict[str, Any] = {
        "signal_day": 0,  # sessions after the 13D reaction session (0 = that session's close, fill next open)
        "stop_atr_mult": 2.0,  # card: catastrophic 2 x atr_14 stop
        "max_hold_days": 10,  # card: 5-20 sessions; Brav et al. show the drift through day +20
        "min_price": 5.0,  # card: skip sub-$5 targets (spread cost)
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: no market gate
        P_MIN_RR: 0.0,  # time exit, no target
    }
    features_required = ["atr_14"]
    engine_trail = False  # card: the drift is slow; a breakeven/N-day-low overlay would cut it

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if COL not in panel.columns or not self.market_ok(regime):
            return []
        rows = self.rows_as_of(panel, as_of, required=[*self.features_required, COL])
        out: list[Signal] = []
        for _, row in rows.iterrows():
            d, atr, close = row[COL], row["atr_14"], float(row["close"])
            if not (finite(d) and finite(atr)) or int(d) != int(self.params["signal_day"]):
                continue
            if close < float(self.params["min_price"]):
                continue
            sig = self.build_signal(
                row, as_of, entry=close, stop=close - float(self.params["stop_atr_mult"]) * float(atr), target=None,
                score=0.0, features={COL: d, "atr_14": atr, "max_hold_days": self.params["max_hold_days"]},
                notes="original Schedule 13D public; drift hold",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
