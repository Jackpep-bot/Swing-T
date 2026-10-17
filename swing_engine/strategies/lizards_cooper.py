"""Jeff Cooper bullish Lizard (long), docs/strategies/lizards_cooper.md (Hit and Run Trading ch. 14, catalog C23).

Lizard bar at close t: low_t is the lowest low of the last 10 bars (including t) and both the open and the close sit
in the top 25% of the bar's range. Entry (book): buy stop one tick above the lizard high, next session only. Stop one
tick under the lizard low. No target; 5-session time stop (card: exit 1-5 days). The aggressive next-open entry is
`entry_style: "open"`. Bearish mirror not used (long-only). Minimum range (card, engine choice): the lizard
range must be at least 0.75 x atr_14 of the prior bar, so tiny-range bars do not qualify.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, PanelStrategy

NAME = "lizards_cooper"
LOW10 = "low_10"  # features.extra: lowest low of the last 10 bars including this one


@register("strategy", NAME)
class LizardsCooper(PanelStrategy):
    name = NAME
    description = "New 10-day low with open and close in the top 25% of the range; buy stop over its high."
    default_params: dict[str, Any] = {
        "min_open_pos": 0.75,  # card: (open - low) / range >= 0.75
        "min_close_pos": 0.75,  # card: (close - low) / range >= 0.75
        "min_range_atr": 0.75,  # card: (high - low) >= 0.75 x atr_14_{t-1} (engine choice)
        "entry_style": "stop",  # card: buy stop above the lizard high; "open" = aggressive next-open variant
        "tick": 0.01,  # card: high_t + 0.01 / low_t - 0.01
        "max_hold_days": 5,  # card: max_hold_days 5
        P_MIN_TREND: TREND_DOWN,
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["trend_state", "atr_14"]
    extra_features = [LOW10, "prev_atr_14"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        rows = c1.rows(self, panel, as_of)
        rng = rows["high"] - rows["low"]
        open_pos, close_pos = (rows["open"] - rows["low"]) / rng, (rows["close"] - rows["low"]) / rng
        keep = ((rng > 0) & (rng >= float(p["min_range_atr"]) * rows["prev_atr_14"]) & (rows["low"] <= rows[LOW10])
                & (open_pos >= float(p["min_open_pos"])) & (close_pos >= float(p["min_close_pos"]))).fillna(False)
        tick, as_stop = float(p["tick"]), p["entry_style"] == "stop"
        out: list[Signal] = []
        for idx, row in rows.loc[keep].iterrows():
            if not self.trend_ok(row):
                continue
            entry = float(row["high"]) + tick if as_stop else float(row["close"])
            sig = self.build_signal(row, as_of, entry=entry, stop=float(row["low"]) - tick, target=None,
                                    score=float(close_pos[idx]),
                                    features={"open_pos": open_pos[idx], "close_pos": close_pos[idx],
                                              "max_hold_days": p["max_hold_days"]},
                                    notes=f"lizard: new 10-day low {row['low']:.2f}, open/close in the top quarter")
            if sig:
                out.append(c1.stop_entry(sig) if as_stop else sig)
        self.log_scan(as_of, len(rows), len(out))
        return out

