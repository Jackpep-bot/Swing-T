"""Heikin-Ashi trend ride (long), docs/strategies/heikin_ashi_trend_ride.md (Valcu, S&C Feb 2004; catalog C46).

HA bars from features/extra.py (`ha_open`, `ha_high`, `ha_low`, `ha_close`). Signal at close t: a strong up HA candle
(ha_close > ha_open with no lower shadow: ha_open - ha_low <= `shadow_tol` x close, the card's float tolerance) after
at least `min_down_candles` (2) down HA candles. Entry next open at real prices. Stop = lowest real low of the down
run - 0.1 x atr_14, raised to the low of the most recent HA indecision candle (body <= 30% of the HA range, both
shadows >= 25% of the range) in the last 10 bars when that is higher and below the close. Primary exit: first down
HA candle (`should_exit`) or 30 sessions; reference target 3R (card), min reward:risk 1.0. `trend_state` gate off by default.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "heikin_ashi_trend_ride"
HA = ["ha_open", "ha_high", "ha_low", "ha_close"]


@register("strategy", NAME)
class HeikinAshiTrendRide(PanelStrategy):
    name = NAME
    description = "First strong up Heikin-Ashi candle after 2+ down candles; exit on the first down HA candle."
    default_params: dict[str, Any] = {
        "min_down_candles": 2,  # card: ha_down_run >= N (default 2)
        "shadow_tol": 0.001,  # card: "no shadow" within 0.1% of price
        "indecision_body_max": 0.30,  # card: body <= 0.3 x HA range
        "indecision_shadow_min": 0.25,  # card: both shadows >= 0.25 x HA range
        "indecision_lookback": 10,  # card: most recent indecision candle in the last 10 bars
        "stop_atr_buffer": 0.1,  # card: min(real low over the down run) - 0.1*atr_14
        "target_r": 3.0,  # card: reference target_r 3.0
        "max_hold_days": 30,  # card: max_hold_days 30
        P_MIN_TREND: TREND_DOWN,  # card: optional trend_state >= 0, off by default
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 1.0,  # card: min_reward_risk 1.0
    }
    features_required = ["atr_14", "trend_state"]
    extra_features = HA
    engine_trail = False  # the ride exits on the first down HA candle (card)

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        o, c = row.get("ha_open"), row.get("ha_close")
        return bars_held >= int(self.params["max_hold_days"]) or (finite(o) and finite(c) and c < o)

    def stop_level(self, w: dict[str, np.ndarray], t: int, run: int, close: float, atr: float) -> float:
        p = self.params
        stop = float(np.min(w["low"][t - run : t])) - float(p["stop_atr_buffer"]) * atr
        o, h, lo, c = (w[k] for k in HA)
        body_max, shadow_min = float(p["indecision_body_max"]), float(p["indecision_shadow_min"])
        for k in range(t - 1, max(t - 1 - int(p["indecision_lookback"]), -1), -1):
            body, rng = abs(c[k] - o[k]), h[k] - lo[k]
            shadow = min(h[k] - max(o[k], c[k]), min(o[k], c[k]) - lo[k])
            if rng > 0 and body <= body_max * rng and shadow >= shadow_min * rng:
                return max(stop, float(w["low"][k])) if w["low"][k] < close else stop
        return stop

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        p = self.params
        v = c1.view(self, panel, as_of, [])
        cur = v.current
        strong = (cur["ha_close"] > cur["ha_open"]) & (cur["ha_open"] - cur["ha_low"] <= float(p["shadow_tol"]) * cur["close"])
        out: list[Signal] = []
        for _, row in cur.loc[strong.fillna(False)].iterrows():
            atr = row["atr_14"]
            if not finite(atr) or not self.trend_ok(row):
                continue
            w = v.window(str(row[SYMBOL]), ["low", *HA])
            t = len(w["low"]) - 1
            down = w["ha_close"][:t] < w["ha_open"][:t]
            run = t - (int(np.flatnonzero(~down)[-1]) + 1 if (~down).any() else 0)
            if run < int(p["min_down_candles"]):
                continue
            close = float(row["close"])
            stop = self.stop_level(w, t, run, close, float(atr))
            sig = self.build_signal(row, as_of, entry=close, stop=stop, target=close + float(p["target_r"]) * (close - stop),
                                    score=float(run), features={"ha_down_run": run, "max_hold_days": p["max_hold_days"]},
                                    notes=f"strong up Heikin-Ashi candle after {run} down candles")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(cur), len(out))
        return out
