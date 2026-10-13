"""CCI Correction (long), Lambert / ChartSchool: docs/strategies/cci_correction.md, catalog P33.

Bias: bullish once CCI(100) is above +100 and until it is below -100 (hysteresis). The card's weekly CCI(26)
bias is replaced by its published daily alternative, CCI(100), so no weekly resampling is needed. Setup: daily
CCI(26) closed below -100 within the last 10 bars. Trigger: CCI(26) crosses back above 0; entry next open. Stop:
lowest low since the dip - 0.1 x atr_14. Exits (card's proposed test exit): CCI(26) falls back below +100 after
being above it, or 20 sessions. No target. Short mirror not built (long-only engine).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_FLAT, PanelStrategy, finite

NAME = "cci_correction"
SIG_COL = "cci_26"
BIAS_COL = "cci_100"


def bias_up(cci: np.ndarray, level: float) -> bool:
    """Hysteresis bias: True when CCI was last above +level more recently than below -level."""
    ups, downs = np.flatnonzero(cci > level), np.flatnonzero(cci < -level)
    return len(ups) > 0 and (len(downs) == 0 or ups[-1] > downs[-1])


@register("strategy", NAME)
class CCICorrection(PanelStrategy):
    name = NAME
    description = "CCI(100) bullish bias; daily CCI(26) dips below -100 then crosses back above 0."
    default_params: dict[str, Any] = {
        "bias_level": 100.0,  # card: +100 sets the bullish bias, -100 flips it
        "dip_level": -100.0,  # card: daily CCI closes below -100
        "trigger_level": 0.0,  # card: then closes back above 0
        "dip_lookback": 10,  # card: cci_dip_seen = min(cci_26 over the last 10 bars) < -100
        "exit_level": 100.0,  # card: take profit when CCI crosses above +100 and back below
        "stop_atr_buffer": 0.1,  # card: stop = lowest low since the dip - 0.1 x atr_14
        "max_hold_days": 20,  # card: 20-day time stop
        P_MIN_MARKET_TREND: TREND_FLAT,  # card: only when the market trend is up (router); flat allowed here
        P_MIN_RR: 0.0,  # card: rule exit, no target
    }
    features_required = ["atr_14"]
    extra_features = [SIG_COL, BIAS_COL, f"prev_{SIG_COL}"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        cci, prev = row.get(SIG_COL), row.get(f"prev_{SIG_COL}")
        level = float(self.params["exit_level"])
        return finite(cci) and finite(prev) and float(prev) > level >= float(cci)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        cols = ["low", SIG_COL, BIAS_COL]
        view = as_of_view(panel, as_of, ["open", "high", "close", *cols, *self.required_features()])
        n = int(p["dip_lookback"])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            w = view.window(str(row[SYMBOL]), cols)
            cci, t = w[SIG_COL], len(w[SIG_COL]) - 1
            if t < n or not (cci[t - 1] <= float(p["trigger_level"]) < cci[t]):
                continue
            recent = cci[t - n + 1 : t + 1]
            dips = np.flatnonzero(recent < float(p["dip_level"]))
            if not len(dips) or not bias_up(w[BIAS_COL][np.isfinite(w[BIAS_COL])], float(p["bias_level"])):
                continue
            first_dip = t - n + 1 + int(dips[0])
            stop = float(np.min(w["low"][first_dip : t + 1])) - float(p["stop_atr_buffer"]) * float(row["atr_14"])
            close = float(row["close"])
            sig = self.build_signal(
                row, as_of, entry=close, stop=stop, target=None, score=float(np.min(recent)) * -1.0,
                features={SIG_COL: cci[t], "cci_dip_min": np.min(recent), BIAS_COL: w[BIAS_COL][t],
                          "max_hold_days": p["max_hold_days"]},
                notes=f"CCI(100) bias up; CCI(26) dipped to {float(np.min(recent)):.0f}, back above 0 ({cci[t]:.0f})",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
