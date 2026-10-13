"""Golden Triangle (Charlotte Hudgin, long): docs/strategies/hudgin_golden_triangle.md (thinkorswim GoldenTriangleLE).

Setup within the last `max_setup_bars`: a pivot = highest high of that window, set while price was accelerating above
a rising 50 SMA (close / sma_50 - 1 >= `accel_min` and sma_50 above its value `slope_bars` earlier); then a drop with
at least one close below the 50 SMA, no deeper than `max_drop_below` under it. Trigger on bar t: close above the
confirmation SMA (sma_10) and volume both the highest of the last `vol_bars` bars and above avg_vol_50d, the first
such bar after the drop low (the price- and volume-confirmation days are folded into one bar). Entry next open; stop
= drop low - 0.25 x atr_14; target = the pivot high (card). Exits: after `max_hold_days` = 20 sessions, and the card's
rule exit on a close below the entry signal's drop low (`exit_below_drop_low`; `should_exit` reads `drop_low` from the
position's entry features, so it cannot fire live, where the ledger keeps no features: there the stop, 0.25 x atr_14
below that low, bounds the gap). The undefined "acceleration" and "max drop" knobs take the card's values (`accel_min`
= 0.10 from its mechanical rule).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import PositionContext, Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view

from ._base import (
    P_MIN_MARKET_TREND,
    P_MIN_RR,
    P_MIN_TREND,
    SYMBOL,
    TREND_DOWN,
    PanelStrategy,
    entry_feature,
    finite,
)

NAME = "hudgin_golden_triangle"
ARRAYS = ("high", "low", "close", "volume", "sma_50", "avg_vol_50d")


@register("strategy", NAME)
class GoldenTriangle(PanelStrategy):
    name = NAME
    description = "Accelerating stock dips below its 50 SMA, reclaims the 10 SMA on the highest volume in 5 bars."
    default_params: dict[str, Any] = {
        "conf_ma": "sma_10",  # card: confirmation SMA, 10 default
        "max_setup_bars": 30,  # card: pivot -> drop -> reclaim within 30 bars
        "accel_min": 0.10,  # card: close / sma_50 - 1 >= accel_min (0.10) at the pivot
        "slope_bars": 10,  # card: sma_50 vs 10 bars earlier
        "max_drop_below": 0.15,  # card: max drop below the SMA 0-15%
        "vol_bars": 5,  # card: volume the highest of the last 5 bars
        "stop_atr_buffer": 0.25,  # card: stop = drop low - 0.25 x atr_14
        "max_hold_days": 20,  # card
        "exit_below_drop_low": True,  # card: rule exit on a close below the entry's drop low
        P_MIN_TREND: TREND_DOWN,  # the setup is the trend test (trend_state is often 0 during the drop)
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 1.5,  # card
    }
    features_required = ["trend_state", "atr_14", "sma_50", "avg_vol_50d"]

    def required_features(self) -> list[str]:
        return [*self.features_required, str(self.params["conf_ma"])]

    def should_exit(self, row: pd.Series, bars_held: int, position: PositionContext | None = None) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        drop_low = entry_feature(position, "drop_low")
        return bool(self.params["exit_below_drop_low"]) and drop_low is not None and float(row["close"]) < drop_low

    def _trigger(self, w: dict[str, np.ndarray], j: int, conf: str) -> bool:
        vb = int(self.params["vol_bars"])
        if j - vb + 1 < 0:
            return False
        vol = w["volume"][j]
        return bool(w["close"][j] > w[conf][j] and vol >= np.max(w["volume"][j - vb + 1 : j + 1])
                    and vol > w["avg_vol_50d"][j])

    def _setup(self, w: dict[str, np.ndarray], t: int) -> tuple[int, int] | None:
        """(pivot index, drop-low index) or None."""
        p = self.params
        s = t - int(p["max_setup_bars"])
        if s - int(p["slope_bars"]) < 0:
            return None
        k = s + int(np.argmax(w["high"][s:t]))
        c, sma = w["close"], w["sma_50"]
        if not (finite(sma[k]) and c[k] / sma[k] - 1.0 >= float(p["accel_min"])
                and sma[k] > sma[k - int(p["slope_bars"])]):
            return None
        if k + 1 >= t or not (c[k + 1 : t] < sma[k + 1 : t]).any():
            return None
        d = k + 1 + int(np.argmin(w["low"][k + 1 : t + 1]))
        if w["low"][d] < sma[d] * (1.0 - float(p["max_drop_below"])):
            return None
        return k, d

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        conf = str(self.params["conf_ma"])
        cols = [*ARRAYS, conf]
        view = as_of_view(panel, as_of, [*cols, *self.required_features()])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            if not self.trend_ok(row) or not finite(row["atr_14"]):
                continue
            w = view.window(str(row[SYMBOL]), cols)
            t = len(w["close"]) - 1
            if not self._trigger(w, t, conf):
                continue
            setup = self._setup(w, t)
            if setup is None:
                continue
            k, d = setup
            if d >= t or any(self._trigger(w, j, conf) for j in range(d + 1, t)):
                continue  # trigger bar is the drop low itself, or not the first trigger after it
            close, pivot = float(w["close"][t]), float(w["high"][k])
            stop = float(w["low"][d]) - float(self.params["stop_atr_buffer"]) * float(row["atr_14"])
            sig = self.build_signal(
                row, as_of, entry=close, stop=stop, target=pivot, score=(pivot - close) / (close - stop),
                features={"pivot_high": pivot, "drop_low": w["low"][d], "bars_since_pivot": t - k},
                notes=f"golden triangle: pivot {pivot:.2f} {t - k} bars ago, drop low {w['low'][d]:.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
