"""Boomers (long), Jeff Cooper: docs/strategies/boomers_cooper.md, catalog C22 (Hit and Run Trading ch. 11).

Basic Boomer: ADX(14) > 30 with +DI > -DI and two consecutive inside days (each inside its prior bar); buy stop just
above the second inside day's high, stop just below its low. Cooper's $0.10 buffer is scaled to the stock as
`max(min_buffer, 0.05 x atr_14)` (card). The order is a one-session buy stop (`entry_type = stop`); the scan re-arms
it while the setup stands. Exit: reference 2R target, 5-session time stop and the engine's breakeven/trail overlay
(card: "a few days; trail"). Not built: the extended-level variant (resting order cancelled on a trade below the
day-1 low) and the short mirror (long-only engine).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import EntryType, Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_FLAT, PanelStrategy, finite

NAME = "boomers_cooper"


@register("strategy", NAME)
class BoomersCooper(PanelStrategy):
    name = NAME
    description = "ADX14 > 30, +DI > -DI, two inside days; buy stop over the 2nd inside high, stop under its low."
    default_params: dict[str, Any] = {
        "adx_min": 30.0,  # card: ADX > 30
        "min_buffer": 0.01,  # card: BUFFER = max(0.01, 0.05 x atr_14) in place of Cooper's $0.10
        "buffer_atr": 0.05,
        "target_r": 2.0,  # card: reference 2R target
        "max_hold_days": 5,  # card: max_hold_days 5
        P_MIN_MARKET_TREND: TREND_FLAT,  # card: healthy_uptrend only if enabled
        P_MIN_RR: 1.0,  # the target is a fixed 2R reference; the floor only guards geometry
    }
    features_required = ["atr_14", "inside_day"]
    extra_features = ["prev_inside_day", "adx_14", "plus_di_14", "minus_di_14"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        keep = (
            (rows["inside_day"] == 1)
            & (rows["prev_inside_day"] == 1)
            & (rows["adx_14"] > float(p["adx_min"]))
            & (rows["plus_di_14"] > rows["minus_di_14"])
        )
        out: list[Signal] = []
        for _, row in rows.loc[keep.fillna(False)].iterrows():
            atr = row["atr_14"]
            if not finite(atr):
                continue
            buf = max(float(p["min_buffer"]), float(p["buffer_atr"]) * float(atr))
            entry, stop = float(row["high"]) + buf, float(row["low"]) - buf
            sig = self.build_signal(
                row, as_of, entry=entry, stop=stop, target=entry + float(p["target_r"]) * (entry - stop),
                score=float(row["adx_14"]),
                features={"adx_14": row["adx_14"], "plus_di_14": row["plus_di_14"], "minus_di_14": row["minus_di_14"],
                          "buffer": buf, "max_hold_days": p["max_hold_days"]},
                notes=f"Boomer: 2 inside days, ADX {float(row['adx_14']):.0f}; buy stop {entry:.2f}, stop {stop:.2f}",
            )
            if sig:
                out.append(sig.model_copy(update={"entry_type": EntryType.STOP}))
        self.log_scan(as_of, len(rows), len(out))
        return out
