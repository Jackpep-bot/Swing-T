"""Slope Performance Trend (long), docs/strategies/slope_performance_trend.md (StockCharts ChartSchool, catalog P50).

State machine on two regression slopes over `lookback` sessions (12 months = 252 by default; the card's swing variants
are 63 and 20): the slope of price (`linreg_slope_252`) and the slope of the price relative to SPY
(`linreg_slope_252_of_rs_line`). Buy on the first session both are positive when the last unmixed state before it was
both negative; mixed readings keep the prior state (no signal, no exit). Exit when both turn negative. Daily
evaluation of the card's completed-monthly-bar rule (approximation; the slopes are point-in-time). No stop published:
engine catastrophic stop 2.5 x atr_14 (card). Needs the market proxy (SPY rows or a market frame) for `rs_line`.
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

NAME = "slope_performance_trend"


@register("strategy", NAME)
class SlopePerformanceTrend(PanelStrategy):
    name = NAME
    description = "Buy when the 12-month price slope and price-relative slope both turn positive; exit both negative."
    default_params: dict[str, Any] = {
        "lookback": 252,  # card: 12-month slope (13-week = 63, 20-day = 20 variants)
        "stop_atr_mult": 2.5,  # card: engine catastrophic stop 2.5 x atr_14
        "max_hold_days": 252,  # card: 252 for the 12-month version (40 for the 20-day version)
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["atr_14"]
    extra_features = ["linreg_slope_252", "linreg_slope_252_of_rs_line"]
    engine_trail = False  # state-flip exit

    def _cols(self) -> tuple[str, str]:
        n = int(self.params["lookback"])
        return f"linreg_slope_{n}", f"linreg_slope_{n}_of_rs_line"

    def required_features(self) -> list[str]:
        return [*self.features_required, *self._cols()]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        a, b = (row.get(c) for c in self._cols())
        return finite(a) and finite(b) and float(a) < 0 and float(b) < 0

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        pc, rc = self._cols()
        view = c1.view(self, panel, as_of, [pc, rc])
        mult = float(self.params["stop_atr_mult"])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            atr, a, b = row["atr_14"], row[pc], row[rc]
            if not (finite(atr) and finite(a) and finite(b)) or not (a > 0 and b > 0):
                continue
            w = view.window(str(row[SYMBOL]), [pc, rc])
            ps, rs = w[pc][:-1], w[rc][:-1]
            unmixed = np.flatnonzero(((ps > 0) & (rs > 0)) | ((ps < 0) & (rs < 0)))
            if not len(unmixed) or ps[unmixed[-1]] > 0:
                continue  # already long (or no prior both-negative state)
            close = float(row["close"])
            sig = self.build_signal(row, as_of, entry=close, stop=close - mult * float(atr), target=None, score=0.0,
                                    features={pc: a, rc: b, "max_hold_days": self.params["max_hold_days"]},
                                    notes=f"price and relative {self.params['lookback']}-bar slopes turned positive")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
