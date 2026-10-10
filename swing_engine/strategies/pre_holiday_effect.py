"""Pre-holiday effect (long), docs/strategies/pre_holiday_effect.md (Almanac 1-2 day version, catalog P47/C58/E34).

Signal at the close of the session two before an NYSE holiday (`pre_holiday_2`, features/extra.py calendar flag),
entry at the next open (the pre-holiday session), exit at the close of the first session after the holiday
(`max_hold_days` 2 = entry session + the post-holiday session). Catastrophic stop 3 x atr_14 (card). No target.

Approximations: the card's academic version enters at the pre-holiday close (needs a MOC fill the engine lacks), so
this is the Almanac "buy 1-2 days before" form; the card's small-cap basket has no market-cap column here, so the
universe is whatever the engine scans (the effect is reported only in small caps, Ko-Yang 2021).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, PanelStrategy, finite

NAME = "pre_holiday_effect"
FLAG = "pre_holiday_2"


@register("strategy", NAME)
class PreHolidayEffect(PanelStrategy):
    name = NAME
    description = "Buy the open of the session before an NYSE holiday, sell the close after it; 3 ATR catastrophic stop."
    default_params: dict[str, Any] = {
        "stop_atr_mult": 3.0,  # card: catastrophic stop 3 * atr_14
        "max_hold_days": 2,  # card: sell just after the holiday (pre-holiday session + first post-holiday session)
        P_MIN_TREND: TREND_DOWN,  # card: no trend filter
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # no target
    }
    features_required = ["atr_14", "trend_state"]
    extra_features = [FLAG]
    engine_trail = False  # two-session calendar hold; the card has no trail

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        rows = c1.rows(self, panel, as_of)
        mult = float(self.params["stop_atr_mult"])
        out: list[Signal] = []
        for _, row in rows.loc[rows[FLAG] == 1].iterrows():
            atr, close = row["atr_14"], float(row["close"])
            if not finite(atr) or not self.trend_ok(row):
                continue
            sig = self.build_signal(row, as_of, entry=close, stop=close - mult * float(atr), target=None, score=0.0,
                                    features={"max_hold_days": self.params["max_hold_days"]},
                                    notes="pre-holiday: next session precedes an NYSE holiday")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
