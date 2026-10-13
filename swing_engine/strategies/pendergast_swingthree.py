"""Pendergast SwingThree (long): docs/strategies/pendergast_swingthree.md (thinkorswim SwingThree).

Signal at the close of t: the previous bar closed above EMA(50) and the close exceeds SMA(high, n) by `offset_pct`
(standing in for the 5-tick buy stop; the original fires intrabar, here the close triggers and the fill is the next
open). Candidate filter (card): trend_state = 1 and volatility >= 2%, with atr_pct_14 standing in for the card's
adr_pct_20 (not a contract column). Stop = max(SMA(low, n), close - 2 x atr_14); exit on the close when the low fails
to hold above SMA(low, n), or after 20 sessions. n = 5 is the engine default (the TOS default is unpublished).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, TREND_UP, PanelStrategy, finite

NAME = "pendergast_swingthree"


def _extras(n: int, ema_len: int) -> list[str]:
    return [f"sma_{n}_of_high", f"sma_{n}_of_low", f"prev_ema_{ema_len}"]


@register("strategy", NAME)
class PendergastSwingThree(PanelStrategy):
    name = NAME
    description = "Prior close over EMA50, close above SMA(high,5) + 0.1%; exit when the low tags SMA(low,5)."
    default_params: dict[str, Any] = {
        "sma_length": 5,  # card: TOS default unpublished, engine default 5 (try 3-10)
        "ema_length": 50,  # card: EMA length default 50
        "offset_pct": 0.001,  # card: 0.1% of price stands in for 5 ticks
        "min_atr_pct": 0.02,  # card: adr_pct_20 >= 2% (atr_pct_14 proxy)
        "stop_atr_mult": 2.0,  # card: stop = max(sma_low_n, entry - 2 x atr_14)
        "max_hold_days": 20,  # card
        P_MIN_TREND: TREND_UP,  # card: trend_state = 1
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["atr_14", "atr_pct_14", "trend_state"]
    extra_features = _extras(5, 50)

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        self.extra_features = _extras(int(self.params["sma_length"]), int(self.params["ema_length"]))

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        band = row.get(self.extra_features[1])
        return finite(band) and float(row["low"]) <= float(band)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        hi_col, lo_col, ema_col = self.extra_features
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        out: list[Signal] = []
        for _, row in rows.iterrows():
            hi, lo, ema_prev, pc = row[hi_col], row[lo_col], row[ema_col], row["prior_close"]
            atr, atr_pct = row["atr_14"], row["atr_pct_14"]
            if not (self.trend_ok(row) and all(finite(x) for x in (hi, lo, ema_prev, pc, atr, atr_pct))):
                continue
            close = float(row["close"])
            if pc <= ema_prev or close <= float(hi) * (1.0 + float(p["offset_pct"])) or atr_pct < float(p["min_atr_pct"]):
                continue
            stop = max(float(lo), close - float(p["stop_atr_mult"]) * float(atr))
            sig = self.build_signal(
                row, as_of, entry=close, stop=stop, target=None, score=float(atr_pct),
                features={hi_col: hi, lo_col: lo, ema_col: ema_prev, "max_hold_days": p["max_hold_days"]},
                notes=f"close {close:.2f} over SMA(high) {float(hi):.2f}; exit when the low tags {float(lo):.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
