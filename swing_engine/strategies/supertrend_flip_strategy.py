"""Supertrend flip (long): docs/strategies/supertrend_flip_strategy.md (TradingView Supertrend Strategy, ATR 10 x 3).

Signal on the close where the Supertrend direction flips from -1 to +1; entry next open; initial stop = the
Supertrend line (final lower band) on the signal bar. The line is the trailing stop (`trail_stop`, ratcheted by the
engine) and a close-based flip back to -1 is the rule exit (`should_exit`). The short side (stop-and-reverse) is not
modelled (long-only engine). Target is a far reference (`target_r`); the line exits. Columns: features.extra
`st_line_10_3` / `st_dir_10_3` (Wilder ATR 10, TradingView `ta.supertrend` recursion).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, PanelStrategy, finite

NAME = "supertrend_flip_strategy"
LINE, DIR, PREV_DIR = "st_line_10_3", "st_dir_10_3", "prev_st_dir_10_3"
UP, DOWN = 1.0, -1.0


@register("strategy", NAME)
class SupertrendFlip(PanelStrategy):
    name = NAME
    description = "Supertrend(10, 3) flips up: buy next open, stop and trail on the line, exit on the flip down."
    default_params: dict[str, Any] = {
        "target_r": 5.0,  # card: reference target_r 5.0 (the rule exit is primary)
        "max_hold_days": 60,  # card
        P_MIN_TREND: TREND_DOWN,  # card: optional gate, default -1 = no gate (faithful)
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 1.0,  # card: min_reward_risk param 1.0
    }
    features_required = ["trend_state"]
    extra_features = [LINE, DIR, PREV_DIR]
    engine_trail = False  # the Supertrend line is the trail

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"]) or row.get(DIR) == DOWN

    def trail_stop(self, row: pd.Series) -> float | None:
        line = row.get(LINE)
        return float(line) if row.get(DIR) == UP and finite(line) else None

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        flips = rows.loc[(rows[DIR] == UP) & (rows[PREV_DIR] == DOWN)]
        out: list[Signal] = []
        for _, row in flips.iterrows():
            if not self.trend_ok(row):
                continue
            close, line = float(row["close"]), float(row[LINE])
            sig = self.build_signal(
                row, as_of, entry=close, stop=line,
                target=close + float(self.params["target_r"]) * (close - line),
                score=-(close - line) / close,  # tighter flips first
                features={LINE: line, DIR: row[DIR]},
                notes=f"supertrend flip up, line {line:.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
