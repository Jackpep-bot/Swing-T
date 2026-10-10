"""Gandalf Project Research System (long), docs/strategies/gandalf_project_research_system.md (thinkorswim built-in,
D'Errico & Trombetta S&C 2017). A GA-mined candle ordering; zero evidence, shadow noise benchmark.

Buy at the close of bar t (index [k] = k bars ago; ohlc4 = (O+H+L+C)/4, median = (H+L)/2, mid-body = (O+C)/2) when
set A: ohlc4[1] < median[1], median[2] <= ohlc4[1], median[2] <= ohlc4[3]; or set B: ohlc4[1] < median[3],
midbody[0] < median[2], midbody[1] < midbody[2]. Filter trend_state >= 0 and an engine stop of 1.5 x atr_14 (card).
Exits (card): after `exit_length` = `max_hold_days` = 5 bars; after `exit_gain_bars` = 2 bars (exit gain length, card v1)
with the close above the entry fill; and while losing (close below the entry fill) on weakness set C or D
(features.extra `gandalf_weak`, exact equality in C as the card). Both lengths are arbitrary and logged as such.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import PositionContext, Signal
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
    entry_price,
    finite,
)

NAME = "gandalf_project_research_system"
ARRAYS = ("open", "high", "low", "close")
LAGS = 4
WEAK = "gandalf_weak"


def gandalf_buy(w: dict[str, np.ndarray]) -> bool:
    o, h, lo, c = (w[k][-LAGS:][::-1] for k in ARRAYS)  # index 0 = as-of bar, 3 = three bars ago
    if len(c) < LAGS or not np.isfinite([o, h, lo, c]).all():
        return False
    ohlc4, median, mid = (o + h + lo + c) / 4.0, (h + lo) / 2.0, (o + c) / 2.0
    set_a = ohlc4[1] < median[1] and median[2] <= ohlc4[1] and median[2] <= ohlc4[3]
    set_b = ohlc4[1] < median[3] and mid[0] < median[2] and mid[1] < mid[2]
    return bool(set_a or set_b)


@register("strategy", NAME)
class GandalfProjectResearchSystem(PanelStrategy):
    name = NAME
    description = "Candle-structure weakness dip-buy (ohlc4 / median / mid-body orderings); 5-bar time exit."
    default_params: dict[str, Any] = {
        "stop_atr_mult": 1.5,  # card: engine stop entry - 1.5 x atr_14
        "max_hold_days": 5,  # card: exit_length 5 (engine v1, arbitrary, not tuned)
        "exit_gain_bars": 2,  # card: exit_gain_length 2 (engine v1): exit once held >= 2 bars and close > entry
        "exit_on_weakness": True,  # card: exit a losing trade on weakness set C or D
        P_MIN_TREND: TREND_FLAT,  # card: filter trend_state >= 0
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["atr_14", "trend_state"]
    extra_features = [WEAK]

    def should_exit(self, row: pd.Series, bars_held: int, position: PositionContext | None = None) -> bool:
        fill = entry_price(position)
        if fill is None:
            return False
        close = float(row["close"])
        if bars_held >= int(self.params["exit_gain_bars"]) and close > fill:
            return True
        return bool(self.params["exit_on_weakness"]) and close < fill and row.get(WEAK) == 1.0

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        view = c1.view(self, panel, as_of, list(ARRAYS))
        mult = float(self.params["stop_atr_mult"])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            atr = row["atr_14"]
            if not finite(atr) or not self.trend_ok(row) or not gandalf_buy(view.window(str(row[SYMBOL]), ARRAYS)):
                continue
            close = float(row["close"])
            sig = self.build_signal(row, as_of, entry=close, stop=close - mult * float(atr), target=None, score=0.0,
                                    features={"max_hold_days": self.params["max_hold_days"]},
                                    notes="Gandalf candle-weakness entry; 5-bar time exit")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
