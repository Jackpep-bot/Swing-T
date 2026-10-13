"""Darvas box breakout (long): docs/strategies/darvas_box.md.

Causal box state machine over the bars before the as-of bar (`darvas_box`): a high not exceeded on the next 3 bars
is the box top; after it, the lowest low that holds for 3 bars is the box bottom (box complete). A low under the
bottom voids the box; a high over the top starts a new one at that bar. Signal: complete box near the 52-week high
(dist_52w_high >= -5% on the bar before), close > box top and volume >= 1.3 x avg_vol_50d; entry next open.
Stop = box bottom - 0.1 x atr_14. Not modelled (engine gaps): pyramiding into later boxes and ratcheting the stop to
each new box bottom (the stop stays at the entry box's bottom; 120-session time stop), earnings ("improving EPS").
"""
from __future__ import annotations

from datetime import date
from typing import Any, NamedTuple

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "darvas_box"


class Box(NamedTuple):
    top: float
    bottom: float


def darvas_box(high: np.ndarray, low: np.ndarray, confirm: int) -> Box | None:
    """The complete, unbroken Darvas box at the end of ``high``/``low`` (bars before the as-of bar), or None."""
    top = bottom = cand = np.nan
    top_i = cand_i = -1
    for j in range(len(high)):
        h, lo = high[j], low[j]
        if not (np.isfinite(h) and np.isfinite(lo)):
            top, top_i = np.nan, -1
            continue
        if top_i < 0 or h > top or (np.isfinite(bottom) and lo < bottom):
            top, top_i, bottom, cand, cand_i = h, j, np.nan, np.nan, -1  # new high (or broken box) restarts
            continue
        if np.isfinite(bottom):
            continue
        if not np.isfinite(cand) or lo < cand:
            cand, cand_i = lo, j
        if j - top_i >= confirm and j - cand_i >= confirm and cand_i > top_i:
            bottom = cand
    return Box(float(top), float(bottom)) if np.isfinite(bottom) and top_i >= 0 else None


@register("strategy", NAME)
class DarvasBox(PanelStrategy):
    name = NAME
    description = "Close above a complete Darvas box top near the 52-week high on 1.3x volume; stop under the box."
    default_params: dict[str, Any] = {
        "confirm_bars": 3,  # card: top/bottom hold for 3 consecutive days
        "lookback_bars": 60,  # engine choice: bars scanned for the current box
        "max_dist_52w_high": 0.05,  # card: dist_52w_high >= -0.05 at box completion
        "vol_mult": 1.3,  # card: breakout volume >= 1.3 x avg_vol_50d (a coder's threshold, not Darvas')
        "stop_atr_offset": 0.1,  # card: stop = box_bottom - 0.1 x atr_14
        "max_hold_days": 120,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no fixed target
    }
    features_required = ["atr_14", "avg_vol_50d", "dist_52w_high"]
    engine_trail = False  # the box bottom is the exit (card); the breakeven overlay would cut the trend

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        cols = ("high", "low", "dist_52w_high")
        view = as_of_view(panel, as_of, ["open", "high", "low", "close", "volume", *self.required_features()])
        n = int(p["lookback_bars"])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            atr, avg_vol = row["atr_14"], row["avg_vol_50d"]
            close = float(row["close"])
            if not (finite(atr) and finite(avg_vol)) or float(row["volume"]) < float(p["vol_mult"]) * float(avg_vol):
                continue
            w = view.window(str(row[SYMBOL]), cols)
            t = len(w["high"]) - 1
            dist = w["dist_52w_high"][t - 1] if t >= 1 else np.nan
            if not finite(dist) or dist < -float(p["max_dist_52w_high"]):
                continue
            box = darvas_box(w["high"][max(0, t - n) : t], w["low"][max(0, t - n) : t], int(p["confirm_bars"]))
            if box is None or close <= box.top:
                continue
            stop = box.bottom - float(p["stop_atr_offset"]) * float(atr)
            sig = self.build_signal(
                row, as_of, entry=close, stop=stop, target=None, score=float(row["volume"]) / float(avg_vol),
                features={"box_top": box.top, "box_bottom": box.bottom, "atr_14": atr,
                          "max_hold_days": p["max_hold_days"]},
                notes=f"Darvas box {box.bottom:.2f}-{box.top:.2f} broken by close {close:.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
