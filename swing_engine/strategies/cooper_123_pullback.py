"""Jeff Cooper 1-2-3-4 pullback (long), docs/strategies/cooper_123_pullback.md (Hit and Run Trading, catalog C20).

Hit list: ADX(14) >= 30 with +DI > -DI on the as-of bar (day 3). Setup: three counted bars in a row each with a low
below the previous counted bar's low; inside days are skipped (neither counted nor breaking the run) and the first
counted bar must lie within `max_setup_bars` of day 3. Entry (card option 1, the stop-entry hook): buy stop one tick
above the day-3 high for the next session; stop one tick under the day-3 low. Target: prior swing high = max high of
the `swing_high_bars` bars before the first counted bar (pullback_holy_grail convention), `min_reward_risk` 1.0. Exit
over 1-5 days: `max_hold_days` 5 plus the engine's breakeven-at-+1R trail (card). Short mirror not used (long-only).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, SYMBOL, TREND_DOWN, PanelStrategy

NAME = "cooper_123_pullback"
ADX, PDI, MDI = "adx_14", "plus_di_14", "minus_di_14"


def lower_low_run(low: np.ndarray, inside: np.ndarray, t: int, n: int, max_bars: int) -> int | None:
    """Index of the reference bar c0 when bars c1..cn (cn = t) are n counted lower lows, inside days skipped."""
    if inside[t] == 1:
        return None
    counted = [t]
    k = t - 1
    while k >= 0 and t - k <= max_bars and len(counted) <= n:
        if inside[k] != 1:
            counted.append(k)
        k -= 1
    if len(counted) <= n:
        return None
    lows = low[counted]  # newest first
    return counted[-1] if np.all(lows[:-1] < lows[1:]) else None


@register("strategy", NAME)
class Cooper123Pullback(PanelStrategy):
    name = NAME
    description = "ADX > 30 trend, three lower lows (inside days skipped); buy stop over day 3 high, stop under its low."
    default_params: dict[str, Any] = {
        "adx_min": 30.0,  # card: ADX(14) > 30 with +DI > -DI
        "n_lower_lows": 3,  # card: three consecutive lower lows
        "max_setup_bars": 10,  # card: c0 within 10 bars of t
        "tick": 0.01,  # card: one tick over day 3 high / under day 3 low
        "swing_high_bars": 20,  # card: target = max(high) over the 20 bars before c0
        "max_hold_days": 5,  # card: exit over 1-5 days
        P_MIN_TREND: TREND_DOWN,  # the ADX/DI hit list is the trend filter
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 1.0,  # card: min_reward_risk 1.0
    }
    features_required = ["inside_day", "trend_state"]
    extra_features = [ADX, PDI, MDI]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        p = self.params
        v = c1.view(self, panel, as_of, [])
        cur = v.current
        keep = ((cur[ADX] >= float(p["adx_min"])) & (cur[PDI] > cur[MDI])).fillna(False)
        tick, swing_n = float(p["tick"]), int(p["swing_high_bars"])
        out: list[Signal] = []
        for _, row in cur.loc[keep].iterrows():
            if not self.trend_ok(row):
                continue
            w = v.window(str(row[SYMBOL]), ["high", "low", "inside_day"])
            t = len(w["low"]) - 1
            c0 = lower_low_run(w["low"], w["inside_day"], t, int(p["n_lower_lows"]), int(p["max_setup_bars"]))
            if c0 is None or c0 < swing_n:
                continue
            entry, stop = float(w["high"][t]) + tick, float(w["low"][t]) - tick
            target = float(np.max(w["high"][c0 - swing_n : c0]))
            sig = self.build_signal(row, as_of, entry=entry, stop=stop, target=target, score=float(row[ADX]),
                                    features={ADX: row[ADX], "swing_high": target, "max_hold_days": p["max_hold_days"]},
                                    notes=f"1-2-3 pullback: ADX {row[ADX]:.0f}, buy stop {entry:.2f}, target {target:.2f}")
            sig = c1.stop_entry(sig)
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(cur), len(out))
        return out
