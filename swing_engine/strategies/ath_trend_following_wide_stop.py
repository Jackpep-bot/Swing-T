"""All-time-high breakout with a 10-ATR trailing stop (Wilcox-Crittenden 2005; Zarattini-Pagani-Wilcox 2025):
docs/strategies/ath_trend_following_wide_stop.md, pre-registered in docs/preregistration/2026-10-09-three-picks.md.

Buy (next open) when the close is the highest close since the symbol's first bar in the store (`ath_close`; folds in
store bars before the panel's warm-up via `data.market_series.join_pre_panel_high`, so "all-time" means since the
store start, 2016-01-04, or listing), with close >= $10 (split-adjusted store close) and at least a year of history.
Stop: ATH x (1 - 10 x ATR(42) / close), ratcheted by the engine through `trail_stop` (a resting stop, not the card's
close-below-then-next-open exit). No target and no time stop: `max_hold_days` is set far beyond any hold so neither
`run_backtest`'s 20-bar default nor the position manager cuts a 300-day position. `engine_trail = False`.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, finite

NAME = "ath_trend_following_wide_stop"
ATH, HIST = "ath_close", "hist_bars"  # features.extra


@register("strategy", NAME)
class AthTrendFollowingWideStop(PanelStrategy):
    name = NAME
    description = "Close at an all-time high; trailing stop 10 x ATR(42) below the high; no target, no time stop."
    default_params: dict[str, Any] = {
        "min_price": 10.0,  # card rule 1 (2025 version; 2005: $15)
        "min_history_bars": 252,  # pre-registration: engine choice (store start / listing day is not an ATH)
        "atr_period": 42,  # card rule 3 (ATR42)
        "stop_atr_mult": 10.0,  # card rule 3 (8-12 no material difference; register 10 only)
        "max_hold_days": 10_000,  # card rule 4: no time stop (finite so the 20-bar backtest default never applies)
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: no regime gate
        P_MIN_RR: 0.0,  # card rule 4: no target
    }
    extra_features = [ATH, HIST, "atr_42"]
    prior_columns: list[str] = []
    engine_trail = False  # the breakeven / N-day-low overlay would cut the long winners the card relies on

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        self.atr_col = f"atr_{int(self.params['atr_period'])}"
        self.extra_features = [ATH, HIST, self.atr_col]

    def _level(self, row: pd.Series) -> float | None:
        """ATH x (1 - mult x ATR / close), or None when an input is missing or the level is not positive."""
        ath, atr, close = row.get(ATH), row.get(self.atr_col), row.get("close")
        if not (finite(ath) and finite(atr) and finite(close)) or float(close) <= 0:
            return None
        level = float(ath) * (1.0 - float(self.params["stop_atr_mult"]) * float(atr) / float(close))
        return level if level > 0 else None

    def trail_stop(self, row: pd.Series) -> float | None:
        return self._level(row)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        p = self.params
        rows = c1.rows(self, panel, as_of)
        if rows.empty:
            return []
        keep = (rows["close"] >= float(p["min_price"])) & (rows[HIST] >= float(p["min_history_bars"])) & (
            rows["close"] >= rows[ATH])
        out: list[Signal] = []
        for _, row in rows.loc[keep].iterrows():
            stop, atr, close = self._level(row), row[self.atr_col], float(row["close"])
            if stop is None or not finite(atr) or float(atr) <= 0:
                continue
            sig = self.build_signal(
                row, as_of, entry=close, stop=stop, target=None, score=close / float(atr),  # 1/sigma: calm first
                features={ATH: row[ATH], HIST: row[HIST], self.atr_col: atr},
                notes=f"all-time high close {close:.2f} ({int(row[HIST])} bars of history)",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
