"""Full gap continuation bar (long): docs/strategies/full_gap_continuation_bar.md (thinkorswim GapUpLE).

Signal on day t when the whole bar sits above the prior bar (low_t > prior_high), optionally with gap_pct, rvol and
trend filters (engine choices, off or loose by default); entry the next open. Stop = prior_high (the gap fills, the
thesis is wrong); exit by time after `max_hold_days`. Neither source gives a stop, target or exit.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, TREND_FLAT, PanelStrategy, finite

NAME = "full_gap_continuation_bar"


@register("strategy", NAME)
class FullGapContinuationBar(PanelStrategy):
    name = NAME
    description = "Bar entirely above the prior bar (low > prior high); next-open entry, stop at the prior high."
    default_params: dict[str, Any] = {
        "min_gap_pct": 0.0,  # card optional filter: gap_pct >= min_gap_pct (0 = off)
        "min_rvol": 0.0,  # card optional filter: rvol_day >= min_rvol (0 = off)
        "max_hold_days": 5,  # card: 5-10 sessions
        P_MIN_TREND: TREND_FLAT,  # card optional filter: trend_state >= 0
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["gap_pct", "rvol_day", "trend_state", "atr_14"]

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        rows = self.rows_as_of(panel, as_of)
        out: list[Signal] = []
        for _, row in rows.iterrows():
            prior_high, gap, rvol = row["prior_high"], row["gap_pct"], row["rvol_day"]
            if not (self.trend_ok(row) and finite(prior_high) and finite(gap)) or float(row["low"]) <= prior_high:
                continue
            if gap < float(p["min_gap_pct"]) or (float(p["min_rvol"]) > 0 and not (finite(rvol) and rvol >= float(p["min_rvol"]))):
                continue
            close = float(row["close"])
            sig = self.build_signal(
                row, as_of, entry=close, stop=float(prior_high), target=None, score=float(gap),
                features={"prior_high": prior_high, "gap_pct": gap, "rvol_day": rvol, "max_hold_days": p["max_hold_days"]},
                notes=f"full gap: low {float(row['low']):.2f} > prior high {float(prior_high):.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
