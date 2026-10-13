"""TTM Squeeze (long), John Carter / LazyBear: docs/strategies/ttm_squeeze.md, catalog B36 / P21 / C40.

Squeeze on: BB(20, 2) inside KC(20, SMA basis +/- 1.5 x SMA20 true range). Trigger: the first bar after at least
`min_squeeze_bars` squeeze-on bars on which it is off (fired), with momentum (`sqz_mom_20`, linreg endpoint of
close - ((HH20 + LL20)/2 + SMA20)/2) above zero and rising. Entry next open. Stop: max(5-bar low - 0.01,
entry - 2 x atr_14). Exit: two consecutive momentum declines or momentum below zero, or 15 sessions. No target.
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

NAME = "ttm_squeeze"
MOM = "sqz_mom_20"
BANDS = ("bb_upper_20", "bb_lower_20", "kc_upper_20", "kc_lower_20")


@register("strategy", NAME)
class TTMSqueeze(PanelStrategy):
    name = NAME
    description = "First bar the Bollinger(20,2) leaves the Keltner(20,1.5) squeeze with rising positive momentum."
    default_params: dict[str, Any] = {
        "min_squeeze_bars": 1,  # card: MIN_SQZ_BARS 1 (test 5)
        "stop_low_bars": 5,  # card: stop = max(min(low, 5 bars) - 0.01, entry - 2 x atr_14)
        "stop_tick": 0.01,
        "stop_atr_mult": 2.0,
        "max_hold_days": 15,  # card
        P_MIN_TREND: TREND_DOWN,  # card: trend_state >= 1 is a variant, off by default
        P_MIN_MARKET_TREND: TREND_FLAT,  # card: healthy_uptrend only if enabled
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["atr_14", "trend_state"]
    extra_features = [*BANDS, MOM, f"prev_{MOM}", f"prev_prev_{MOM}"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        m, m1, m2 = (row.get(c) for c in (MOM, f"prev_{MOM}", f"prev_prev_{MOM}"))
        if finite(m) and float(m) < 0:
            return True
        return all(finite(x) for x in (m, m1, m2)) and float(m) < float(m1) < float(m2)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        cols = ["low", MOM, *BANDS]
        view = as_of_view(panel, as_of, ["open", "high", "close", *cols, *self.required_features()])
        n_sqz, n_low = int(p["min_squeeze_bars"]), int(p["stop_low_bars"])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            if int(p[P_MIN_TREND]) > TREND_DOWN and not self.trend_ok(row):
                continue
            w = view.window(str(row[SYMBOL]), cols)
            mom, t = w[MOM], len(w["low"]) - 1
            on = (w["bb_upper_20"] < w["kc_upper_20"]) & (w["bb_lower_20"] > w["kc_lower_20"])
            if t < max(n_sqz, n_low) or on[t] or not on[t - n_sqz : t].all() or not np.isfinite(w["bb_upper_20"][t]):
                continue
            if not (finite(mom[t]) and finite(mom[t - 1]) and mom[t] > 0 and mom[t] > mom[t - 1]):
                continue
            close = float(row["close"])
            stop = max(float(np.min(w["low"][t - n_low + 1 : t + 1])) - float(p["stop_tick"]),
                       close - float(p["stop_atr_mult"]) * float(row["atr_14"]))
            run = int(np.argmin(on[t - 1 :: -1])) if not on[: t].all() else t
            sig = self.build_signal(
                row, as_of, entry=close, stop=stop, target=None, score=float(mom[t]) / close,
                features={MOM: mom[t], "squeeze_bars": run, "max_hold_days": p["max_hold_days"]},
                notes=f"squeeze fired after {run} bar(s); momentum {mom[t]:.3f} > 0 and rising",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
