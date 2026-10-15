"""D'Errico Price Swing detector (long), docs/strategies/derrico_price_swing.md (catalog B22, thinkorswim PriceSwing).

`swing_type` picks one upswing definition (each is its own trial):
1 pivot: low[t] > low[t-1] after low[t-1] < low[t-2];  2 Bollinger: close crosses back above bb_lower_20;
3 RSI: rsi_14 crosses above 40;  4 RSI + higher low: low[t] > low[t-1] while rsi_14 < 40.
Exit by time after 20 bars (original). The original has no stop and no filter; the card's engine choices add
`trend_state >= 0` and a 2 x atr_14 stop. RSI(14) and BB(20, 2) defaults are the card's assumption (tos text truncated).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
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

NAME = "derrico_price_swing"
ARRAYS = ("low", "close", "bb_lower_20", "rsi_14")


def upswing(w: dict[str, np.ndarray], t: int, swing_type: int, oversold: float) -> bool:
    lo, c, bb, r = w["low"], w["close"], w["bb_lower_20"], w["rsi_14"]
    if swing_type == 1:
        return t >= 2 and lo[t] > lo[t - 1] and lo[t - 1] < lo[t - 2]
    if swing_type == 2:
        return t >= 1 and c[t] > bb[t] and c[t - 1] <= bb[t - 1]
    if swing_type == 3:
        return t >= 1 and r[t] > oversold and r[t - 1] <= oversold
    if swing_type == 4:
        return t >= 1 and lo[t] > lo[t - 1] and r[t] < oversold
    raise ValueError(f"{NAME}: swing_type must be 1-4, got {swing_type}")


@register("strategy", NAME)
class DerricoPriceSwing(PanelStrategy):
    name = NAME
    description = "Buy each upswing of the chosen type (pivot / BB cross / RSI 40 cross / higher low); 20-bar exit."
    default_params: dict[str, Any] = {
        "swing_type": 3,  # card: four variants 1-4 (each a separate trial)
        "rsi_oversold": 40.0,  # card/tos: oversold 40
        "stop_atr_mult": 2.0,  # card engine choice: entry - 2 x atr_14
        "max_hold_days": 20,  # card/tos: time exit after 20 bars
        P_MIN_TREND: TREND_FLAT,  # card engine choice: trend_state >= 0
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["atr_14", "trend_state", "rsi_14"]
    extra_features = ["bb_lower_20"]  # contract column; listed so features.extra fills it when a panel lacks it

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        view = c1.view(self, panel, as_of, list(ARRAYS))
        st, os_, mult = int(self.params["swing_type"]), float(self.params["rsi_oversold"]), float(self.params["stop_atr_mult"])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            atr = row["atr_14"]
            if not finite(atr) or not self.trend_ok(row):
                continue
            w = view.window(str(row[SYMBOL]), ARRAYS)
            if not upswing(w, len(w["close"]) - 1, st, os_):
                continue
            close = float(row["close"])
            sig = self.build_signal(row, as_of, entry=close, stop=close - mult * float(atr), target=None, score=0.0,
                                    features={"swing_type": st, "rsi_14": row["rsi_14"],
                                              "max_hold_days": self.params["max_hold_days"]},
                                    notes=f"price swing type {st} upswing; {int(self.params['max_hold_days'])}-bar exit")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
