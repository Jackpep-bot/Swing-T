"""Connors %b (long), docs/strategies/connors_pctb.md (catalog C6, High Probability ETF Trading ch. 5).

Close above the 200-day SMA and Bollinger %b below 0.2 on each of the last 3 closes; exit when %b closes above 0.8.
The card leaves the band unconfirmed: `pctb_col` bb_pctb_20 (20, 2) by default, `bb_pctb_5` as the pre-registered
short-band trial. Connors buys the close; the engine fills the next open (no MOC). No stop in the original
("stops hurt"); the engine needs one for sizing, so a catastrophic 2 x atr_14 stop (card). Same family as
rsi2_meanrev, but the 3-close %b entry is not an RSI-2 parameter change, so this is its own module.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "connors_pctb"


@register("strategy", NAME)
class ConnorsPctB(PanelStrategy):
    name = NAME
    description = "close > sma_200 and %b < 0.2 for 3 closes; exit %b > 0.8; 2 ATR catastrophic stop."
    default_params: dict[str, Any] = {
        "pctb_col": "bb_pctb_20",  # card: band 20/2 (trial 2: "bb_pctb_5")
        "entry_max": 0.2,  # card: %b < 0.2 ...
        "entry_days": 3,  # card: ... on 3 consecutive closes
        "exit_min": 0.8,  # card: exit when %b closes > 0.8
        "trend_ma": "sma_200",  # card: close > 200-day SMA
        "stop_atr_mult": 2.0,  # card: catastrophic entry - 2 x atr_14
        "max_hold_days": 10,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,  # gates on the instrument's own 200-day
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["atr_14"]
    extra_features = ["bb_pctb_20"]

    def required_features(self) -> list[str]:
        return [*self.features_required, str(self.params["pctb_col"]), str(self.params["trend_ma"])]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        pb = row.get(str(self.params["pctb_col"]))
        return finite(pb) and float(pb) > float(self.params["exit_min"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        col, ma = str(self.params["pctb_col"]), str(self.params["trend_ma"])
        view = c1.view(self, panel, as_of, [col])
        days, mult = int(self.params["entry_days"]), float(self.params["stop_atr_mult"])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            atr, trend = row["atr_14"], row[ma]
            close = float(row["close"])
            if not (finite(atr) and finite(trend)) or close <= float(trend):
                continue
            pb = view.window(str(row[SYMBOL]), [col])[col][-days:]
            if len(pb) < days or not (np.isfinite(pb).all() and (pb < float(self.params["entry_max"])).all()):
                continue
            sig = self.build_signal(row, as_of, entry=close, stop=close - mult * float(atr), target=None,
                                    score=float(self.params["entry_max"]) - float(pb.mean()),
                                    features={col: pb[-1], "max_hold_days": self.params["max_hold_days"]},
                                    notes=f"%b < {float(self.params['entry_max']):g} for {days} closes above {ma}; "
                                    f"exit %b > {float(self.params['exit_min']):g}")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
