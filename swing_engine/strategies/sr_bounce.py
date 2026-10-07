"""Schwab support/resistance bounce (long).

Source: docs/sources-schwab-massive.md. Price reaches a prior support level and turns; the target is the
opposite prior level (HON ~$170 low -> ~$200 prior high). Levels come from features/levels.py
(support_1 / resistance_1 are the nearest pivot levels below / above the prior close).
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_FLAT, PanelStrategy, finite

NAME = "sr_bounce"


@register("strategy", NAME)
class SRBounce(PanelStrategy):
    name = NAME
    description = "Low touches support_1, close back above it; stop below support by ATR; target resistance_1."
    default_params: dict[str, Any] = {
        "touch_pct": 0.01,  # |low - support_1| / close must be within this fraction (1%) to count as a touch
        "stop_atr_mult": 1.0,  # stop = support_1 - stop_atr_mult * atr_14
        P_MIN_TREND: TREND_FLAT,  # Schwab: trade with the trend; bounces allowed in sideways (0) or up (1)
        P_MIN_MARKET_TREND: TREND_FLAT,
        P_MIN_RR: 1.0,  # local floor; risk.min_reward_risk applies the portfolio rule
    }
    features_required = ["support_1", "resistance_1", "atr_14", "trend_state"]

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        rows = self.rows_as_of(panel, as_of)
        touch = float(self.params["touch_pct"])
        mult = float(self.params["stop_atr_mult"])
        out: list[Signal] = []
        for _, row in rows.iterrows():
            sup, res, atr = row["support_1"], row["resistance_1"], row["atr_14"]
            if not (finite(sup) and finite(res) and finite(atr)) or not self.trend_ok(row):
                continue
            sup, res, atr = float(sup), float(res), float(atr)
            close, low = float(row["close"]), float(row["low"])
            if close <= 0 or atr <= 0:
                continue
            touch_dist = (low - sup) / close  # negative when the low pierced the level (shakeout)
            if abs(touch_dist) > touch:
                continue
            if close <= sup or res <= close:
                continue
            stop = sup - mult * atr
            risk = close - stop
            reward_risk = (res - close) / risk if risk > 0 else math.nan
            bounce_atr = (close - low) / atr  # how far price rejected the level, in ATRs
            sig = self.build_signal(
                row,
                as_of,
                entry=close,
                stop=stop,
                target=res,
                score=reward_risk + bounce_atr,
                features={
                    "support_1": sup,
                    "resistance_1": res,
                    "atr_14": atr,
                    "touch_dist": touch_dist,
                    "bounce_atr": bounce_atr,
                    "trend_state": row["trend_state"],
                },
                notes=f"bounce off support {sup:.2f}; target resistance {res:.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
