"""80-20 reversal (long), Raschke & Connors: docs/strategies/eighty_twenty_reversal.md, catalog C2 (Street Smarts).

Setup bar (yesterday): opened in the top 20% of its range and closed in the bottom 20%. Today trades at least
0.1 x atr_14 (yesterday's) under yesterday's low and comes back through it. Taught entry: a buy stop at yesterday's low
after the flush, stop near today's low, day trade or 1-2 days.

Approximation: the engine has no "stop that arms only after an undercut" order and no intraday bars, so the signal
is confirmed at today's close (the low undercut yesterday's low and the close is back above it), entered at the next
open with the stop at today's low - 0.01, and held at most 2 sessions (the card's swing variant). This is later than
the taught intraday entry. Short mirror not built.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, finite

NAME = "eighty_twenty_reversal"


@register("strategy", NAME)
class EightyTwentyReversal(PanelStrategy):
    name = NAME
    description = "Yesterday opened top 20% / closed bottom 20%; today undercuts its low and closes back above it."
    default_params: dict[str, Any] = {
        "open_pos_min": 0.8,  # card: open in the top 20% of the range
        "close_pos_max": 0.2,  # card: close in the bottom 20%
        "undercut_atr": 0.1,  # card: low_t < low_{t-1} - 0.1 x atr_14_{t-1} (5-15 ticks)
        "stop_tick": 0.01,  # card: stop = low_t - 0.01
        "max_hold_days": 2,  # card: swing variant, max_hold_days 2
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: choppy / narrow_uptrend via the router
        P_MIN_RR: 0.0,  # card: no target taught
    }
    features_required = ["atr_14"]
    extra_features = ["prev_atr_14"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        out: list[Signal] = []
        for _, row in rows.iterrows():
            po, ph, pl, pc, patr = (row[c] for c in ("prior_open", "prior_high", "prior_low", "prior_close", "prev_atr_14"))
            if not all(finite(x) for x in (po, ph, pl, pc, patr)) or ph <= pl:
                continue
            open_pos, close_pos = (po - pl) / (ph - pl), (pc - pl) / (ph - pl)
            if open_pos < float(p["open_pos_min"]) or close_pos > float(p["close_pos_max"]):
                continue
            low, close = float(row["low"]), float(row["close"])
            if not (low < pl - float(p["undercut_atr"]) * patr and close > pl):
                continue
            sig = self.build_signal(
                row, as_of, entry=close, stop=low - float(p["stop_tick"]), target=None, score=(pl - low) / patr,
                features={"setup_open_pos": open_pos, "setup_close_pos": close_pos, "undercut_atr": (pl - low) / patr,
                          "max_hold_days": p["max_hold_days"]},
                notes=f"80-20: setup bar open {open_pos:.0%} / close {close_pos:.0%} of range; undercut {pl:.2f} "
                f"to {low:.2f}, closed back at {close:.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
