"""Connors TPS (time, price, scale-in), long: docs/strategies/connors_tps_scale_in.md (High Probability ETF Trading).

Rules: close > sma_200; rsi_2 < 25 on two consecutive closes -> buy 10% of the planned position; each later close
below the previous entry adds 20/30/40%; exit everything when rsi_2 closes above 70; no stop.
Approximation: the engine has no scale-in hook (one Signal = one fill, card "Needs a scale-in hook"), so this module
enters the WHOLE position on the initial setup and never adds. That removes the averaging-down skew that defines TPS;
results measure only the setup and the RSI(2) > 70 exit. Catastrophic stop entry - 3 x atr_14 (card), 10-day time
exit (card), no target. Universe per card: index and sector ETFs (the module itself does not filter).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, RollingSpec, finite

NAME = "connors_tps_scale_in"


@register("strategy", NAME)
class ConnorsTPS(PanelStrategy):
    name = NAME
    description = "TPS setup (close > sma_200, rsi_2 < 25 two days) as a single entry; exit rsi_2 > 70; 3 ATR stop."
    default_params: dict[str, Any] = {
        "rsi_entry": 25.0,  # card: RSI(2) below 25 ...
        "rsi_days": 2,  # ... on two consecutive closes
        "rsi_exit": 70.0,  # card: exit when RSI(2) closes above 70
        "stop_atr_mult": 3.0,  # card: catastrophic stop -3 x atr_14 from the first entry
        "max_hold_days": 10,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card
    }
    features_required = ["rsi_2", "sma_200", "atr_14"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        rsi2 = row.get("rsi_2")
        return bars_held >= int(self.params["max_hold_days"]) or (
            finite(rsi2) and float(rsi2) > float(self.params["rsi_exit"]))

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        spec = RollingSpec("rsi_2", "max", int(self.params["rsi_days"]))
        rows = self.rows_as_of(panel, as_of, rolling=[spec])
        keep = (rows["close"] > rows["sma_200"]) & (rows[spec.out] < float(self.params["rsi_entry"]))
        out: list[Signal] = []
        for _, row in rows.loc[keep.fillna(False)].iterrows():
            close, atr = float(row["close"]), float(row["atr_14"])
            if not finite(atr):
                continue
            sig = self.build_signal(
                row, as_of, entry=close, stop=close - float(self.params["stop_atr_mult"]) * atr, target=None,
                score=-float(row["rsi_2"]), features={"rsi_2": row["rsi_2"], "max_rsi_2": row[spec.out]},
                notes="TPS setup, full size at once (no scale-in hook)",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
