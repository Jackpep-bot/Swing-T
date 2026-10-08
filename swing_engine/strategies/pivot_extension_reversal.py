"""Pivot Extension reversal (long), docs/strategies/pivot_extension_reversal.md (TradeStation Pivot Extension LE,
TradingView Pivot Extension; catalog B80/P14). Counter-trend demonstration kept as a swing-low baseline.

A pivot low with `left` = 4 strictly higher lows before it and `right` = 2 after it is confirmed on bar t = i + 2
(features.extra.last_pivot, no look-ahead); buy the next open. Stop = pivot low - 0.1 x atr_14; target = entry + 2R,
or the latest confirmed pivot high (same strengths) when it lies above the entry, is closer and still gives
`min_reward_risk` 1.5 (card). 10-session cap. Raw vendor rule by default; the card's filtered variant is
`min_trend_state: 1`.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.features.extra import last_pivot

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "pivot_extension_reversal"
ARRAYS = ("high", "low", "close")


@register("strategy", NAME)
class PivotExtensionReversal(PanelStrategy):
    name = NAME
    description = "Buy the bar after a confirmed 4/2 pivot low; stop under it, 2R or prior pivot-high target."
    default_params: dict[str, Any] = {
        "left": 4,  # card: LeftStrength 4
        "right": 2,  # card: RightStrength 2
        "stop_atr_buffer": 0.1,  # card: stop = pivot low - 0.1 x atr_14
        "target_r": 2.0,  # card: entry + 2R ...
        "max_hold_days": 10,  # card
        P_MIN_TREND: TREND_DOWN,  # card variant (a) raw; (b) = TREND_UP
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 1.5,  # card: ... or the pivot high when >= 1.5R
    }
    features_required = ["atr_14", "trend_state"]

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        view = c1.view(self, panel, as_of, list(ARRAYS))
        left, right = int(self.params["left"]), int(self.params["right"])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            atr = row["atr_14"]
            if not finite(atr) or not self.trend_ok(row):
                continue
            w = view.window(str(row[SYMBOL]), ARRAYS)
            t = len(w["close"]) - 1
            lows, idx = last_pivot(w["low"], left, right, highs=False)
            if idx[t] != t - right:
                continue  # no pivot low confirmed on this bar
            close, low = float(w["close"][t]), float(lows[t])
            stop = low - float(self.params["stop_atr_buffer"]) * float(atr)
            target = close + float(self.params["target_r"]) * (close - stop)
            highs, _ = last_pivot(w["high"], left, right, highs=True)
            if finite(highs[t]) and close < highs[t] < target:
                target = float(highs[t])
            sig = self.build_signal(row, as_of, entry=close, stop=stop, target=target, score=0.0,
                                    features={"pivot_low": low, "max_hold_days": self.params["max_hold_days"]},
                                    notes=f"pivot low {low:.2f} ({left}/{right}) confirmed; target {target:.2f}")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
