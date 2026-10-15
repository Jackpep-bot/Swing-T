"""Pivot Reversal (long), TradeStation Pivot Reversal LE: docs/strategies/pivot_reversal_breakout.md, catalog B80/P15.

Pivot high = a bar strictly above the 4 bars on each side (strength 4/4), known only 4 bars later
(`features.extra.last_pivot`). While the latest confirmed pivot high is at most 30 bars old, untouched since, and
above the close, place a buy stop 0.01 over it (`entry_type = stop`, one session; the daily re-scan stands in for
the good-until-filled order). Stop: the latest confirmed pivot low - 0.01, then trailed up to each newer confirmed
pivot low (`trail_stop`, ratchet only). trend_state >= 0. No target; 20-session time stop. The TradingView 4/2
variant and the stop-and-reverse short side are not built.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import EntryType, Signal
from swing_engine.core.registry import register
from swing_engine.features.extra import last_pivot
from swing_engine.features.patterns2 import as_of_view

from ._base import (
    P_MIN_MARKET_TREND,
    P_MIN_RR,
    P_MIN_TREND,
    SYMBOL,
    TREND_DOWN,
    TREND_FLAT,
    PanelStrategy,
    finite,
)

NAME = "pivot_reversal_breakout"
LEFT = RIGHT = 4  # card: TradeStation strength 4 (4 lower highs on each side)
PIVOT_LOW = f"last_pivot_low_{LEFT}_{RIGHT}"


@register("strategy", NAME)
class PivotReversalBreakout(PanelStrategy):
    name = NAME
    description = "Buy stop over the latest confirmed 4/4 pivot high; stop and trail under confirmed pivot lows."
    default_params: dict[str, Any] = {
        "max_pivot_age": 30,  # card: pivot age <= 30 bars
        "tick": 0.01,  # card: buy stop pivot high + 0.01; stop pivot low - 0.01
        "max_hold_days": 20,  # card
        P_MIN_TREND: TREND_FLAT,  # card: trend_state >= 0
        P_MIN_MARKET_TREND: TREND_DOWN,  # control for sr_breakout; no market gate in the source
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["trend_state"]
    extra_features = [PIVOT_LOW]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def trail_stop(self, row: pd.Series) -> float | None:
        level = row.get(PIVOT_LOW)
        return float(level) - float(self.params["tick"]) if finite(level) else None

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        view = as_of_view(panel, as_of, ["open", "high", "low", "close", *self.required_features()])
        tick = float(p["tick"])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            if not self.trend_ok(row):
                continue
            w = view.window(str(row[SYMBOL]), ["high", "low"])
            t = len(w["high"]) - 1
            hi_lvl, hi_idx = last_pivot(w["high"], LEFT, RIGHT, highs=True)
            lo_lvl = last_pivot(w["low"], LEFT, RIGHT, highs=False)[0]
            i, pivot, base = int(hi_idx[t]), hi_lvl[t], lo_lvl[t]
            if i < 0 or t - i > int(p["max_pivot_age"]) or not finite(base):
                continue
            if float(row["close"]) >= pivot or np.max(w["high"][i + 1 : t + 1]) >= pivot:
                continue  # already above, or the stop would have filled on an earlier bar
            entry, stop = float(pivot) + tick, float(base) - tick
            sig = self.build_signal(
                row, as_of, entry=entry, stop=stop, target=None, score=-(t - i),
                features={"pivot_high": pivot, "pivot_low": base, "pivot_age": t - i, "max_hold_days": p["max_hold_days"]},
                notes=f"buy stop {entry:.2f} over the {LEFT}/{RIGHT} pivot high {t - i} bars old; stop {stop:.2f}",
            )
            if sig:
                out.append(sig.model_copy(update={"entry_type": EntryType.STOP}))
        self.log_scan(as_of, len(view.current), len(out))
        return out
