"""Connors 3-Day High/Low (long), docs/strategies/connors_3day_high_low.md (catalog C7, High Probability ETF Trading,
strategy 1); rsi2_meanrev family.

Rule: close > sma_200, close < sma_5, and three consecutive lower highs AND lower lows (high[t] < high[t-1] <
high[t-2] < high[t-3], same for lows). Exit on the first close above sma_5. The original buys at the signal close;
the engine has no market-on-close entry, so it fills at the next open (known handicap). The original has no stop:
the engine adds a catastrophic entry - 2 x atr_14 and a 6-session time stop. The scale-in "aggressive version" is
not modelled. Universe: Connors trades liquid index / sector ETFs; set `symbols` to that list (None = every symbol).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "connors_3day_high_low"


@register("strategy", NAME)
class Connors3DayHighLow(PanelStrategy):
    name = NAME
    description = "close > sma_200, close < sma_5, 3 lower highs and lows; exit close > sma_5; 2 ATR stop."
    default_params: dict[str, Any] = {
        "down_days": 3,  # card: three consecutive lower highs and lower lows (keep 3, do not sweep)
        "trend_ma": "sma_200",  # card: close above the 200-day SMA
        "exit_ma": "sma_5",  # card: exit on the first close above the 5-day SMA (also the reference target)
        "stop_atr_mult": 2.0,  # card: catastrophic stop (not in the source)
        "max_hold_days": 6,  # card implementation spec
        "symbols": None,  # card: index / sector ETFs only (config list); None = all
        P_MIN_MARKET_TREND: TREND_DOWN,  # Connors gates on the instrument's own 200-day
        P_MIN_RR: 0.0,  # card: rule exit
    }
    features_required = ["atr_14", "sma_200"]
    extra_features = ["sma_5"]

    def required_features(self) -> list[str]:
        cols = [*super().required_features(), str(self.params["trend_ma"]), str(self.params["exit_ma"])]
        return list(dict.fromkeys(cols))

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        ma = row.get(str(self.params["exit_ma"]))
        return finite(ma) and float(row["close"]) > float(ma)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        n = int(p["down_days"])
        trend_col, exit_col = str(p["trend_ma"]), str(p["exit_ma"])
        allowed = set(p["symbols"]) if p.get("symbols") else None
        view = as_of_view(panel, as_of, ["high", "low", "close", *self.required_features()])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            if allowed is not None and row[SYMBOL] not in allowed:
                continue
            trend_ma, exit_ma, atr = row[trend_col], row[exit_col], row["atr_14"]
            if not all(finite(x) for x in (trend_ma, exit_ma, atr)):
                continue
            close = float(row["close"])
            if not float(trend_ma) < close < float(exit_ma):
                continue
            w = view.window(str(row[SYMBOL]), ("high", "low"))
            if len(w["high"]) < n + 1:
                continue
            hs, ls = w["high"][-(n + 1) :], w["low"][-(n + 1) :]
            if not ((np.diff(hs) < 0).all() and (np.diff(ls) < 0).all()):
                continue
            sig = self.build_signal(
                row,
                as_of,
                entry=close,
                stop=close - float(p["stop_atr_mult"]) * float(atr),
                target=float(exit_ma),
                score=(float(exit_ma) - close) / float(atr) if float(atr) > 0 else 0.0,
                features={trend_col: trend_ma, exit_col: exit_ma, "atr_14": atr, "max_hold_days": p["max_hold_days"]},
                notes=f"{n} lower highs and lows above {trend_col}, below {exit_col}; exit close > {exit_col}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
