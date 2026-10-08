"""Consecutive up bars (long), docs/strategies/consecutive_bars.md (catalog B40 ConsBarsUpLE, P6 TradingView
Consecutive Up/Down).

Rule: N consecutive higher closes (TradeStation N=3, tos N=4); fires on the bar that completes the run (`up_streak`
== N) and enters at the next open. The built-ins have no stops or exits, so the card's engine spec applies: stop =
the tighter of the lowest low of the N streak bars and entry - 2 x atr_14, target 2R, 10-session time exit, optional
trend filter (off). The BarUpDn variant and the short side are not built.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, PanelStrategy, RollingSpec, finite

NAME = "consecutive_bars"


@register("strategy", NAME)
class ConsecutiveBars(PanelStrategy):
    name = NAME
    description = "N (3) consecutive higher closes; stop = tighter of streak low / 2 ATR, 2R target, 10-day exit."
    default_params: dict[str, Any] = {
        "bars": 3,  # card: N=3 (TradeStation); tos uses 4
        "stop_atr_mult": 2.0,  # card: entry - 2 x atr_14 when tighter than the streak low
        "target_r": 2.0,  # card: target = entry + 2R
        "max_hold_days": 10,  # card
        P_MIN_TREND: TREND_DOWN,  # card: trend_state == 1 is optional (set 1 to enable)
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 2.0,  # card
    }
    features_required = ["atr_14", "trend_state"]
    extra_features = ["up_streak"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        n = int(p["bars"])
        spec = RollingSpec("low", "min", n)
        rows = self.rows_as_of(panel, as_of, rolling=[spec], required=self.required_features())
        out: list[Signal] = []
        for _, row in rows.iterrows():
            streak, low_n, atr = row["up_streak"], row[spec.out], row["atr_14"]
            if not all(finite(x) for x in (streak, low_n, atr)) or int(streak) != n or not self.trend_ok(row):
                continue
            close = float(row["close"])
            stop = max(float(low_n), close - float(p["stop_atr_mult"]) * float(atr))
            sig = self.build_signal(
                row,
                as_of,
                entry=close,
                stop=stop,
                target=close + float(p["target_r"]) * (close - stop),
                score=float(row["close"]) / float(low_n) - 1.0,
                features={"up_streak": streak, "streak_low": low_n, "atr_14": atr, "max_hold_days": p["max_hold_days"]},
                notes=f"{n} consecutive higher closes; stop {stop:.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
