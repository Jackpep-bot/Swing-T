"""Parabolic SAR stop-and-reverse, long side (Wilder 1978; TradeStation Parabolic LE / Parabolic_m Trail LX,
TradingView Parabolic SAR Strategy), docs/strategies/parabolic_sar_reversal.md (catalog B82/P13).

While the SAR is short (`psar_dir == -1`), re-issue the TradeStation buy stop at tomorrow's SAR (`psar` on row t is the
SAR for bar t+1; EntryType.STOP, one session). Initial stop = the new long SAR after the flip, i.e. the short leg's
extreme point (its lowest low); `first_stop_atr3_mult` switches to the Parabolic_m first-bar stop min(EP, low -
1.5 x ATR(3)). The position then trails on the SAR (`trail_stop`, ratcheted by the engine), the source's own exit;
reference target 4R; 40-session cap. AF 0.02 / 0.02 / 0.20 (features.extra PSAR constants).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "parabolic_sar_reversal"
PSAR, PSAR_DIR, ATR3 = "psar", "psar_dir", "atr_3"


@register("strategy", NAME)
class ParabolicSARReversal(PanelStrategy):
    name = NAME
    description = "Buy stop at the falling SAR; stop at the short leg's low; trail on the rising SAR."
    default_params: dict[str, Any] = {
        "first_stop_atr3_mult": None,  # card option: Parabolic_m first-bar stop low - 1.5 x ATR(3); None = EP stop
        "target_r": 4.0,  # card: reference target_r 4.0
        "max_hold_days": 40,  # card
        P_MIN_TREND: TREND_DOWN,  # demonstration rule: no filter (router: healthy_uptrend only)
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 1.0,  # card
    }
    features_required = ["trend_state"]
    extra_features = [PSAR, PSAR_DIR, ATR3]
    engine_trail = False  # the SAR is the trail

    def trail_stop(self, row: pd.Series) -> float | None:
        sar, d = row.get(PSAR), row.get(PSAR_DIR)
        return float(sar) if finite(sar) and finite(d) and float(d) > 0 else None

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        view = c1.view(self, panel, as_of, [PSAR, PSAR_DIR, ATR3])
        mult = self.params.get("first_stop_atr3_mult")
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            if row[PSAR_DIR] != -1 or not finite(row[PSAR]) or not self.trend_ok(row):
                continue
            w = view.window(str(row[SYMBOL]), ["low", PSAR_DIR])
            not_short = np.flatnonzero(w[PSAR_DIR] != -1)
            start = int(not_short[-1]) + 1 if len(not_short) else 0
            ep = float(w["low"][start:].min())
            stop = ep
            if mult is not None and finite(row[ATR3]):
                stop = min(ep, float(row["low"]) - float(mult) * float(row[ATR3]))
            entry = float(row[PSAR])
            sig = c1.stop_entry(self.build_signal(
                row, as_of, entry=entry, stop=stop, target=entry + float(self.params["target_r"]) * (entry - stop),
                score=-(entry - float(row["close"])) / float(row["close"]),
                features={PSAR: entry, "short_leg_ep": ep, "max_hold_days": self.params["max_hold_days"]},
                notes=f"PSAR reversal: buy stop {entry:.2f}, stop {stop:.2f}"))
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
