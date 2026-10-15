"""Kell Cycle of Price Action (long): docs/strategies/kell_cycle_of_price_action.md, two of its setups on daily bars.

`setup: wedge_pop` (default): a downside extension (high < ema_10 - 1.5 x atr_14) within the last 15 bars, then the
first close back above both the 10 and 20 EMA on rvol_day >= 1.5. `setup: base_break`: close above the highest high
of the prior `base_bars` bars, every base close at or above ema_20, rvol_day >= 1.5. Both: not extended
(close / ema_10 - 1 <= 3%, Kell's journal), stop = signal-day low, skipped when that is more than 3% away; entry next
open (daily proxy for his 65-minute triggers). Exit: close below ema_20 (`should_exit`; the EMA trail replaces the
engine overlay), 60-day cap; no target. Not modelled: the EMA Crossback setup (pullback_trend with a pop
prerequisite), the Wedge Drop exit variant, selling into extensions and adding pieces (no scale hooks). The QQQ-vs-20
EMA gate needs QQQ as a second market series; `min_market_trend_state` (SPY trend) stands in.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view

from ._base import (
    P_MIN_MARKET_TREND,
    P_MIN_RR,
    P_MIN_TREND,
    SYMBOL,
    TREND_DOWN,
    TREND_FLAT,
    PanelStrategy,
    finite,
)

NAME = "kell_cycle_of_price_action"
FAST, SLOW = "ema_10", "ema_20"
WEDGE_POP, BASE_BREAK = "wedge_pop", "base_break"
ARRAYS = ("high", "low", "close", "atr_14", FAST, SLOW)


@register("strategy", NAME)
class KellCycle(PanelStrategy):
    name = NAME
    description = "Kell Wedge Pop (or Base n' Break) through the 10/20 EMA on volume, not extended; trail ema_20."
    default_params: dict[str, Any] = {
        "setup": WEDGE_POP,  # card: each setup is a separate variant (wedge_pop | base_break)
        "down_ext_atr": 1.5,  # card: downside extension = high < ema_10 - 1.5 x atr_14
        "pop_window": 15,  # card: pop within 15 bars of the extension
        "base_bars": 10,  # card: base length 5-15 bars
        "rvol_min": 1.5,  # card
        "max_ext_10": 0.03,  # card: never buy 3-4%+ above the 10 EMA
        "max_stop_pct": 0.03,  # card: skip if the stop is more than 3% away
        "max_hold_days": 60,  # card
        P_MIN_TREND: TREND_DOWN,  # wedge pops start from downtrends
        P_MIN_MARKET_TREND: TREND_FLAT,  # stand-in for QQQ > its 20 EMA (correction mode otherwise)
        P_MIN_RR: 0.0,  # card
    }
    features_required = ["trend_state", "atr_14", "rvol_day"]
    extra_features = [FAST, SLOW]
    engine_trail = False  # the ema_20 close exit is the trail

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        slow = row.get(SLOW)
        return bars_held >= int(self.params["max_hold_days"]) or (finite(slow) and float(row["close"]) < slow)

    def _wedge_pop(self, w: dict[str, np.ndarray], t: int) -> bool:
        p = self.params
        top = np.maximum(w[FAST], w[SLOW])
        if not (w["close"][t] > top[t] and w["close"][t - 1] <= top[t - 1]):
            return False
        s = max(0, t - int(p["pop_window"]))
        ext = w["high"][s:t] < w[FAST][s:t] - float(p["down_ext_atr"]) * w["atr_14"][s:t]
        return bool(ext.any())

    def _base_break(self, w: dict[str, np.ndarray], t: int) -> bool:
        s = t - int(self.params["base_bars"])
        return s >= 0 and bool(w["close"][t] > w["high"][s:t].max() and (w["close"][s:t] >= w[SLOW][s:t]).all())

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        setup = self._wedge_pop if p["setup"] == WEDGE_POP else self._base_break
        view = as_of_view(panel, as_of, [*ARRAYS, *self.required_features()])
        cur = view.current
        cur = cur.loc[((cur["rvol_day"] >= float(p["rvol_min"])) & (cur["close"] / cur[FAST] - 1.0 <= float(
            p["max_ext_10"]))).fillna(False)]
        out: list[Signal] = []
        for _, row in cur.iterrows():
            if not self.trend_ok(row):
                continue
            w = view.window(str(row[SYMBOL]), ARRAYS)
            t = len(w["close"]) - 1
            if t < 1 or not setup(w, t):
                continue
            close, low = float(row["close"]), float(row["low"])
            if (close - low) / close > float(p["max_stop_pct"]):
                continue
            sig = self.build_signal(
                row, as_of, entry=close, stop=low, target=None, score=float(row["rvol_day"]),
                features={"ext_10": close / float(row[FAST]) - 1.0, FAST: row[FAST], SLOW: row[SLOW],
                          "rvol_day": row["rvol_day"]},
                notes=f"Kell {p['setup']}: close {close:.2f} over ema_10/20 on rvol {float(row['rvol_day']):.1f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
