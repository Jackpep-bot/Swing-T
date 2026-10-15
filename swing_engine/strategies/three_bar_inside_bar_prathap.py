"""Johnan Prathap Three-Bar Inside Bar (long), docs/strategies/three_bar_inside_bar_prathap.md (S&C Mar 2011, B39).

Bars 1..4 oldest to newest, bar 4 = the as-of bar t: close[t-2] > close[t-3] (bar 2 closed up), bar 3 inside bar 2
(`inside_day[t-1] == 1`), close[t] > close[t-1]. Entry next open. Default = the card's engine-native variant (b):
stop = min(low[t-1], low[t]) - 0.25 x atr_14, target 1.5R, 5-session time stop, min reward:risk 1.5. Variant (a),
the taught bracket (secondary source): `bracket_pct` 0.0075 sets stop and target 0.75% from entry and needs
`min_reward_risk` 1.0. Short mirror not used (long-only).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "three_bar_inside_bar_prathap"


@register("strategy", NAME)
class ThreeBarInsideBarPrathap(PanelStrategy):
    name = NAME
    description = "Up close, inside bar, higher close: buy next open; stop under the inside/signal low, 1.5R target."
    default_params: dict[str, Any] = {
        "stop_atr_buffer": 0.25,  # card (b): stop = min(low[t-1], low[t]) - 0.25 x atr_14
        "target_r": 1.5,  # card (b): target = entry + 1.5R
        "bracket_pct": None,  # card (a): 0.0075 = taught 0.75% stop and target (then min_reward_risk 1.0)
        "max_hold_days": 5,  # card (b): max_hold_days 5
        P_MIN_TREND: TREND_DOWN,  # card: no trend filter taught
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 1.5,  # card (b): 1.5
    }
    features_required = ["atr_14", "inside_day", "trend_state"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        p = self.params
        v = c1.view(self, panel, as_of, [])
        out: list[Signal] = []
        for _, row in v.current.iterrows():
            atr = row["atr_14"]
            if not finite(atr) or not self.trend_ok(row):
                continue
            w = v.window(str(row[SYMBOL]), ["low", "close", "inside_day"])
            c, t = w["close"], len(w["close"]) - 1
            if t < 3 or not (c[t - 2] > c[t - 3] and w["inside_day"][t - 1] == 1 and c[t] > c[t - 1]):
                continue
            close = float(c[t])
            if p["bracket_pct"] is not None:
                stop, target = close * (1 - float(p["bracket_pct"])), close * (1 + float(p["bracket_pct"]))
            else:
                stop = min(w["low"][t - 1], w["low"][t]) - float(p["stop_atr_buffer"]) * float(atr)
                target = close + float(p["target_r"]) * (close - stop)
            sig = self.build_signal(row, as_of, entry=close, stop=stop, target=target, score=close / c[t - 1] - 1.0,
                                    features={"max_hold_days": p["max_hold_days"]},
                                    notes=f"three-bar inside bar: close {close:.2f} > inside-bar close {c[t - 1]:.2f}")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(v.current), len(out))
        return out
