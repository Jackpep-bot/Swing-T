"""Bollinger Method III (Intraday Intensity reversal) and W-bottoms (long), docs/strategies/
bollinger_w_bottom_ii_reversal.md (catalog C38).

`variant: method3`: a buy alert is a bar whose low tags the lower band (20, 2) while II% (21-bar Intraday Intensity,
`ii_pct_21`) is positive, within the last `alert_max_age` bars; the trigger is the first confirmation bar after it,
close above the prior high with close_pos >= 0.7 (card's coding of "a strong up bar"). Stop = lowest low since the
alert - 0.1 x atr_14.
`variant: w_bottom`: the last two confirmed pivot lows (width 5, features.extra.last_pivot) are 5-30 bars apart, the
first at or outside the band (%b <= 0), the retest inside it (%b > 0) and no more than 1 x atr_14 above the first; buy
the first close above the highest high between them (card: next open after the close, no stop-entry). Stop = retest
low - 0.1 x atr_14. Both: target = bb_upper_20 at signal time, max 15 sessions.
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

NAME = "bollinger_w_bottom_ii_reversal"
METHOD3, W_BOTTOM = "method3", "w_bottom"
PCTB, II = "bb_pctb_20", "ii_pct_21"
ARRAYS = ("high", "low", "close", "bb_lower_20", PCTB, II)


@register("strategy", NAME)
class BollingerWBottomII(PanelStrategy):
    name = NAME
    description = "Lower-band tag with II% > 0 then a strong up bar, or a W-bottom peak break; target the upper band."
    default_params: dict[str, Any] = {
        "variant": METHOD3,  # card: Method III alert + confirmation, or "w_bottom"
        "alert_max_age": 3,  # engine choice: confirmation within 3 bars of the alert (card: "after a buy alert")
        "confirm_close_pos_min": 0.7,  # card: strong up bar = close > prior high and close_pos > 0.7
        "pivot_width": 5,  # card: pivot lows from features/levels.py width 5
        "w_min_bars": 5,  # card: lows 5-30 bars apart
        "w_max_bars": 30,
        "retest_atr": 1.0,  # card: retest low within 1 x atr_14 of the first low (or lower)
        "stop_atr_buffer": 0.1,  # card: stop retest low - 0.1 x atr_14
        "max_hold_days": 15,  # card
        P_MIN_TREND: TREND_DOWN,
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 1.5,  # card: the stop is structural, so R:R is meaningful
    }
    features_required = ["atr_14", "trend_state"]
    extra_features = ["bb_upper_20", "bb_lower_20", PCTB, II]  # bb_*_20 are contract columns resolvable in extra

    def _method3(self, w: dict[str, np.ndarray], t: int) -> tuple[int, float] | None:
        h, lo, c = w["high"], w["low"], w["close"]
        cp_min = float(self.params["confirm_close_pos_min"])

        def strong(j: int) -> bool:
            rng = h[j] - lo[j]
            return c[j] > h[j - 1] and rng > 0 and (c[j] - lo[j]) / rng >= cp_min

        if t < 2 or not strong(t):
            return None
        for k in range(t - 1, max(0, t - 1 - int(self.params["alert_max_age"])), -1):
            if lo[k] <= w["bb_lower_20"][k] and w[II][k] > 0:
                if any(strong(j) for j in range(k + 1, t)):
                    return None  # not the first confirmation after this alert
                return k, float(lo[k : t + 1].min())
        return None

    def _w_bottom(self, w: dict[str, np.ndarray], t: int, atr: float) -> tuple[int, float] | None:
        width = int(self.params["pivot_width"])
        _, idx = last_pivot(w["low"], width, width, highs=False)
        p2 = idx[t]
        if p2 < 0:
            return None
        p1 = idx[p2 + width - 1]
        if p1 < 0 or not int(self.params["w_min_bars"]) <= p2 - p1 <= int(self.params["w_max_bars"]):
            return None
        lo, pb = w["low"], w[PCTB]
        if not (pb[p1] <= 0 < pb[p2] and lo[p2] <= lo[p1] + float(self.params["retest_atr"]) * atr):
            return None
        peak = float(w["high"][p1 : p2 + 1].max())
        c = w["close"]
        if not c[t] > peak or (c[p2 + 1 : t] > peak).any():
            return None
        return p2, float(lo[p2])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        view = c1.view(self, panel, as_of, list(ARRAYS))
        variant = str(self.params["variant"])
        buf = float(self.params["stop_atr_buffer"])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            atr, upper = row["atr_14"], row["bb_upper_20"]
            if not (finite(atr) and finite(upper)) or not self.trend_ok(row):
                continue
            w = view.window(str(row[SYMBOL]), ARRAYS)
            t = len(w["close"]) - 1
            hit = self._method3(w, t) if variant == METHOD3 else self._w_bottom(w, t, float(atr))
            if hit is None:
                continue
            k, low = hit
            close = float(w["close"][t])
            sig = self.build_signal(
                row, as_of, entry=close, stop=low - buf * float(atr), target=float(upper),
                score=float(w[II][t]) if finite(w[II][t]) else 0.0,
                features={"setup_age": t - k, "setup_low": low, PCTB: w[PCTB][k], II: w[II][k],
                          "max_hold_days": self.params["max_hold_days"]},
                notes=f"{variant}: setup {t - k} bar(s) ago, low {low:.2f}; target upper band {float(upper):.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
