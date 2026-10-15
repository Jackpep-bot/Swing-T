"""Fibonacci retracement pullback (long), docs/strategies/fibonacci_retracement_pullback.md (catalog B71/C48).

Impulse (in-module swing labelling, engine choice): impulse high = highest high of the `swing_lookback` bars before
the as-of bar, at least `min_pullback_bars` bars back; impulse low = lowest low of the `swing_lookback` bars before
that high; size >= 3 x atr_14 (card). Long on bar t when trend_state == 1, the lowest low of the last 3 bars sits in
the 38.2-61.8% retracement zone, no close since the impulse high went below the 78.6% level, and close_t > high_{t-1}
(card confirmation). Entry next open. Stop = min(78.6% level, lowest low since the high) - 0.1 x atr_14; target = the
impulse high; 15-session time stop; min reward:risk 1.5. The 50%-only control is `zone_low/zone_high` 0.45/0.55.
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
    TREND_FLAT,
    TREND_UP,
    PanelStrategy,
    finite,
)

NAME = "fibonacci_retracement_pullback"


@register("strategy", NAME)
class FibonacciRetracementPullback(PanelStrategy):
    name = NAME
    description = "Uptrend pullback into the 38.2-61.8% Fibonacci zone of a 3-ATR impulse; buy close > prior high."
    default_params: dict[str, Any] = {
        "swing_lookback": 40,  # engine choice: impulse high within the last 40 bars, impulse low 40 bars before it
        "min_pullback_bars": 2,  # engine choice: the high is at least 2 bars before t (a pullback exists)
        "min_impulse_atr": 3.0,  # card: impulse size >= 3 x atr_14
        "zone_low": 0.382,  # card: entry zone 0.382-0.618 (control: 0.45-0.55)
        "zone_high": 0.618,
        "zone_bars": 3,  # card: min(low over the last 3 bars) in the zone
        "invalid_level": 0.786,  # card: no close below the 0.786 level since the impulse high
        "stop_atr_buffer": 0.1,  # card: stop = min(level_0.786, lowest low) - 0.1 x atr_14
        "max_hold_days": 15,  # card: max_hold_days 15
        P_MIN_TREND: TREND_UP,  # card: trend_state == 1
        P_MIN_MARKET_TREND: TREND_FLAT,
        P_MIN_RR: 1.5,  # card: min_reward_risk 1.5
    }
    features_required = ["atr_14", "trend_state"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        p = self.params
        v = c1.view(self, panel, as_of, [])
        n, min_pb = int(p["swing_lookback"]), int(p["min_pullback_bars"])
        out: list[Signal] = []
        for _, row in v.current.iterrows():
            atr = row["atr_14"]
            if not finite(atr) or not self.trend_ok(row):
                continue
            w = v.window(str(row[SYMBOL]), ["high", "low", "close"])
            hi, lo, cl = w["high"], w["low"], w["close"]
            t = len(cl) - 1
            if t < 2 * n or not cl[t] > hi[t - 1]:
                continue
            h = t - n + int(np.argmax(hi[t - n : t]))
            if t - h < min_pb:
                continue
            top, bottom = float(hi[h]), float(np.min(lo[h - n : h]))
            size = top - bottom
            if size < float(p["min_impulse_atr"]) * float(atr):
                continue
            retr = (top - float(np.min(lo[t - int(p["zone_bars"]) + 1 : t + 1]))) / size
            invalid = top - float(p["invalid_level"]) * size
            if not float(p["zone_low"]) <= retr <= float(p["zone_high"]) or np.any(cl[h + 1 : t + 1] < invalid):
                continue
            close, mid = float(cl[t]), (float(p["zone_low"]) + float(p["zone_high"])) / 2.0
            stop = min(invalid, float(np.min(lo[h + 1 : t + 1]))) - float(p["stop_atr_buffer"]) * float(atr)
            sig = self.build_signal(row, as_of, entry=close, stop=stop, target=top, score=-abs(retr - mid),
                                    features={"retr_pct": retr, "impulse_high": top, "impulse_low": bottom,
                                              "max_hold_days": p["max_hold_days"]},
                                    notes=f"Fib pullback: {retr * 100:.0f}% retracement of {bottom:.2f}->{top:.2f}, "
                                    f"close {close:.2f} > prior high")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(v.current), len(out))
        return out
