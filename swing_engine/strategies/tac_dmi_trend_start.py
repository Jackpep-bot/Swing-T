"""TAC-DMI trend start (long), docs/strategies/tac_dmi_trend_start.md (thinkorswim TAC_DMI, BC Low "Identify the
Start of a Trend with DMI").

Clusters of short Wilder DMI lines (periods 3, 4, 5: the article's unverified lengths, fixed and untuned, tolerance
0): long when every +DI is below 10 and the lowest reaches 5 while the ADX cluster turns down from 70 (every ADX
below its prior value, the highest prior ADX >= 70). Exit on the mirrored short signal (-DI cluster) or after 10
sessions. Stop (card): lowest low of the last 5 bars - 0.1 x atr_14; target 2R. The optional trend filter is off.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, PanelStrategy, finite

NAME = "tac_dmi_trend_start"
LENGTHS = (3, 4, 5)  # card v1: 3/4/5 for both ADX and DI (unverified; do not tune)


def dmi_names(side: str) -> list[str]:
    return [f"{side}_{n}" for n in LENGTHS]


ADX, PREV_ADX = dmi_names("adx"), dmi_names("prev_adx")
PLUS, MINUS = dmi_names("plus_di"), dmi_names("minus_di")


@register("strategy", NAME)
class TacDmiTrendStart(PanelStrategy):
    name = NAME
    description = "+DI(3,4,5) cluster below 10 touching 5 as the ADX(3,4,5) cluster turns down from 70; 2R target."
    default_params: dict[str, Any] = {
        "di_cluster_max": 10.0,  # card: DI lines cluster below 10 ...
        "di_extreme": 5.0,  # ... and the lowest reaches 5
        "adx_turn_level": 70.0,  # card: ADX cluster turns down from 70
        "stop_lookback": 5,  # card: lowest low of the last 5 bars ...
        "stop_atr_buffer": 0.1,  # ... minus 0.1 x atr_14
        "target_r": 2.0,  # card
        "max_hold_days": 10,  # card
        P_MIN_TREND: TREND_DOWN,  # card: optional trend filter (engine choice) off
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 2.0,  # card
    }
    features_required = ["atr_14", "trend_state"]
    extra_features = [*ADX, *PREV_ADX, *PLUS, *MINUS, "low_5"]

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        self.extra_features = [*ADX, *PREV_ADX, *PLUS, *MINUS, f"low_{int(self.params['stop_lookback'])}"]

    def _cluster(self, row: pd.Series, di_cols: list[str]) -> bool:
        vals = [row.get(c) for c in [*di_cols, *ADX, *PREV_ADX]]
        if not all(finite(v) for v in vals):
            return False
        n = len(LENGTHS)
        di, adx, prev = [float(v) for v in vals[:n]], [float(v) for v in vals[n : 2 * n]], [float(v) for v in vals[2 * n :]]
        p = self.params
        return (
            max(di) < float(p["di_cluster_max"])
            and min(di) <= float(p["di_extreme"])
            and max(prev) >= float(p["adx_turn_level"])
            and all(a < b for a, b in zip(adx, prev, strict=True))
        )

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"]) or self._cluster(row, MINUS)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        low_col = self.extra_features[-1]
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        out: list[Signal] = []
        for _, row in rows.iterrows():
            atr, low_n = row["atr_14"], row[low_col]
            if not (finite(atr) and finite(low_n)) or not self.trend_ok(row) or not self._cluster(row, PLUS):
                continue
            close = float(row["close"])
            stop = float(low_n) - float(p["stop_atr_buffer"]) * float(atr)
            sig = self.build_signal(
                row,
                as_of,
                entry=close,
                stop=stop,
                target=close + float(p["target_r"]) * (close - stop),
                score=max(float(row[c]) for c in PREV_ADX),
                features={**{c: row[c] for c in [*ADX, *PLUS]}, "atr_14": atr, "max_hold_days": p["max_hold_days"]},
                notes="TAC-DMI: +DI(3,4,5) cluster "
                + "/".join(f"{float(row[c]):.1f}" for c in PLUS)
                + " as ADX turns down from "
                + f"{max(float(row[c]) for c in PREV_ADX):.0f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
