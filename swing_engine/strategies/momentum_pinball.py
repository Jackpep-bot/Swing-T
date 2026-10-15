"""Momentum Pinball (long), docs/strategies/momentum_pinball.md (Raschke & Connors, Street Smarts 1995, catalog C3).

Signal: LBR/RSI = RSI(3) of the 1-day change (`lbr_rsi_3`, features.extra) closes below 30, on names with a good
daily range (atr_pct_14 >= 2%, card). DAILY APPROXIMATION (labelled `approx_daily`, card): the method's buy stop over
the next day's FIRST-HOUR high, with the stop at the first-hour low, needs 60-minute bars the store does not hold; here
the buy stop sits at the signal-day high (EntryType.STOP, next session only) and the stop at its low. This changes the
method. Exit: at the close if losing (close below the entry fill, `exit_if_losing`, card), else never a second
night (`max_hold_days` 2).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import PositionContext, Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, entry_price

NAME = "momentum_pinball"
LBR = "lbr_rsi_3"


@register("strategy", NAME)
class MomentumPinball(PanelStrategy):
    name = NAME
    description = "LBR/RSI(3) < 30: buy stop over the day's high next session (daily approx of the first-hour break)."
    default_params: dict[str, Any] = {
        "lbr_max": 30.0,  # card: LBR/RSI closes below 30
        "min_atr_pct": 0.02,  # card: "good average daily range" -> atr_pct_14 >= 0.02
        "max_hold_days": 2,  # card: exit next day, never hold a second night
        "exit_if_losing": True,  # card: "if losing at the close, exit"
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["atr_pct_14"]
    extra_features = [LBR]
    engine_trail = False  # two-session trade

    def should_exit(self, row: pd.Series, bars_held: int, position: PositionContext | None = None) -> bool:
        fill = entry_price(position)
        return bool(self.params["exit_if_losing"]) and fill is not None and float(row["close"]) < fill

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        rows = c1.rows(self, panel, as_of)
        rows = rows.loc[(rows[LBR] < float(self.params["lbr_max"]))
                        & (rows["atr_pct_14"] >= float(self.params["min_atr_pct"]))]
        out: list[Signal] = []
        for _, row in rows.iterrows():
            high, low = float(row["high"]), float(row["low"])
            sig = self.build_signal(row, as_of, entry=high, stop=low, target=None,
                                    score=float(self.params["lbr_max"]) - float(row[LBR]),
                                    features={LBR: row[LBR], "approx_daily": 1.0,
                                              "max_hold_days": self.params["max_hold_days"]},
                                    notes=f"pinball (approx_daily): LBR/RSI {float(row[LBR]):.1f}; buy stop {high:.2f}")
            sig = c1.stop_entry(sig)
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
