"""Landry TKO (knockout bar) pullback (long): docs/strategies/tko_landry.md.

Knockout bar k in [t-3, t-1]: range >= 1.5 x atr_14 of the bar before, a down bar (close < open) closing in the
bottom 35% of its range, undercutting the lowest low of the 5 bars before it, with Proper Order (sma_10 > ema_20 >
ema_30) on the bar before. Trigger: the first close above the knockout high (the taught entry is an intraday buy stop,
so the close trigger with a next-open fill enters later and wider). Stop = knockout low - 0.1 x atr_14; target = the
highest high of the 20 bars before k, or entry + 2R when that is higher. 15-session time stop; the half-off at +1R
needs partial exits (not modelled).
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

NAME = "tko_landry"
FAST, MID, SLOW = "sma_10", "ema_20", "ema_30"


@register("strategy", NAME)
class TkoLandry(PanelStrategy):
    name = NAME
    description = "Wide down bar undercutting recent lows inside a Proper Order uptrend; buy the close over its high."
    default_params: dict[str, Any] = {
        "max_ko_age": 3,  # card: setup bar k in [t-3, t-1]
        "range_atr_mult": 1.5,  # card: high_k - low_k >= 1.5 x atr_14[k-1]
        "close_pos_max": 0.35,  # card: close_pos_k <= 0.35
        "undercut_bars": 5,  # card: low_k < prior_min_low_5[k]
        "swing_high_bars": 20,  # card: target = highest high of 20 bars before k ...
        "target_r": 2.0,  # ... or entry + 2R if higher
        "stop_atr_offset": 0.1,  # card: stop = low_k - 0.1 x atr_14
        "max_hold_days": 15,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 1.5,  # card
    }
    features_required = ["atr_14", FAST]
    extra_features = [MID, SLOW]

    def _ko_bar(self, w: dict[str, np.ndarray], t: int) -> int | None:
        p = self.params
        under = int(p["undercut_bars"])
        for k in range(t - 1, max(under, t - 1 - int(p["max_ko_age"])), -1):
            o, h, lo, c, atr_prev = w["open"][k], w["high"][k], w["low"][k], w["close"][k], w["atr_14"][k - 1]
            rng = h - lo
            if not (finite(atr_prev) and rng > 0) or rng < float(p["range_atr_mult"]) * atr_prev or c >= o:
                continue
            if (c - lo) / rng > float(p["close_pos_max"]) or lo >= np.min(w["low"][k - under : k]):
                continue
            fast, mid, slow = w[FAST][k - 1], w[MID][k - 1], w[SLOW][k - 1]
            if finite(fast) and finite(mid) and finite(slow) and fast > mid > slow:
                return k
        return None

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        cols = ("open", "high", "low", "close", "atr_14", FAST, MID, SLOW)
        view = as_of_view(panel, as_of, list(cols))
        swing_n = int(p["swing_high_bars"])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            w = view.window(str(row[SYMBOL]), cols)
            t = len(w["close"]) - 1
            k = self._ko_bar(w, t)
            if k is None or k < swing_n or not finite(w["atr_14"][t]):
                continue
            ko_high, close = w["high"][k], w["close"][t]
            if close <= ko_high or (w["close"][k + 1 : t] > ko_high).any():
                continue  # no trigger, or not the first close over the knockout high
            stop = w["low"][k] - float(p["stop_atr_offset"]) * w["atr_14"][t]
            swing_high = float(np.max(w["high"][k - swing_n : k]))
            target = max(swing_high, close + float(p["target_r"]) * (close - stop))
            sig = self.build_signal(
                row, as_of, entry=close, stop=stop, target=target, score=(target - close) / (close - stop),
                features={"ko_high": ko_high, "ko_low": w["low"][k], "ko_age": t - k, "swing_high": swing_high,
                          "max_hold_days": p["max_hold_days"]},
                notes=f"TKO bar {t - k} bar(s) ago; close {close:.2f} > knockout high {ko_high:.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
