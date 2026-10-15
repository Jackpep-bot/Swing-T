"""Bollinger Bands with bullish engulfing (Kosinski, long): docs/strategies/bb_bullish_engulfing_kosinski.md.

Signal bar t: bullish engulfing (prior bar bearish, today bullish, today's body covers the prior body: open <= prior
close and close >= prior open; the card's body definition) at the lower band (low_t or low_{t-1} at or below
bb_lower_20) closing back above it. Stop = close - atr_factor x atr_14. The thinkorswim R:R filter is measured from the
signal-bar high: (bb_upper_20 - high) / (high - stop) >= reward_risk_min. Target = bb_upper_20 at the signal;
`should_exit` when the high reaches the (moving) upper band. Entry next open.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, PanelStrategy, finite

NAME = "bb_bullish_engulfing_kosinski"
UPPER, LOWER = "bb_upper_20", "bb_lower_20"


@register("strategy", NAME)
class BBBullishEngulfing(PanelStrategy):
    name = NAME
    description = "Bullish engulfing at the lower Bollinger band; ATR stop; target and exit at the upper band."
    default_params: dict[str, Any] = {
        "atr_factor": 2.0,  # card: stop = close - ATR x factor (2.0 engine choice; source range 1-3)
        "reward_risk_min": 1.0,  # card: (upper - high) / (high - stop) >= 1.0
        "max_hold_days": 15,  # card: engine choice
        P_MIN_TREND: TREND_DOWN,
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 1.0,  # card: build_signal recomputes R:R from the entry, so 1.0 here as well
    }
    features_required = ["trend_state", "atr_14", UPPER, LOWER]
    extra_features = [UPPER, LOWER]  # contract columns; listed so panels without Bollinger columns get them
    prior_columns = ["open", "low", "close", LOWER]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        upper = row.get(UPPER)
        return bars_held >= int(self.params["max_hold_days"]) or (finite(upper) and float(row["high"]) >= upper)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        p = self.params
        out: list[Signal] = []
        for _, row in rows.iterrows():
            keys = ("open", "high", "low", "close", "prior_open", "prior_close", "prior_low", UPPER, LOWER, "atr_14")
            if not all(finite(row.get(k)) for k in keys) or not self.trend_ok(row):
                continue
            o, h, c = float(row["open"]), float(row["high"]), float(row["close"])
            po, pc = float(row["prior_open"]), float(row["prior_close"])
            engulf = pc < po and c > o and o <= pc and c >= po
            lower, upper = float(row[LOWER]), float(row[UPPER])
            prior_lower = row.get(f"prior_{LOWER}")
            touched = float(row["low"]) <= lower or (finite(prior_lower) and float(row["prior_low"]) <= prior_lower)
            if not (engulf and touched and c > lower):
                continue
            stop = c - float(p["atr_factor"]) * float(row["atr_14"])
            rr_tos = (upper - h) / (h - stop) if h > stop else float("nan")
            if not (finite(rr_tos) and rr_tos >= float(p["reward_risk_min"])):
                continue
            sig = self.build_signal(
                row, as_of, entry=c, stop=stop, target=upper, score=rr_tos,
                features={UPPER: upper, LOWER: lower, "rr_from_high": rr_tos, "atr_14": row["atr_14"]},
                notes=f"bullish engulfing at lower band {lower:.2f}; target upper band {upper:.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
