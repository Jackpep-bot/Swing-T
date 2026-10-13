"""Turtle Soup Plus One (long; Raschke & Connors, Street Smarts): docs/strategies/turtle_soup.md.

Day 1 (the signal bar): a new 20-day low (low < L, L = min(low) of the 20 bars before it), the bar that set L at least
`min_age` sessions earlier, and the close at or below L. Day 2: buy stop at L (`EntryType.STOP`: fills at
max(open, L) when the high reaches it, else the order expires), exactly the card's daily rule. Stop: day-1 low minus a
buffer (the lower of the day-1/day-2 lows is not knowable at the signal). No target; the engine's breakeven/N-day-low
trail stands in for "trail as it becomes profitable"; 5-day time stop. Same-day Turtle Soup needs the intrabar order
of the undercut and the reclaim (card: ambiguous on daily bars) and is not modelled; the short side is not used.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import EntryType, Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "turtle_soup"


@register("strategy", NAME)
class TurtleSoupPlusOne(PanelStrategy):
    name = NAME
    description = "Turtle Soup Plus One: close at/below a 20-day low set >= 3 bars ago; buy stop at that low next day."
    default_params: dict[str, Any] = {
        "channel": 20,  # card: 20-day low
        "min_age": 3,  # card: Plus One, prior 20-day low at least 3 sessions earlier
        "stop_buffer_pct": 0.001,  # card: ticks -> 0.05-0.10% of price for stocks
        "sma_filter": None,  # card: compare close > sma_200 ("sma_200") vs none
        "max_hold_days": 5,  # card
        P_MIN_TREND: TREND_DOWN,
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no target taught
    }
    features_required = ["trend_state"]

    def required_features(self) -> list[str]:
        f = self.params.get("sma_filter")
        return [*self.features_required, str(f)] if f else list(self.features_required)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        n, min_age, buf = int(p["channel"]), int(p["min_age"]), float(p["stop_buffer_pct"])
        view = as_of_view(panel, as_of, ["open", "high", "low", "close", *self.required_features()])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            f = p.get("sma_filter")
            if not self.trend_ok(row) or (f and not (finite(row[f]) and row["close"] > row[f])):
                continue
            lows = view.window(str(row[SYMBOL]), ["low"])["low"]
            t = len(lows) - 1
            seg = lows[t - n : t] if t >= n else np.array([])
            if seg.size < n or not np.isfinite(seg).all():
                continue
            k = t - 1 - int(np.argmin(seg[::-1]))  # latest bar holding the low (ties count as the newer print)
            level, low, close = float(seg.min()), float(lows[t]), float(row["close"])
            if not (low < level and close <= level and t - k >= min_age):
                continue
            sig = self.build_signal(
                row, as_of, entry=level, stop=low * (1.0 - buf), target=None, score=(level - low) / level,
                features={"prior_low": level, "prior_low_age": t - k},
                notes=f"Turtle Soup +1: buy stop {level:.2f} (20-day low set {t - k} bars ago)",
            )
            if sig:
                out.append(sig.model_copy(update={"entry_type": EntryType.STOP}))
        self.log_scan(as_of, len(view.current), len(out))
        return out
