"""Bollinger squeeze breakout (long): docs/strategies/bollinger_squeeze_breakout.md.

Setup: BandWidth (bb_width_20) at or below its 10th percentile of the trailing 126 bars on any of the 5 bars before
the as-of bar (`prev_min_5_of_pctile_126_of_bb_width_20`). Trigger, Method I: close above bb_upper_20; Method IV
(`method: 4`): also the prior close above the prior upper band and adx_14 >= adx_min. Stop = max(sma_20, low - tick)
but never more than 2 x atr_14 below the close; exit on a close below sma_20 (the mid band) or after 20 sessions.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, TREND_UP, PanelStrategy, finite

NAME = "bollinger_squeeze_breakout"
SQUEEZE_COL = "prev_min_5_of_pctile_126_of_bb_width_20"
PREV_UPPER = "prev_bb_upper_20"
ADX_COL = "adx_14"
METHOD_IV = 4


@register("strategy", NAME)
class BollingerSqueezeBreakout(PanelStrategy):
    name = NAME
    description = "BandWidth in its 126-bar bottom decile within 5 bars, then a close above the upper band."
    default_params: dict[str, Any] = {
        "squeeze_pctile": 0.10,  # card: bbw_pctile_126 <= 0.10 on any of the prior 5 bars
        "method": 1,  # card: Method I (close > upper band); 4 = Method IV (2 closes above + ADX)
        "adx_min": 20.0,  # card: Method IV ADX threshold, start 20 (Bollinger's value unverified)
        "tick": 0.01,  # card: stop = max(sma_20, low - 0.01)
        "max_stop_atr": 2.0,  # card: stop capped at 2 x atr_14 below entry
        "max_hold_days": 20,  # card
        P_MIN_TREND: TREND_UP,  # card filter: trend_state >= 1 (variant flag: run with and without)
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no target, min_reward_risk 0
    }
    features_required = ["bb_upper_20", "sma_20", "atr_14", "trend_state"]
    extra_features = [SQUEEZE_COL, PREV_UPPER, ADX_COL]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        mid = row.get("sma_20")
        return finite(mid) and float(row["close"]) < float(mid)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        out: list[Signal] = []
        for _, row in rows.iterrows():
            sq, upper, mid, atr = row[SQUEEZE_COL], row["bb_upper_20"], row["sma_20"], row["atr_14"]
            if not (self.trend_ok(row) and all(finite(x) for x in (sq, upper, mid, atr))):
                continue
            close = float(row["close"])
            if float(sq) > float(p["squeeze_pctile"]) or close <= float(upper):
                continue
            if int(p["method"]) == METHOD_IV:
                pu, pc, adx = row[PREV_UPPER], row["prior_close"], row[ADX_COL]
                if not (finite(pu) and finite(pc) and finite(adx)) or pc <= pu or adx < float(p["adx_min"]):
                    continue
            stop = max(float(mid), float(row["low"]) - float(p["tick"]), close - float(p["max_stop_atr"]) * float(atr))
            sig = self.build_signal(
                row, as_of, entry=close, stop=stop, target=None, score=float(p["squeeze_pctile"]) - float(sq),
                features={"bbw_pctile_min5": sq, "bb_upper_20": upper, "sma_20": mid, ADX_COL: row[ADX_COL],
                          "max_hold_days": p["max_hold_days"]},
                notes=f"squeeze release: close {close:.2f} > upper band {float(upper):.2f} (method {p['method']})",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
