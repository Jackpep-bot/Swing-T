"""Bullish RSI divergence (long), docs/strategies/rsi_divergence.md (TradingView built-in, catalog P23).

RSI(14) pivot low at bar i = t - 5: rsi_i is the minimum of rsi over i-5 .. i+5 (left/right 5), so it is confirmed
only on the as-of bar t (the built-in 5-bar lag). The previous confirmed RSI pivot low j lies 5-60 bars before i.
Variant "regular" (default, card variant A): price low_i < low_j, rsi_i > rsi_j and rsi_i < 35. Variant "hidden"
(card variant B): low_i > low_j, rsi_i < rsi_j, trend_state == 1. Entry next open. Stop = low_i - 0.5 x atr_14. Time
exit 20 sessions, no target by default; `target_resistance` uses resistance_1 with min reward:risk 2.0 (card's
comparison variant). Bearish divergences are not used (long-only).
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
    TREND_DOWN,
    TREND_UP,
    PanelStrategy,
    finite,
)

NAME = "rsi_divergence"
REGULAR, HIDDEN = "regular", "hidden"


def pivot_lows(x: np.ndarray, left: int, right: int, first: int, last: int) -> list[int]:
    """Indices first <= i <= last whose value is the minimum of x[i-left .. i+right] (all finite)."""
    out = []
    for i in range(max(first, left), min(last, len(x) - 1 - right) + 1):
        win = x[i - left : i + right + 1]
        if np.isfinite(win).all() and x[i] == win.min():
            out.append(i)
    return out


@register("strategy", NAME)
class RsiDivergence(PanelStrategy):
    name = NAME
    description = "RSI(14) pivot-low divergence (regular: lower price low, higher RSI low) confirmed 5 bars later."
    default_params: dict[str, Any] = {
        "variant": REGULAR,  # card: variant A regular bullish; "hidden" = variant B
        "pivot_left": 5,  # card: left/right lookback 5/5
        "pivot_right": 5,
        "min_spacing": 5,  # card: two pivots 5-60 bars apart
        "max_spacing": 60,
        "max_pivot_rsi": 35.0,  # card variant A: rsi_14 at the pivot < 35
        "stop_atr_mult": 0.5,  # card: stop = div_pivot_low - 0.5 * atr_14
        "target_resistance": False,  # card comparison variant: target resistance_1 with min_reward_risk 2.0
        "max_hold_days": 20,  # card: max_hold_days 20
        P_MIN_TREND: TREND_DOWN,  # variant B forces trend_state == 1 below
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # time exit; set 2.0 with target_resistance (card)
    }
    features_required = ["atr_14", "rsi_14", "trend_state", "resistance_1"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def divergence(self, low: np.ndarray, rsi: np.ndarray) -> int | None:
        """Pivot bar i of a bullish divergence confirmed on the last bar, else None."""
        p = self.params
        left, right = int(p["pivot_left"]), int(p["pivot_right"])
        i = len(rsi) - 1 - right
        if not pivot_lows(rsi, left, right, i, i):
            return None
        prior = pivot_lows(rsi, left, right, i - int(p["max_spacing"]), i - int(p["min_spacing"]))
        if not prior:
            return None
        j = prior[-1]
        if p["variant"] == HIDDEN:
            return i if low[i] > low[j] and rsi[i] < rsi[j] else None
        return i if low[i] < low[j] and rsi[i] > rsi[j] and rsi[i] < float(p["max_pivot_rsi"]) else None

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        p = self.params
        v = c1.view(self, panel, as_of, [])
        out: list[Signal] = []
        for _, row in v.current.iterrows():
            atr = row["atr_14"]
            if not finite(atr) or not self.trend_ok(row) or (p["variant"] == HIDDEN and row["trend_state"] != TREND_UP):
                continue
            w = v.window(str(row[SYMBOL]), ["low", "rsi_14"])
            i = self.divergence(w["low"], w["rsi_14"])
            if i is None:
                continue
            close = float(row["close"])
            target = float(row["resistance_1"]) if p["target_resistance"] and finite(row["resistance_1"]) else None
            if p["target_resistance"] and target is None:
                continue
            sig = self.build_signal(row, as_of, entry=close, stop=float(w["low"][i]) - float(p["stop_atr_mult"]) * float(atr),
                                    target=target, score=-float(w["rsi_14"][i]),
                                    features={"pivot_rsi": w["rsi_14"][i], "pivot_low": w["low"][i],
                                              "max_hold_days": p["max_hold_days"]},
                                    notes=f"{p['variant']} bullish RSI divergence at {w['low'][i]:.2f} "
                                    f"(RSI {w['rsi_14'][i]:.0f}), confirmed {len(w['low']) - 1 - i} bars later")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(v.current), len(out))
        return out
