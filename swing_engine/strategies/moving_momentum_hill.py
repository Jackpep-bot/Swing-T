"""Moving Momentum (long), Arthur Hill / ChartSchool: docs/strategies/moving_momentum_hill.md, catalog P43.

Trend: SMA20 > SMA150. Setup: slow stochastic %K(14,3) below 20 on any of the last 10 bars (the card's mechanical
window). Trigger: MACD(12,26,9) histogram turns positive (`macd_hist[t-1] <= 0 < macd_hist[t]`). Entry next open.
Stop: lowest low since the first %K < 20 bar of the window - 0.1 x atr_14, raised to `support_1` when that is
higher and still below the entry. Target: max(prior 20-bar high, entry + 2R). Exits: SMA20 < SMA150 or 25 sessions,
plus the engine breakeven/trail overlay (card). Short mirror not built.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_FLAT, PanelStrategy, finite

NAME = "moving_momentum_hill"
FAST, SLOW, STOCH = "sma_20", "sma_150", "stoch_k_14_3"


@register("strategy", NAME)
class MovingMomentumHill(PanelStrategy):
    name = NAME
    description = "SMA20 > SMA150; slow %K(14,3) < 20 within 10 bars; MACD histogram turns positive."
    default_params: dict[str, Any] = {
        "stoch_level": 20.0,  # card: Stochastic(14,3) below 20
        "setup_window": 10,  # card: setup armed if %K < 20 on any bar in [t-10, t]
        "stop_atr_buffer": 0.1,  # card: support stop - 0.1 x atr_14
        "swing_high_bars": 20,  # card: target = max(prior 20-bar high, entry + 2R)
        "target_r": 2.0,
        "max_hold_days": 25,  # card
        P_MIN_MARKET_TREND: TREND_FLAT,  # card: healthy_uptrend 1.0, narrow_uptrend 0.5
        P_MIN_RR: 1.5,  # card: min_reward_risk 1.5
    }
    features_required = ["atr_14", "macd_hist", "support_1", FAST]
    extra_features = [SLOW, STOCH]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        fast, slow = row.get(FAST), row.get(SLOW)
        return finite(fast) and finite(slow) and float(fast) < float(slow)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        cols = ["high", "low", "macd_hist", STOCH]
        view = as_of_view(panel, as_of, ["open", "close", *cols, *self.required_features()])
        n = int(p["setup_window"])
        cur = view.current
        keep = (cur[FAST] > cur[SLOW]).fillna(False)
        out: list[Signal] = []
        for _, row in cur.loc[keep].iterrows():
            w = view.window(str(row[SYMBOL]), cols)
            hist, k, t = w["macd_hist"], w[STOCH], len(w["low"]) - 1
            if t < max(n, int(p["swing_high_bars"])) or not (hist[t - 1] <= 0 < hist[t]):
                continue
            armed = np.flatnonzero(k[t - n : t + 1] < float(p["stoch_level"]))
            if not len(armed):
                continue
            first = t - n + int(armed[0])
            close, atr = float(row["close"]), float(row["atr_14"])
            stop = float(np.min(w["low"][first : t + 1])) - float(p["stop_atr_buffer"]) * atr
            sup = row["support_1"]
            if finite(sup) and stop < float(sup) < close:
                stop = float(sup)
            swing = float(np.max(w["high"][t - int(p["swing_high_bars"]) : t]))
            target = max(swing, close + float(p["target_r"]) * (close - stop))
            sig = self.build_signal(
                row, as_of, entry=close, stop=stop, target=target, score=float(row[FAST]) / float(row[SLOW]) - 1.0,
                features={STOCH: k[first], "setup_age": t - first, "macd_hist": hist[t], FAST: row[FAST], SLOW: row[SLOW],
                          "max_hold_days": p["max_hold_days"]},
                notes=f"SMA20 > SMA150; %K {k[first]:.0f} < 20 {t - first} bar(s) ago; MACD hist turned + ({hist[t]:.3f})",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(cur), len(out))
        return out
