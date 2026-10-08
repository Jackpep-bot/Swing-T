"""Revenue surprise (Jegadeesh-Livnat 2006, catalog E25), docs/strategies/revenue_surprise.md replay variant.

On the last session of each month (`month_end`, features/extra.py) the scanned symbols are sorted on the latest
standardized revenue surprise; the top decile with a positive earnings surprise (`sue > 0`, card) is bought at the next open (the first
session of the month) and held `max_hold_days` (21). Stop entry - 3 x atr_14, no target (card). Long only.

Data: the OPTIONAL panel columns `rev_surprise` and `sue` (data/fundamentals.py edgar_panel_features: seasonal
random-walk surprise over the prior 8 quarters, visible the session after the 10-Q/10-K filing). Without
`rev_surprise` the strategy returns no signals; `min_sue` is skipped when `sue` is absent or the param is None.
Approximation: edgar_panel_features scales total revenue, not revenue per share (the paper's Rs).
No engine panel builder joins edgar_panel_features yet, so replay, nightly and the CLI produce no revenue_surprise
signals.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, PanelStrategy, finite

NAME = "revenue_surprise"
RS_COL = "rev_surprise"
SUE_COL = "sue"


@register("strategy", NAME)
class RevenueSurprise(PanelStrategy):
    name = NAME
    description = "Month-end top decile of the standardized revenue surprise (with sue > 0); 3 ATR stop, 21-day hold."
    default_params: dict[str, Any] = {
        "top_fraction": 0.10,  # card: long the top decile
        "min_sue": 0.0,  # card replay variant: top decile with sue_ts > 0 (None = off)
        "stop_atr_mult": 3.0,  # card: stop entry - 3 * atr_14
        "max_hold_days": 21,  # card: max_hold_days 21
        P_MIN_TREND: TREND_DOWN,
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: min_reward_risk 0.0
    }
    features_required = ["atr_14", "trend_state"]
    extra_features = ["month_end"]
    engine_trail = False  # monthly factor hold

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or RS_COL not in panel.columns or not self.market_ok(regime):
            return []
        rows = c1.rows(self, panel, as_of)
        if rows.empty or not (rows["month_end"] == 1).any():
            return []
        keep = c1.top_fraction(rows[RS_COL].astype(float), float(self.params["top_fraction"]))
        min_sue = self.params.get("min_sue")
        if min_sue is not None and SUE_COL in rows.columns:
            keep &= rows[SUE_COL].astype(float) > float(min_sue)
        mult = float(self.params["stop_atr_mult"])
        out: list[Signal] = []
        for _, row in rows.loc[keep].iterrows():
            close, atr, rs = float(row["close"]), row["atr_14"], float(row[RS_COL])
            if not finite(atr) or not self.trend_ok(row):
                continue
            sig = self.build_signal(row, as_of, entry=close, stop=close - mult * float(atr), target=None, score=rs,
                                    features={RS_COL: rs, SUE_COL: row.get(SUE_COL),
                                              "max_hold_days": self.params["max_hold_days"]},
                                    notes=f"revenue surprise {rs:.2f} in the top decile at month end")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
