"""Katsanos RSMK relative-strength zero cross (long): docs/strategies/katsanos_rsmk.md.

RSMK = 100 x EMA_3(ln(C/SPY) - ln(C/SPY)[90]) (`rsmk_90_3`, features.extra; needs SPY rows or the market frame).
Entry when RSMK crosses above 0, next open. Stop entry - 2.5 x atr_14 (engine-required); time exit after 20 sessions
(the article's exit length is unpublished). Optional trend_state gate via min_trend_state (off by default).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, PanelStrategy, finite

NAME = "katsanos_rsmk"


def _extras(n: int, m: int) -> list[str]:
    return [f"rsmk_{n}_{m}", f"prev_rsmk_{n}_{m}"]


@register("strategy", NAME)
class KatsanosRSMK(PanelStrategy):
    name = NAME
    description = "RSMK (90-bar log relative strength vs SPY, EMA 3) crosses above zero; 20-session time exit."
    default_params: dict[str, Any] = {
        "rs_length": 90,  # card: n = 90 (Traders' Tips / TOS default)
        "ema_length": 3,  # card: m = 3
        "stop_atr_mult": 2.5,  # card: stop entry - 2.5 x atr_14
        "max_hold_days": 20,  # card: engine assumption until the article default is confirmed
        P_MIN_TREND: TREND_DOWN,  # card: optional require_trend_state 1 (off)
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["atr_14", "trend_state"]
    extra_features = _extras(90, 3)

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        self.extra_features = _extras(int(self.params["rs_length"]), int(self.params["ema_length"]))

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        col, prev_col = self.extra_features
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        out: list[Signal] = []
        for _, row in rows.iterrows():
            r, r_prev, atr = row[col], row[prev_col], row["atr_14"]
            if not (finite(r) and finite(r_prev) and finite(atr)) or not (r > 0 >= r_prev):
                continue
            if float(self.params[P_MIN_TREND]) > TREND_DOWN and not self.trend_ok(row):
                continue
            close = float(row["close"])
            sig = self.build_signal(
                row, as_of, entry=close, stop=close - float(self.params["stop_atr_mult"]) * float(atr), target=None,
                score=float(r), features={col: r, "atr_14": atr, "max_hold_days": self.params["max_hold_days"]},
                notes=f"RSMK crossed above zero ({float(r_prev):.2f} -> {float(r):.2f})",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
