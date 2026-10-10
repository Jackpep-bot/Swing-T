"""Garner SimpleMeanReversion z-score (long): docs/strategies/zscore_mean_reversion_garner.md (thinkorswim).

z = (close - SMA(L)) / StDev(L) with L = 20, so sd = (bb_upper_20 - sma_20) / 2 (2-std Bollinger, ddof 0) and the slow
SMA (10 x L) is sma_200. Buy when z first crosses below -1.0 while sma_20 > sma_200; sell to close when z > -0.5
(`should_exit`). The source has no stop; the engine needs one: entry - 2 x atr_14 (card, as rsi2_meanrev). Reference
target = the exit level sma_20 - 0.5 x sd. The short side is not used.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, PanelStrategy, finite

NAME = "zscore_mean_reversion_garner"
MID, UPPER = "sma_20", "bb_upper_20"
BB_STD = 2.0


def zscore(close: Any, mid: Any, upper: Any) -> float:
    sd = (float(upper) - float(mid)) / BB_STD
    return (float(close) - float(mid)) / sd if sd > 0 else float("nan")


@register("strategy", NAME)
class ZScoreMeanReversionGarner(PanelStrategy):
    name = NAME
    description = "z(20) crosses below -1 with sma_20 > sma_200; exit z > -0.5; 2 ATR stop."
    default_params: dict[str, Any] = {
        "entry_z": -1.0,  # card: buy to open when zScore < -1.0
        "exit_z": -0.5,  # card: sell to close when zScore > -0.5
        "stop_atr_mult": 2.0,  # card: engine choice, as rsi2_meanrev
        "max_hold_days": 10,  # card
        P_MIN_TREND: TREND_DOWN,  # the fast/slow SMA test is the trend filter
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: reference target is the exit level, R:R honest and low
    }
    features_required = ["trend_state", "atr_14", "sma_200", MID, UPPER]
    extra_features = [UPPER]  # contract column; listed so panels without Bollinger columns get it
    prior_columns = ["close", MID, UPPER]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        if not all(finite(row.get(c)) for c in ("close", MID, UPPER)):
            return False
        return zscore(row["close"], row[MID], row[UPPER]) > float(self.params["exit_z"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        entry_z, exit_z = float(self.params["entry_z"]), float(self.params["exit_z"])
        out: list[Signal] = []
        for _, row in rows.iterrows():
            vals = [row.get(c) for c in ("close", MID, UPPER, "prior_close", f"prior_{MID}", f"prior_{UPPER}",
                                         "sma_200", "atr_14")]
            if not all(finite(v) for v in vals) or not float(row[MID]) > float(row["sma_200"]):
                continue
            z = zscore(row["close"], row[MID], row[UPPER])
            z_prev = zscore(row["prior_close"], row[f"prior_{MID}"], row[f"prior_{UPPER}"])
            if not (z < entry_z <= z_prev) or not self.trend_ok(row):
                continue
            close, mid = float(row["close"]), float(row[MID])
            sd = (float(row[UPPER]) - mid) / BB_STD
            sig = self.build_signal(
                row, as_of, entry=close, stop=close - float(self.params["stop_atr_mult"]) * float(row["atr_14"]),
                target=mid + exit_z * sd, score=-z,
                features={"zscore": z, "zscore_prev": z_prev, MID: mid, "sma_200": row["sma_200"]},
                notes=f"z {z:.2f} crossed below {entry_z}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
