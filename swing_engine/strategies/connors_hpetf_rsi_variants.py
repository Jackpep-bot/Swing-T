"""Connors "High Probability ETF Trading" variants (long): docs/strategies/connors_hpetf_rsi_variants.md.

All variants need close > sma_200. `variant`:
* `rsi_25_75`: RSI(4) closes < 25; exit RSI(4) > 55.
* `multiple_days_down`: close < sma_5 and 4 of the last 5 closes down; exit close > sma_5.
* `rsi_10_6`: RSI(2) < 10; exit close > sma_5.
The source enters at the close; the engine enters at the next open (no MOC hook). The aggressive add-ons need a
scale-in hook and are not modelled. Card stop: entry - 2 x atr_14; 6-session time stop. The card's universe is index
and sector ETFs: set it through the settings universe. Thresholds are unverified (card).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, finite

NAME = "connors_hpetf_rsi_variants"
RSI_25_75, DAYS_DOWN, RSI_10_6 = "rsi_25_75", "multiple_days_down", "rsi_10_6"


@register("strategy", NAME)
class ConnorsHPETF(PanelStrategy):
    name = NAME
    description = "Connors ETF variants over sma_200: RSI(4)<25, 4-of-5 down days, or RSI(2)<10; quick rule exits."
    default_params: dict[str, Any] = {
        "variant": RSI_25_75,  # card table: rsi_25_75 | multiple_days_down | rsi_10_6
        "rsi4_entry": 25.0,  # card: RSI(4) closes < 25
        "rsi4_exit": 55.0,  # card: exit RSI(4) > 55
        "down_days_min": 4,  # card: down closes on 4 of the last 5 days
        "rsi2_entry": 10.0,  # card: RSI(2) < 10
        "stop_atr_mult": 2.0,  # card: catastrophic stop entry - 2 x atr_14
        "max_hold_days": 6,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: the instrument's own 200-day is the only trend gate
        P_MIN_RR: 0.0,  # card: rule exit, no target
    }
    features_required = ["sma_200", "rsi_2", "atr_14"]
    extra_features = ["rsi_4", "sma_5", "down_days_5"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        if self.params["variant"] == RSI_25_75:
            rsi4 = row.get("rsi_4")
            return finite(rsi4) and float(rsi4) > float(self.params["rsi4_exit"])
        sma5 = row.get("sma_5")
        return finite(sma5) and float(row["close"]) > float(sma5)

    def _setup(self, row: pd.Series) -> float | None:
        """Oversold depth (higher = deeper) when the variant's setup holds, else None."""
        p, close = self.params, float(row["close"])
        if p["variant"] == RSI_25_75:
            rsi4 = row["rsi_4"]
            return float(p["rsi4_entry"]) - float(rsi4) if finite(rsi4) and rsi4 < float(p["rsi4_entry"]) else None
        if p["variant"] == RSI_10_6:
            rsi2 = row["rsi_2"]
            return float(p["rsi2_entry"]) - float(rsi2) if finite(rsi2) and rsi2 < float(p["rsi2_entry"]) else None
        if p["variant"] == DAYS_DOWN:
            sma5, down = row["sma_5"], row["down_days_5"]
            if finite(sma5) and finite(down) and close < float(sma5) and down >= int(p["down_days_min"]):
                return float(down)
            return None
        raise ValueError(f"{NAME}: unknown variant {p['variant']!r}")

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        out: list[Signal] = []
        for _, row in rows.iterrows():
            sma200, atr = row["sma_200"], row["atr_14"]
            if not (finite(sma200) and finite(atr)) or float(row["close"]) <= float(sma200):
                continue
            depth = self._setup(row)
            if depth is None:
                continue
            close = float(row["close"])
            sig = self.build_signal(
                row, as_of, entry=close, stop=close - float(self.params["stop_atr_mult"]) * float(atr), target=None,
                score=depth,
                features={"rsi_4": row["rsi_4"], "rsi_2": row["rsi_2"], "down_days_5": row["down_days_5"],
                          "sma_5": row["sma_5"], "max_hold_days": self.params["max_hold_days"]},
                notes=f"Connors {self.params['variant']} over the 200-day",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
