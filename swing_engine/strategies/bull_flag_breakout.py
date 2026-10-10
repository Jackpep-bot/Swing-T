"""Generic bull flag breakout (long): docs/strategies/bull_flag_breakout.md, daily translation of the Katsanos /
thinkorswim flag system with Schwab Learn targets. The qullamaggie_flag module is the leader-only variant (RS, ADR,
30% pole); this one has no RS/ADR filter and sizes the pattern in ATRs.

Flag = the consolidation since the highest high of the last `flag_max_bars` bars before today (features/patterns2.py
`flag`), 3-15 bars long, no deeper than 2.5 x atr_14 below its high (the pivot). Pole: pivot - lowest low of the
`pole_max_bars` bars before the flag top >= 5.5 x atr_14. trend_state >= 1 stands in for the 70-bar uptrend. Trigger:
close above the pivot, no more than 1 x atr_14 above it, rvol_day >= 1.2. Entry next open (the stop entry at the flag
high is the source's); stop = flag low - 0.01; target = entry + 1.0 x pole (Schwab A; Katsanos 1.2x = `pole_target`).
Skipped (card): the ambiguous "ATR changed >= 5%" rule, the "previous flag >= 50 bars ago" rule, the inactivity exit
and the half-pole partial (no scale-out hook).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view, flag

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

NAME = "bull_flag_breakout"


@register("strategy", NAME)
class BullFlagBreakout(PanelStrategy):
    name = NAME
    description = "Pole >= 5.5 ATR in <= 23 bars, 3-15 bar flag <= 2.5 ATR deep; buy the close over the flag high."
    default_params: dict[str, Any] = {
        "pole_atr_min": 5.5,  # card (Katsanos): pole height >= 5.5 x ATR ...
        "pole_max_bars": 23,  # ... formed in <= 23 bars
        "flag_min_bars": 3,  # card: flag length 3-15 bars
        "flag_max_bars": 15,
        "flag_atr_max": 2.5,  # card: flag height <= 2.5 x ATR
        "max_extension_atr": 1.0,  # card: close - pivot <= 1 x atr_14
        "rvol_min": 1.2,  # card: rvol_day >= 1.2
        "tick": 0.01,  # card: stop = flag low - 0.01
        "pole_target": 1.0,  # card: target = entry + 1.0 x pole (Schwab A); Katsanos 1.2
        "max_hold_days": 40,  # card
        P_MIN_TREND: TREND_UP,  # card: trend_state >= 1 (stand-in for the 70-bar uptrend)
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 2.0,  # card: default 2.0 applies
    }
    features_required = ["atr_14", "rvol_day", "trend_state"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        view = as_of_view(panel, as_of, ["high", "low", "close", *self.required_features()])
        cur = view.current
        cur = cur.loc[(cur["rvol_day"] >= float(p["rvol_min"])).fillna(False)]
        out: list[Signal] = []
        for _, row in cur.iterrows():
            atr = row["atr_14"]
            if not (self.trend_ok(row) and finite(atr) and atr > 0):
                continue
            w = view.window(str(row[SYMBOL]), ["high", "low", "close"])
            t = len(w["close"]) - 1
            fl = flag(w["high"], w["low"], t - 1, int(p["flag_max_bars"]))
            if fl is None or fl.length < int(p["flag_min_bars"]) or fl.pivot - fl.low > float(p["flag_atr_max"]) * atr:
                continue
            close = float(w["close"][t])
            if not 0 < close - fl.pivot <= float(p["max_extension_atr"]) * atr:
                continue
            seg = w["low"][max(0, fl.top_idx - int(p["pole_max_bars"])) : fl.top_idx]
            hi = w["high"][max(0, fl.top_idx - int(p["pole_max_bars"])) : fl.top_idx]
            if seg.size == 0 or not (np.isfinite(seg).all() and np.isfinite(hi).all()) or hi.max() >= fl.pivot:
                continue  # pivot must be the pole top, else the flag is longer than flag_max_bars
            pole = fl.pivot - float(seg.min())
            if pole < float(p["pole_atr_min"]) * atr:
                continue
            sig = self.build_signal(
                row, as_of, entry=close, stop=fl.low - float(p["tick"]),
                target=close + float(p["pole_target"]) * pole, score=pole / atr,
                features={"pivot": fl.pivot, "flag_low": fl.low, "flag_len": fl.length, "pole_atr": pole / atr},
                notes=f"bull flag: {fl.length}-bar flag under {fl.pivot:.2f} after a {pole / atr:.1f} ATR pole",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
