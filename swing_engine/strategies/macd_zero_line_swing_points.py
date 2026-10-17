"""MACD zero-line cross confirmed by swing points (long): docs/strategies/macd_zero_line_swing_points.md (ChartSchool).

On the close of t: MACD(12,26) crossed above zero within the last 10 bars; the close breaks above the latest confirmed
swing high for the first time (prior close at or below it); the latest confirmed swing low is above the one before
(higher lows); and level_break == 1 (out of the support/resistance congestion zone). Pivots are `pivot_width` bars
each side (features/levels.py width 5), confirmed only `pivot_width` bars later. Entry next open; stop = latest swing
low - 0.1 x atr_14; target = measured move entry + (swing high - swing low). The card's min_reward_risk 2.0 cannot be
met by that target (risk is always larger than the base range), so the default is 0 and the target is a reference.
The trail to each new swing low needs a stateful stop; the engine's lowest-low trail stands in. 40-session time stop.
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

NAME = "macd_zero_line_swing_points"


def confirmed_pivots(x: np.ndarray, width: int, high: bool, last: int) -> list[int]:
    """Indices i with x[i] the extreme of x[i-width .. i+width] (ties count, as in features/levels.py), confirmed by
    bar ``last`` (i + width <= last)."""
    out = []
    for i in range(width, last - width + 1):
        seg = x[i - width : i + width + 1]
        if (out and i - out[-1] <= width) or not np.isfinite(seg).all():  # a tie next to a pivot is the same swing
            continue
        others = np.delete(seg, width)
        if (x[i] >= others.max()) if high else (x[i] <= others.min()):
            out.append(i)
    return out


@register("strategy", NAME)
class MacdZeroLineSwingPoints(PanelStrategy):
    name = NAME
    description = "MACD crossed above zero within 10 bars; close breaks the last swing high with higher swing lows."
    default_params: dict[str, Any] = {
        "cross_window": 10,  # card: MACD zero up-cross within the last 10 bars (inclusive of t)
        "pivot_width": 5,  # card: features/levels.py pivot width 5
        "lookback_bars": 120,  # engine choice: bars searched for swing points
        "stop_atr_offset": 0.1,  # card: stop = last_swing_low - 0.1 x atr_14
        "max_hold_days": 40,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card says 2.0, unreachable with the measured-move target (see module docstring)
    }
    features_required = ["macd", "level_break", "atr_14"]

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        width, cross_n, look = int(p["pivot_width"]), int(p["cross_window"]), int(p["lookback_bars"])
        cols = ("high", "low", "close", "macd")
        view = as_of_view(panel, as_of, ["open", *cols, *self.required_features()])
        cur = view.current
        out: list[Signal] = []
        for _, row in cur.loc[(cur["level_break"] == 1).fillna(False)].iterrows():
            w = view.window(str(row[SYMBOL]), cols)
            t = len(w["close"]) - 1
            if t < cross_n + 1:
                continue
            m = w["macd"][t - cross_n : t + 1]
            m_prev = w["macd"][t - cross_n - 1 : t]
            if not ((m_prev <= 0) & (m > 0)).any():
                continue
            lo_i = max(0, t - look)
            highs = confirmed_pivots(w["high"][lo_i:], width, True, t - lo_i)
            lows = confirmed_pivots(w["low"][lo_i:], width, False, t - lo_i)
            if not highs or len(lows) < 2:
                continue
            sh, sl, sl_prev = w["high"][lo_i + highs[-1]], w["low"][lo_i + lows[-1]], w["low"][lo_i + lows[-2]]
            close, prior = w["close"][t], w["close"][t - 1]
            if not (close > sh >= prior and sl > sl_prev and finite(row["atr_14"])):
                continue
            stop = sl - float(p["stop_atr_offset"]) * float(row["atr_14"])
            sig = self.build_signal(
                row, as_of, entry=close, stop=stop, target=close + (sh - sl), score=(close - sh) / float(row["atr_14"]),
                features={"swing_high": sh, "swing_low": sl, "prev_swing_low": sl_prev, "macd": row["macd"],
                          "max_hold_days": p["max_hold_days"]},
                notes=f"MACD zero cross; close {close:.2f} > swing high {sh:.2f}, swing lows {sl_prev:.2f} -> {sl:.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(cur), len(out))
        return out
