"""Ichimoku cloud pullback (long): docs/strategies/ichimoku_cloud_pullback.md (ChartSchool).

On the close of t: close above the cloud's lower edge (cloud_low = min of the spans plotted 26 bars ahead); a close
below the Kijun on one of the previous `dip_window` bars; and a close back above the Tenkan (close_{t-1} <= tenkan_{t-1},
close_t > tenkan_t). Entry next open. Stop = lowest low since the first dip bar in the window - 0.1 x atr_14.
Reference target = the higher of entry + 3R and the prior 20-bar high. Exit on a close below the cloud's lower edge
or after 30 sessions; the engine's ATR trail stands in for the 2 x ATR trail option.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "ichimoku_cloud_pullback"
TENKAN, KIJUN, CLOUD_LOW = "tenkan_9", "kijun_26", "cloud_low"


@register("strategy", NAME)
class IchimokuCloudPullback(PanelStrategy):
    name = NAME
    description = "Above the cloud, dip under the Kijun, close back over the Tenkan; stop under the dip low."
    default_params: dict[str, Any] = {
        "dip_window": 8,  # card: close below kijun on some bar in [t-8, t-1]
        "stop_atr_offset": 0.1,  # card: stop = dip_low - 0.1 x atr_14
        "target_r": 3.0,  # card: reference target_r 3.0 ...
        "swing_high_bars": 20,  # ... or the prior 20-bar swing high when higher
        "max_hold_days": 30,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 1.5,  # card
    }
    features_required = ["atr_14"]
    extra_features = [TENKAN, KIJUN, CLOUD_LOW]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        cloud = row.get(CLOUD_LOW)
        return finite(cloud) and float(row["close"]) < float(cloud)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        cols = ("high", "low", "close", TENKAN, KIJUN)
        view = as_of_view(panel, as_of, ["open", *cols, *self.required_features()])
        dip_n, swing_n = int(p["dip_window"]), int(p["swing_high_bars"])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            close, cloud, atr = float(row["close"]), row[CLOUD_LOW], row["atr_14"]
            if not (finite(cloud) and finite(atr)) or close <= float(cloud):
                continue
            w = view.window(str(row[SYMBOL]), cols)
            t = len(w["close"]) - 1
            if t < max(dip_n, swing_n) + 1:
                continue
            c, tk = w["close"], w[TENKAN]
            if not (finite(tk[t]) and finite(tk[t - 1]) and c[t - 1] <= tk[t - 1] and c[t] > tk[t]):
                continue
            dips = np.flatnonzero(c[t - dip_n : t] < w[KIJUN][t - dip_n : t])
            if dips.size == 0:
                continue
            first = t - dip_n + int(dips[0])
            dip_low = float(np.min(w["low"][first : t + 1]))
            stop = dip_low - float(p["stop_atr_offset"]) * float(atr)
            swing_high = float(np.max(w["high"][t - swing_n : t]))
            target = max(close + float(p["target_r"]) * (close - stop), swing_high)
            sig = self.build_signal(
                row, as_of, entry=close, stop=stop, target=target, score=(close - float(cloud)) / float(atr),
                features={"dip_low": dip_low, TENKAN: tk[t], KIJUN: w[KIJUN][t], CLOUD_LOW: cloud,
                          "swing_high": swing_high, "max_hold_days": p["max_hold_days"]},
                notes=f"Kijun dip {t - first} bar(s) ago, close {close:.2f} back over Tenkan {tk[t]:.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
