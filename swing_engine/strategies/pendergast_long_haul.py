"""Donald Pendergast Long Haul (long), docs/strategies/pendergast_long_haul.md (thinkorswim LongHaul, catalog B12).

Setup: RSI(14) fell below `rsi_oversold` within the last `oversold_lookback` bars and has not risen above
`rsi_overbought` since. Entry at the close that is above the highest high of the prior `high_length` bars and above
the slow MA; filled next open. Stop = lowest low of the last 3 bars (entry - 1.5 x atr_14 if that is not below the
close); the same 3-bar low is the trailing stop (`trail_stop`); `should_exit` on a close below the fast MA or after
40 sessions. TOS publishes no defaults: RSI 30/70, high length 5, SMA(10)/SMA(50) are the card's engine assumptions.
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

NAME = "pendergast_long_haul"
LOW3 = "low_3"  # features.extra: lowest low of the last 3 bars including this one


@register("strategy", NAME)
class PendergastLongHaul(PanelStrategy):
    name = NAME
    description = "RSI(14) dipped < 30 without reaching 70; buy the close over the 5-bar high and SMA50; 3-bar-low trail."
    default_params: dict[str, Any] = {
        "rsi_oversold": 30.0,  # card engine assumption: RSI(14) oversold 30 ...
        "rsi_overbought": 70.0,  # ... overbought 70
        "oversold_lookback": 30,  # card: bars_since(rsi_14 < 30) <= 30
        "high_length": 5,  # card: close > prior_max_high_5
        "fast_ma": "sma_10",  # card: exit close < sma_10
        "slow_ma": "sma_50",  # card: close > sma_50
        "fallback_stop_atr": 1.5,  # card: else entry - 1.5 x atr_14
        "max_hold_days": 40,  # card: max_hold_days 40
        P_MIN_TREND: TREND_DOWN,
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["atr_14", "rsi_14", "trend_state"]
    extra_features = [LOW3]
    engine_trail = False  # the 3-bar-low trail is the strategy's own (card)

    def required_features(self) -> list[str]:
        return [*self.features_required, str(self.params["fast_ma"]), str(self.params["slow_ma"]), LOW3]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        ma = row.get(str(self.params["fast_ma"]))
        return bars_held >= int(self.params["max_hold_days"]) or (finite(ma) and float(row["close"]) < float(ma))

    def trail_stop(self, row: pd.Series) -> float | None:
        low3 = row.get(LOW3)
        return float(low3) if finite(low3) else None

    def setup_ok(self, rsi: np.ndarray) -> bool:
        p = self.params
        recent = rsi[-int(p["oversold_lookback"]) - 1 :]
        hits = np.flatnonzero(recent < float(p["rsi_oversold"]))
        return len(hits) > 0 and bool(np.nanmax(recent[hits[-1] :]) < float(p["rsi_overbought"]))

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        p = self.params
        v = c1.view(self, panel, as_of, [])
        cur, n = v.current, int(p["high_length"])
        keep = (cur["close"] > cur[str(p["slow_ma"])]).fillna(False)
        out: list[Signal] = []
        for _, row in cur.loc[keep].iterrows():
            if not self.trend_ok(row):
                continue
            w = v.window(str(row[SYMBOL]), ["high", "rsi_14"])
            if len(w["high"]) <= n or not row["close"] > np.max(w["high"][-n - 1 : -1]) or not self.setup_ok(w["rsi_14"]):
                continue
            close, low3, atr = float(row["close"]), row[LOW3], row["atr_14"]
            stop = float(low3) if finite(low3) and low3 < close else close - float(p["fallback_stop_atr"]) * float(atr)
            sig = self.build_signal(row, as_of, entry=close, stop=stop, target=None, score=-float(row["rsi_14"]),
                                    features={"rsi_14": row["rsi_14"], "max_hold_days": p["max_hold_days"]},
                                    notes=f"Long Haul: RSI dipped < {p['rsi_oversold']:.0f} without reaching "
                                    f"{p['rsi_overbought']:.0f}; close {close:.2f} over the {n}-bar high")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(cur), len(out))
        return out
