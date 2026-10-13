"""Trendline break (long), docs/strategies/trendline_break.md (TradeStation Trendline LE, Finviz TL; no originator
rule, so entry/stop/target are the card's engine choices, logged as trials).

The line runs through the last two confirmed pivot highs (width 5 both sides, features.extra.last_pivot, known only
5 bars later), both confirmed by bar t-1, at most `lookback` bars old and descending. No close above the line from the
first pivot through t-1 (zero tolerance); trigger = close[t] above the line's value on bar t (TradeStation enters
intrabar on the high; the engine uses the close and the next open). Stop = lowest low since the last touch pivot -
0.25 x atr_14; target = the most recent confirmed pivot high above the entry, else entry + 2R; 15-session cap.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.features.extra import last_pivot

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "trendline_break"
ARRAYS = ("high", "low", "close")


@register("strategy", NAME)
class TrendlineBreak(PanelStrategy):
    name = NAME
    description = "Close above a falling line through the last two confirmed pivot highs; pivot-high or 2R target."
    default_params: dict[str, Any] = {
        "pivot_width": 5,  # card: pivot width 5 (levels.py default)
        "lookback": 120,  # card: lookback 20-120 bars
        "stop_atr_buffer": 0.25,  # card: stop = lowest low since the last touch - 0.25 x atr_14
        "target_r": 2.0,  # card: else entry + 2R
        "rvol_min": None,  # card: optional rvol_day >= 1.2 (off)
        "max_hold_days": 15,  # card
        P_MIN_TREND: TREND_DOWN,  # card: optional trend_state >= 0 (off)
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 2.0,  # card
    }
    features_required = ["atr_14", "trend_state", "rvol_day"]

    def _line(self, w: dict[str, np.ndarray], t: int) -> tuple[int, float, np.ndarray] | None:
        width = int(self.params["pivot_width"])
        _, idx = last_pivot(w["high"], width, width, highs=True)
        p2 = idx[t - 1]
        if p2 < 0:
            return None
        p1 = idx[p2 + width - 1]
        if p1 < 0 or t - p1 > int(self.params["lookback"]):
            return None
        slope = (w["high"][p2] - w["high"][p1]) / (p2 - p1)
        if not slope < 0:
            return None
        line = w["high"][p2] + slope * (np.arange(p1, t + 1) - p2)  # line value on bars p1..t
        c = w["close"][p1 : t + 1]
        if (c[:-1] > line[:-1]).any() or not c[-1] > line[-1]:
            return None
        return p2, float(line[-1]), idx

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        view = c1.view(self, panel, as_of, list(ARRAYS))
        rvol_min, width = self.params.get("rvol_min"), int(self.params["pivot_width"])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            atr = row["atr_14"]
            if not finite(atr) or not self.trend_ok(row):
                continue
            if rvol_min is not None and not (finite(row["rvol_day"]) and float(row["rvol_day"]) >= float(rvol_min)):
                continue
            w = view.window(str(row[SYMBOL]), ARRAYS)
            t = len(w["close"]) - 1
            if t < 1 or (hit := self._line(w, t)) is None:
                continue
            p2, level, idx = hit
            close = float(w["close"][t])
            stop = float(w["low"][p2 : t + 1].min()) - float(self.params["stop_atr_buffer"]) * float(atr)
            target, q = close + float(self.params["target_r"]) * (close - stop), p2
            while q >= 0 and t - q <= int(self.params["lookback"]):  # most recent confirmed pivot high above entry
                if w["high"][q] > close:
                    target = float(w["high"][q])
                    break
                q = idx[q + width - 1]
            sig = self.build_signal(row, as_of, entry=close, stop=stop, target=target, score=(close - level) / float(atr),
                                    features={"tl_value": level, "tl_pivot": w["high"][p2],
                                              "max_hold_days": self.params["max_hold_days"]},
                                    notes=f"trendline break: close {close:.2f} > line {level:.2f}")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
