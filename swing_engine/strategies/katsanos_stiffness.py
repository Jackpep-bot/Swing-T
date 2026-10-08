"""Katsanos Stiffness (long), docs/strategies/katsanos_stiffness.md (S&C Nov 2018, thinkorswim StiffnessStrat, B14).

Stiffness = 100 x share of the last 60 closes above SMA(100) + 0.2 x StDev(100) (`stiffness_60_100`, features.extra;
the card flags the offset sign as unverified and defaults to thinkorswim's MA + 0.2 SD). Buy when it crosses above 90
while the market index EMA rose over each of the last 2 bars (engine assumption: SPY EMA(100) =
`ema_100_of_market_close`, card). Exit when Stiffness < 50 or after 84 bars. No stop in the original; engine stop
entry - 3 x atr_14 (card). Needs the market proxy (SPY rows or a market frame) for the index filter.
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

NAME = "katsanos_stiffness"


@register("strategy", NAME)
class KatsanosStiffness(PanelStrategy):
    name = NAME
    description = "Stiffness(60, SMA100 + 0.2 SD) crosses above 90 with the index EMA rising; exit < 50 or 84 bars."
    default_params: dict[str, Any] = {
        "stiffness_col": "stiffness_60_100",  # card: length 60, MA 100, num dev 0.2
        "entry_level": 90.0,  # card: entry stiffness level 90
        "exit_level": 50.0,  # card: exit stiffness level 50
        "market_ema_col": "ema_100_of_market_close",  # card: SPY EMA(100) (length unpublished); None = no filter
        "market_rising_bars": 2,  # card: index EMA rose over the last 2 bars
        "stop_atr_mult": 3.0,  # card: engine stop entry - 3 x atr_14
        "max_hold_days": 84,  # card: exit after 84 bars
        P_MIN_MARKET_TREND: TREND_DOWN,  # the card's own index filter replaces the regime gate
        P_MIN_RR: 0.0,  # card: not applied (no target)
    }
    features_required = ["atr_14"]
    extra_features = ["stiffness_60_100", "ema_100_of_market_close"]
    engine_trail = False  # multi-month trend hold with a stiffness exit

    def required_features(self) -> list[str]:
        mkt = self.params.get("market_ema_col")
        return [*self.features_required, str(self.params["stiffness_col"]), *([str(mkt)] if mkt else [])]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        s = row.get(str(self.params["stiffness_col"]))
        return finite(s) and float(s) < float(self.params["exit_level"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        col, mkt = str(self.params["stiffness_col"]), self.params.get("market_ema_col")
        view = c1.view(self, panel, as_of, [col])
        level, k, mult = float(self.params["entry_level"]), int(self.params["market_rising_bars"]), float(self.params["stop_atr_mult"])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            atr = row["atr_14"]
            if not finite(atr):
                continue
            w = view.window(str(row[SYMBOL]), [col, *([str(mkt)] if mkt else [])])
            s = w[col][-2:]
            if len(s) < 2 or not (np.isfinite(s).all() and s[0] <= level < s[1]):
                continue
            if mkt:
                m = w[str(mkt)][-(k + 1):]
                if len(m) < k + 1 or not (np.isfinite(m).all() and (np.diff(m) > 0).all()):
                    continue
            close = float(row["close"])
            sig = self.build_signal(row, as_of, entry=close, stop=close - mult * float(atr), target=None,
                                    score=float(s[1]), features={col: s[1], "max_hold_days": self.params["max_hold_days"]},
                                    notes=f"stiffness crossed {level:g} ({float(s[1]):.0f}); exit < "
                                    f"{float(self.params['exit_level']):g}")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
