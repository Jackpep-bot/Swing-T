"""Volatility Expansion Close (long), docs/strategies/volatility_expansion_close.md (TradeStation Volty Expan Close LE/LX).

Every close t arms a buy stop for the next session at close_t + 0.75 x ATR(5), with ATR(5) the simple 5-bar mean of
true range (TradeStation AvgTrueRange: `atr_sma_5`). Initial stop and trailing exit = close - 1.5 x ATR(5),
recomputed each close and only ratcheted up (`trail_stop`; LX). No target; 20-session time stop (card). The engine
expires an untriggered stop after one session, matching "valid one session". Short side (SE) not used; the Open
variant needs a stop-off-the-open hook and is not coded.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, PanelStrategy, finite

NAME = "volatility_expansion_close"
ATR5 = "atr_sma_5"


@register("strategy", NAME)
class VolatilityExpansionClose(PanelStrategy):
    name = NAME
    description = "Buy stop at close + 0.75 x ATR(5); trailing stop close - 1.5 x ATR(5); 20-day time stop."
    default_params: dict[str, Any] = {
        "entry_atr_mult": 0.75,  # card: buy stop next bar at close + 0.75 x ATR(5)
        "exit_atr_mult": 1.5,  # card: LX stop at close - 1.5 x ATR(5), recomputed each bar
        "max_hold_days": 20,  # card: max_hold_days 20
        P_MIN_TREND: TREND_DOWN,  # card: no filters
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["trend_state"]
    extra_features = [ATR5]
    engine_trail = False  # LX is the strategy's own close-based trail

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def trail_stop(self, row: pd.Series) -> float | None:
        atr = row.get(ATR5)
        return float(row["close"]) - float(self.params["exit_atr_mult"]) * float(atr) if finite(atr) else None

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        rows = c1.rows(self, panel, as_of)
        out: list[Signal] = []
        for _, row in rows.iterrows():
            close, atr = float(row["close"]), row[ATR5]
            if not finite(atr) or float(atr) <= 0 or not self.trend_ok(row):
                continue
            entry = close + float(p["entry_atr_mult"]) * float(atr)
            sig = self.build_signal(row, as_of, entry=entry, stop=close - float(p["exit_atr_mult"]) * float(atr),
                                    target=None, score=0.0,
                                    features={ATR5: atr, "max_hold_days": p["max_hold_days"]},
                                    notes=f"volatility expansion: buy stop {entry:.2f} = close + "
                                    f"{p['entry_atr_mult']} x ATR5 {float(atr):.2f}")
            sig = c1.stop_entry(sig)
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
