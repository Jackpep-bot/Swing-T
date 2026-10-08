"""Smash Day / Hidden Smash Day (long), docs/strategies/williams_smash_day.md (Larry Williams 1999 ch. 7, catalog C11).

Setup bar k: naked smash = close below the prior day's low; hidden smash = up close (close > prior close) in the lowest
25% of its own range. Entry: buy stop 1 tick over the smash-day high (EntryType.STOP), left working for `order_days`
sessions: the signal is re-issued on each of the next sessions while no high has reached the level (engine stop
orders live one session) and no low has undercut the smash low (engine choice: the setup is void then). Stop 1 tick
under the smash-day low. Trend gate (card): trend_state == 1 and close > sma_50. No target; 5-session cap.
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

NAME = "williams_smash_day"
NAKED, HIDDEN, BOTH = "naked", "hidden", "both"
ARRAYS = ("high", "low", "close")


@register("strategy", NAME)
class WilliamsSmashDay(PanelStrategy):
    name = NAME
    description = "Naked or hidden smash day in an uptrend; buy stop 1 tick over its high for up to 3 sessions."
    default_params: dict[str, Any] = {
        "smash_type": BOTH,  # card: naked and hidden smash days ("naked" / "hidden" for separate trials)
        "hidden_close_pos_max": 0.25,  # card: close in the lowest 25% of the range (keep fixed)
        "order_days": 3,  # card: buy stop left working 1-3 days (keep 3 fixed)
        "tick": 0.01,  # card: 1 tick over the high / under the low
        "trend_ma": "sma_50",  # card: close > sma_50 ...
        "max_hold_days": 5,  # card
        P_MIN_TREND: TREND_UP,  # card: ... and trend_state == 1
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no target taught
    }
    features_required = ["trend_state"]

    def required_features(self) -> list[str]:
        return [*self.features_required, str(self.params["trend_ma"])]

    def _smash(self, w: dict[str, np.ndarray], k: int) -> bool:
        h, lo, c = w["high"], w["low"], w["close"]
        kind = str(self.params["smash_type"])
        naked = c[k] < lo[k - 1]
        rng = h[k] - lo[k]
        hidden = c[k] > c[k - 1] and rng > 0 and (c[k] - lo[k]) <= float(self.params["hidden_close_pos_max"]) * rng
        return bool((naked and kind in (NAKED, BOTH)) or (hidden and kind in (HIDDEN, BOTH)))

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        view = c1.view(self, panel, as_of, list(ARRAYS))
        ma, tick, days = str(self.params["trend_ma"]), float(self.params["tick"]), int(self.params["order_days"])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            if not self.trend_ok(row) or not (finite(row[ma]) and float(row["close"]) > float(row[ma])):
                continue
            w = view.window(str(row[SYMBOL]), ARRAYS)
            t = len(w["close"]) - 1
            for k in range(t, max(0, t - days), -1):
                if not self._smash(w, k):
                    continue
                level, low = float(w["high"][k]) + tick, float(w["low"][k])
                if (w["high"][k + 1 : t + 1] >= level).any() or (w["low"][k + 1 : t + 1] < low).any():
                    break  # already triggered or voided
                sig = c1.stop_entry(self.build_signal(
                    row, as_of, entry=level, stop=low - tick, target=None, score=-float(t - k),
                    features={"smash_high": w["high"][k], "smash_low": low, "smash_age": t - k,
                              "max_hold_days": self.params["max_hold_days"]},
                    notes=f"smash day {t - k} session(s) ago: buy stop {level:.2f}, stop {low - tick:.2f}"))
                if sig:
                    out.append(sig)
                break
        self.log_scan(as_of, len(view.current), len(out))
        return out
