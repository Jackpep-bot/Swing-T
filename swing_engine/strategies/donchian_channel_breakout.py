"""Donchian channel breakout (long): docs/strategies/donchian_channel_breakout.md (thinkorswim/Cagigas 40/15).

Close-based variant from the card: close above the highest high of the prior `entry_len` bars (dc_high_40) with
trend_state >= 0; entry next open. Initial stop = max(prior `exit_len`-bar low, close - 2 x atr_14). The exit
channel (low below the lowest low of the prior 15 bars) is a stop, so it runs through `trail_stop`: at each close the
stop moves to the `exit_len`-bar low including that bar, which is the prior-15 channel for the next session (the
engine ratchets it, so it never loosens). The engine's breakeven overlay is off: the channel is the exit.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, TREND_FLAT, PanelStrategy, finite

NAME = "donchian_channel_breakout"


def _extras(entry_len: int, exit_len: int) -> list[str]:
    return [f"dc_high_{entry_len}", f"dc_low_{exit_len}", f"low_{exit_len}"]


@register("strategy", NAME)
class DonchianChannelBreakout(PanelStrategy):
    name = NAME
    description = "Close above the prior 40-bar high; stop and exit on the prior 15-bar low channel."
    default_params: dict[str, Any] = {
        "entry_len": 40,  # card: entry length 40 (catalog)
        "exit_len": 15,  # card: exit length 15
        "stop_atr_mult": 2.0,  # card: initial stop = max(dc_low_15, entry - 2 x atr_14)
        "max_hold_days": 40,  # card
        P_MIN_TREND: TREND_FLAT,  # card: trend_state >= 0
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["atr_14", "trend_state"]
    extra_features = _extras(40, 15)
    engine_trail = False

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        self.extra_features = _extras(int(self.params["entry_len"]), int(self.params["exit_len"]))

    def trail_stop(self, row: pd.Series) -> float | None:
        level = row.get(self.extra_features[2])
        return float(level) if finite(level) else None

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        hi_col, lo_col, _ = self.extra_features
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        out: list[Signal] = []
        for _, row in rows.iterrows():
            hi, lo, atr = row[hi_col], row[lo_col], row["atr_14"]
            close = float(row["close"])
            if not (self.trend_ok(row) and finite(hi) and finite(lo) and finite(atr)) or close <= float(hi):
                continue
            stop = max(float(lo), close - float(self.params["stop_atr_mult"]) * float(atr))
            sig = self.build_signal(
                row, as_of, entry=close, stop=stop, target=None, score=(close - float(hi)) / float(atr),
                features={hi_col: hi, lo_col: lo, "atr_14": atr, "max_hold_days": self.params["max_hold_days"]},
                notes=f"close {close:.2f} > {self.params['entry_len']}-bar high {float(hi):.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
