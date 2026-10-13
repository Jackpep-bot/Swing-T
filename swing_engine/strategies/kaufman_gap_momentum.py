"""Perry Kaufman Gap Momentum System (long), docs/strategies/kaufman_gap_momentum.md (S&C Jan 2024, catalog B43).

Gap Momentum = 100 x sum(up opening gaps) / sum(down gaps) over `length` (40), signal = its SMA over `signal_length`
(20), slope = sign of the signal's one-bar change (features/extra.py `gapm_slope_<length>_<signal>`, the published
non-cumulative code). Buy when the slope turns from <= 0 to > 0 (card: a fresh rise, not every rising day); entry next
open; exit when the signal line turns down (`should_exit` on slope < 0) or after 30 sessions. Stop entry - 2 x atr_14
(engine choice, card). No target. Optional trend_state >= 0 via `min_trend_state`.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, PanelStrategy, finite

NAME = "kaufman_gap_momentum"


@register("strategy", NAME)
class KaufmanGapMomentum(PanelStrategy):
    name = NAME
    description = "Gap-momentum signal line turns up (40/20); exit when it turns down; 2 ATR stop."
    default_params: dict[str, Any] = {
        "length": 40,  # card: published default 40
        "signal_length": 20,  # card: published default 20
        "stop_atr_mult": 2.0,  # card: stop = entry - 2 x atr_14 (engine choice)
        "max_hold_days": 30,  # card: max_hold_days 30
        P_MIN_TREND: TREND_DOWN,  # card: optional trend_state >= 0 (set 0 to enable)
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: min_reward_risk 0
    }
    features_required = ["atr_14", "trend_state"]
    extra_features = ["gapm_slope_40_20", "prev_gapm_slope_40_20"]
    engine_trail = False  # exit is the signal-line turn (card)

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        self.extra_features = [self.slope_col, f"prev_{self.slope_col}"]  # panel builders read the instance's lengths

    @property
    def slope_col(self) -> str:
        return f"gapm_slope_{int(self.params['length'])}_{int(self.params['signal_length'])}"

    def required_features(self) -> list[str]:
        return [*self.features_required, self.slope_col, f"prev_{self.slope_col}"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        slope = row.get(self.slope_col)
        return bars_held >= int(self.params["max_hold_days"]) or (finite(slope) and slope < 0)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        rows = c1.rows(self, panel, as_of)
        col = self.slope_col
        keep = ((rows[col] > 0) & (rows[f"prev_{col}"] <= 0)).fillna(False)
        mult = float(self.params["stop_atr_mult"])
        out: list[Signal] = []
        for _, row in rows.loc[keep].iterrows():
            close, atr = float(row["close"]), row["atr_14"]
            if not finite(atr) or not self.trend_ok(row):
                continue
            sig = self.build_signal(row, as_of, entry=close, stop=close - mult * float(atr), target=None, score=0.0,
                                    features={"max_hold_days": self.params["max_hold_days"]},
                                    notes=f"gap momentum signal line turned up ({col})")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
