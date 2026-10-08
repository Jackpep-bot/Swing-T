"""Jeff Cooper Expansion Pivot (long), docs/strategies/expansion_pivot_cooper.md (catalog C21, Hit and Run Trading
ch. 8).

Rule (exact on daily bars): today's high-low range exceeds each of the previous 9 sessions' ranges; yesterday or
today the low was at or below the 50-day SMA; today closes above it. Next session: buy stop a tick above the
expansion bar's high (entry_type stop); stop a tick under its low. Cooper exits "in a few days, then trail": the
card's engine spec is a 2R reference target and a 7-session time exit (the engine's breakeven / trail overlay stays
on). Optional `trend_ma` (sma_200) filter is off. Long only.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import EntryType, Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "expansion_pivot_cooper"


@register("strategy", NAME)
class ExpansionPivotCooper(PanelStrategy):
    name = NAME
    description = "Widest range in 10 sessions crossing up through sma_50; buy stop over the high, stop under the low."
    default_params: dict[str, Any] = {
        "range_lookback": 9,  # card: range larger than each of the previous 9 sessions (fixed by Cooper)
        "ma": "sma_50",  # card: 50-day MA
        "tick": 0.01,  # card: buy a few cents above the high / stop just below the low
        "target_r": 2.0,  # card: reference 2R
        "max_hold_days": 7,  # card
        "trend_ma": None,  # card optional variant: close > sma_200
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 2.0,  # card
    }
    features_required = ["sma_50"]

    def required_features(self) -> list[str]:
        cols = [*self.features_required, str(self.params["ma"])]
        trend = self.params.get("trend_ma")
        return list(dict.fromkeys([*cols, str(trend)] if trend else cols))

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        n, ma_col, tick = int(p["range_lookback"]), str(p["ma"]), float(p["tick"])
        trend = p.get("trend_ma")
        view = as_of_view(panel, as_of, ["high", "low", "close", *self.required_features()])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            w = view.window(str(row[SYMBOL]), ("high", "low"))
            if len(w["high"]) < n + 2:
                continue
            rng = w["high"][-(n + 1) :] - w["low"][-(n + 1) :]
            ma, close = row[ma_col], float(row["close"])
            if not (finite(ma) and np.isfinite(rng).all()) or not rng[-1] > rng[:-1].max():
                continue
            if not (min(w["low"][-2], w["low"][-1]) <= float(ma) < close):
                continue
            if trend and not (finite(row[str(trend)]) and close > float(row[str(trend)])):
                continue
            entry, stop = float(row["high"]) + tick, float(row["low"]) - tick
            sig = self.build_signal(
                row,
                as_of,
                entry=entry,
                stop=stop,
                target=entry + float(p["target_r"]) * (entry - stop),
                score=float(rng[-1] / rng[:-1].mean()) if rng[:-1].mean() > 0 else 0.0,
                features={"range": rng[-1], "max_prior_range": rng[:-1].max(), ma_col: ma,
                          "max_hold_days": p["max_hold_days"]},
                notes=f"expansion pivot through {ma_col} {float(ma):.2f}: buy stop {entry:.2f}, stop {stop:.2f}",
            )
            if sig:
                out.append(sig.model_copy(update={"entry_type": EntryType.STOP}))
        self.log_scan(as_of, len(view.current), len(out))
        return out
