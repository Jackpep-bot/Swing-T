"""Calhoun MeanReversionSwingLE (long), docs/strategies/calhoun_mean_reversion_swing.md (catalog B3, thinkorswim).

Despite the name, a pullback-in-uptrend entry. As of bar t over the last `max_len` bars: peak p = highest high
before t, leg start s = lowest low before p, pullback low j = lowest low after p (through t). Requires p - s >=
`min_len` bars, leg high[p] - low[s] >= `min_range`, retracement (high[p] - low[j]) / leg within `tolerance` of 0.50,
and close[t] - low[j] >= `min_up_move` for the first time since j. Thresholds are thinkorswim's dollars by default;
`units: atr` reads them as multiples of atr_14 (card's normalised variant). Stop low[j] - 0.1 x atr_14, target the
leg high (both engine choices from the card), 20-session cap.
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

NAME = "calhoun_mean_reversion_swing"
UNITS_DOLLAR, UNITS_ATR = "dollar", "atr"
ARRAYS = ("high", "low", "close")


@register("strategy", NAME)
class CalhounMeanReversionSwing(PanelStrategy):
    name = NAME
    description = "Up-leg >= 20 bars and $5, ~50% retracement, then a $0.50 bounce off the pullback low."
    default_params: dict[str, Any] = {
        "min_len": 20,  # card/tos: segment 1 lasts >= 20 bars
        "max_len": 400,  # card/tos: whole sequence <= 400 bars
        "units": UNITS_DOLLAR,  # card: tos dollar thresholds; "atr" = multiples of atr_14 (5 / 0.5 in the card)
        "min_range": 5.0,  # card/tos: uptrend range >= $5
        "min_up_move": 0.5,  # card/tos: rise >= $0.50 off the pullback low
        "retrace": 0.5,  # card/tos: 50% retracement
        "tolerance": 0.01,  # card: ratio within 0.49-0.51
        "stop_atr_buffer": 0.1,  # card: stop low[j] - 0.1 x atr_14
        "max_hold_days": 20,  # card
        P_MIN_TREND: TREND_DOWN,  # card: trend_state >= 0 is an optional filter (off: tos rule)
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 1.5,  # card
    }
    features_required = ["atr_14", "trend_state"]

    def _setup(self, w: dict[str, np.ndarray], t: int, unit: float) -> tuple[int, int, int] | None:
        h, lo, c = w["high"], w["low"], w["close"]
        start = max(0, t - int(self.params["max_len"]))
        if t - start < 2:
            return None
        p = start + int(np.argmax(h[start:t]))
        if p <= start:
            return None
        s = start + int(np.argmin(lo[start:p]))
        j = p + 1 + int(np.argmin(lo[p + 1 : t + 1]))
        leg = h[p] - lo[s]
        if p - s < int(self.params["min_len"]) or leg < float(self.params["min_range"]) * unit:
            return None
        if abs((h[p] - lo[j]) / leg - float(self.params["retrace"])) > float(self.params["tolerance"]):
            return None
        up = float(self.params["min_up_move"]) * unit
        if c[t] - lo[j] < up or (c[j + 1 : t] - lo[j] >= up).any():
            return None  # no trigger, or not the first close that clears the up move
        return s, p, j

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        view = c1.view(self, panel, as_of, list(ARRAYS))
        atr_units = str(self.params["units"]) == UNITS_ATR
        buf = float(self.params["stop_atr_buffer"])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            atr = row["atr_14"]
            if not finite(atr) or not self.trend_ok(row):
                continue
            w = view.window(str(row[SYMBOL]), ARRAYS)
            t = len(w["close"]) - 1
            hit = self._setup(w, t, float(atr) if atr_units else 1.0)
            if hit is None:
                continue
            s, p, j = hit
            close, peak, low = float(w["close"][t]), float(w["high"][p]), float(w["low"][j])
            sig = self.build_signal(
                row, as_of, entry=close, stop=low - buf * float(atr), target=peak, score=(close - low) / float(atr),
                features={"leg_low": w["low"][s], "leg_high": peak, "pullback_low": low, "leg_bars": p - s,
                          "retrace": (peak - low) / (peak - w["low"][s]), "max_hold_days": self.params["max_hold_days"]},
                notes=f"Calhoun swing: {p - s}-bar leg {w['low'][s]:.2f}->{peak:.2f}, pullback low {low:.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
