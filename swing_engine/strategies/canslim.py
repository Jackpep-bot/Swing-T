"""CAN SLIM (O'Neil / IBD), docs/strategies/canslim.md: a thin `base_breakout` variant (catalog maps_to: the chart side).

N/S/L/M come from base_breakout: a cup-with-handle or flat-base pivot breakout within 5% (N), on >= 1.4x volume (S),
63-day RS percentile >= 0.80 (L), market gate min_market_trend_state = 1 (M, approximating the Market School
confirmed uptrend); stop 7-8% (O'Neil), target +20-25%, 40-session cap. Stop 0.08 / target 0.25 / vol 1.5 are the
card's upper-end CAN SLIM values, base_breakout keeps the lower ones.

Approximation of C: the engine has no quarterly EPS growth, 3-year EPS CAGR, ROE (A) or 13F holders (I). The closest
point-in-time input is the OPTIONAL panel column `sue` (data/fundamentals.py edgar_panel_features: standardized
quarterly EPS surprise vs the same quarter a year earlier); signals require sue >= `min_sue`. Without the column the
strategy returns no signals (`require_fundamentals`; False degrades it to base_breakout with these params).
Replay, nightly and the CLI join these columns from the store (data.fundamentals.join_edgar) after
`swing ingest-edgar`.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_RR, SYMBOL, finite
from .base_breakout import BaseBreakout

NAME = "canslim"
SUE_COL = "sue"


@register("strategy", NAME)
class Canslim(BaseBreakout):
    name = NAME
    description = "base_breakout (RS >= 80, M gate) plus a positive EPS surprise (sue) as the C proxy; 8% stop, +25%."
    default_params: dict[str, Any] = {
        **BaseBreakout.default_params,
        "breakout_vol_mult": 1.5,  # card: buy at the pivot on 40-50%+ volume (vol_mult 1.4-1.5)
        "rs_rank_min": 0.80,  # card: L, RS rating >= 80
        "stop_pct": 0.08,  # card: sell at a 7-8% loss
        "target_pct": 0.25,  # card: take 20-25%
        "min_sue": 0.0,  # C proxy: latest standardized EPS surprise above zero (no EPS-growth column exists)
        "require_fundamentals": True,  # no `sue` column -> no signals (C cannot be checked)
        P_MIN_RR: 2.5,  # card: minimum R:R about 2.5 (20/8)
    }

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        has_sue = SUE_COL in panel.columns
        if not has_sue and bool(self.params["require_fundamentals"]):
            return []
        sigs = super().signals(panel, as_of, regime)
        if not has_sue or not sigs:
            return sigs
        sue = self.rows_as_of(panel, as_of, required=[SUE_COL]).set_index(SYMBOL)[SUE_COL]
        floor = float(self.params["min_sue"])
        out = []
        for s in sigs:
            val = sue.get(s.symbol)
            if finite(val) and float(val) >= floor:
                out.append(s.model_copy(update={"features": {**s.features, SUE_COL: float(val)}}))
        return out
