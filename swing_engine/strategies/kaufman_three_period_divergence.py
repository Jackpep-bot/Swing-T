"""Kaufman Three Period Divergence (long), docs/strategies/kaufman_three_period_divergence.md (catalog B41, tos).

Linear-regression slopes of close and of the 14-bar stochastic FastK over three lookbacks (5 / 10 / 15, card's
pre-registered set). `variant: tos` buys when price slopes up while momentum slopes down on >= `entry_number` periods
(thinkorswim's coded direction, a trend-continuation entry); `variant: textbook` buys the opposite (price down,
momentum up). Signal only on the first bar the count is reached. Exit when all three price/momentum slope pairs agree
in sign (`should_exit`), or after 20 sessions. No stop in the original: engine stop 2 x atr_14 (card).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "kaufman_three_period_divergence"
TOS, TEXTBOOK = "tos", "textbook"


@register("strategy", NAME)
class KaufmanThreePeriodDivergence(PanelStrategy):
    name = NAME
    description = "Price vs stochastic regression-slope divergence on 3 lookbacks; exit when all slopes agree."
    default_params: dict[str, Any] = {
        "variant": TOS,  # card: tos "bearish divergence buy" (A) vs textbook bullish (B), two trials
        "momentum": "stoch_k_14",  # card: FastK, momentum length 14
        "periods": [5, 10, 15],  # card: pre-registered lookbacks 5 / 10 / 15
        "entry_number": 3,  # card: divergence on all 3 periods
        "stop_atr_mult": 2.0,  # card engine choice
        "max_hold_days": 20,  # card
        P_MIN_TREND: TREND_DOWN,  # card: trend_state >= 0 gate optional (off)
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["atr_14", "trend_state"]
    extra_features = [f"linreg_slope_{n}{s}" for n in (5, 10, 15) for s in ("", "_of_stoch_k_14")]

    def _pairs(self) -> list[tuple[str, str]]:
        mom = str(self.params["momentum"])
        return [(f"linreg_slope_{int(n)}", f"linreg_slope_{int(n)}_of_{mom}") for n in self.params["periods"]]

    def required_features(self) -> list[str]:
        return [*self.features_required, *(c for pair in self._pairs() for c in pair)]

    def _count(self, price: float, mom: float) -> int:
        if str(self.params["variant"]) == TEXTBOOK:
            return int(price < 0 < mom)
        return int(price > 0 > mom)

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        vals = [(row.get(p), row.get(m)) for p, m in self._pairs()]
        return all(finite(p) and finite(m) for p, m in vals) and all(
            np.sign(float(p)) == np.sign(float(m)) for p, m in vals)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        pairs = self._pairs()
        cols = [c for pair in pairs for c in pair]
        view = c1.view(self, panel, as_of, cols)
        need, mult = int(self.params["entry_number"]), float(self.params["stop_atr_mult"])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            atr = row["atr_14"]
            if not finite(atr) or not self.trend_ok(row):
                continue
            w = view.window(str(row[SYMBOL]), cols)
            if len(w[cols[0]]) < 2 or not all(np.isfinite(w[c][-2:]).all() for c in cols):
                continue
            now = sum(self._count(w[p][-1], w[m][-1]) for p, m in pairs)
            before = sum(self._count(w[p][-2], w[m][-2]) for p, m in pairs)
            if now < need or before >= need:
                continue
            close = float(row["close"])
            sig = self.build_signal(row, as_of, entry=close, stop=close - mult * float(atr), target=None,
                                    score=float(now), features={"divergences": now,
                                                                "max_hold_days": self.params["max_hold_days"]},
                                    notes=f"{self.params['variant']} divergence on {now}/{len(pairs)} periods")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
