"""Elder Triple Screen (long): docs/strategies/elder_triple_screen.md, catalog C33.

Screen 1 (tide): the weekly MACD-histogram (12,26,9) of completed W-FRI weeks is rising (`wk_macd_hist >
wk_macd_hist_prev`). Screen 2 (wave): the 2-day EMA of Force Index is below zero. Screen 3 (entry): a buy stop 0.01
over the day's high (`entry_type = stop`, one session), re-armed at each new day's high while the setup holds, at
most 3 re-arms (card's engine choice). Stop: the lower of the last two daily lows - 0.1 x atr_14 (the card's "lower of
the entry-day and prior-day low"; the entry-day low is unknown when the order is placed). Target 2R; exit when the
tide stops rising or after 20 sessions. Elder's 2% / 6% money rules belong to `risk/`, not here.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import EntryType, Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_FLAT, PanelStrategy, finite

NAME = "elder_triple_screen"
TIDE, TIDE_PREV, FORCE = "wk_macd_hist", "wk_macd_hist_prev", "force_2"


@register("strategy", NAME)
class ElderTripleScreen(PanelStrategy):
    name = NAME
    description = "Weekly MACD-histogram rising; 2-day Force Index EMA < 0; buy stop over the prior day's high."
    default_params: dict[str, Any] = {
        "max_rearms": 3,  # card: re-arm at the new day's high, max 3 re-arms
        "tick": 0.01,  # card: one tick above the previous day's high
        "stop_atr_buffer": 0.1,  # card: stop + 0.1 x atr_14 buffer
        "target_r": 2.0,  # card: 2R target (engine default)
        "max_hold_days": 20,  # card
        P_MIN_MARKET_TREND: TREND_FLAT,  # card: healthy and narrow uptrends
        P_MIN_RR: 1.0,  # the target is a fixed 2R; the floor only guards geometry
    }
    features_required = ["atr_14"]
    extra_features = [TIDE, TIDE_PREV, FORCE]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        tide, prev = row.get(TIDE), row.get(TIDE_PREV)
        return finite(tide) and finite(prev) and float(tide) <= float(prev)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        cols = ["low", TIDE, TIDE_PREV, FORCE]
        view = as_of_view(panel, as_of, ["open", "high", "close", *cols, *self.required_features()])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            w = view.window(str(row[SYMBOL]), cols)
            setup = (w[TIDE] > w[TIDE_PREV]) & (w[FORCE] < 0)
            t = len(setup) - 1
            if t < 1 or not setup[t]:
                continue
            streak = int(np.argmin(setup[::-1])) if not setup.all() else t + 1
            if streak > int(p["max_rearms"]) + 1:
                continue  # the buy stop was re-armed max_rearms times without a fill: setup void
            tick = float(p["tick"])
            entry = float(row["high"]) + tick
            stop = float(min(w["low"][t], w["low"][t - 1])) - float(p["stop_atr_buffer"]) * float(row["atr_14"])
            sig = self.build_signal(
                row, as_of, entry=entry, stop=stop, target=entry + float(p["target_r"]) * (entry - stop),
                score=float(w[TIDE][t] - w[TIDE_PREV][t]) / float(row["close"]),
                features={TIDE: w[TIDE][t], TIDE_PREV: w[TIDE_PREV][t], FORCE: w[FORCE][t], "setup_day": streak,
                          "max_hold_days": p["max_hold_days"]},
                notes=f"tide up (weekly MACD-H {w[TIDE_PREV][t]:.3f} -> {w[TIDE][t]:.3f}), Force EMA2 < 0; buy stop {entry:.2f}",
            )
            if sig:
                out.append(sig.model_copy(update={"entry_type": EntryType.STOP}))
        self.log_scan(as_of, len(view.current), len(out))
        return out
