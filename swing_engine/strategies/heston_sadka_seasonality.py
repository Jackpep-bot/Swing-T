"""Heston-Sadka same-calendar-month seasonality (long top decile): docs/strategies/heston_sadka_seasonality.md.

Score = `seas_month_1_5` (features.extra): the stock's mean return in the current calendar month over the previous
1-5 years, needing >= 3 of them (the store holds ~10.75 years, so years 11-20 are out of reach). The card's standalone
replay: on the month's first session (`tom_day == 1`) buy the top decile of the same-session cross-section with
trend_state >= 0, stop 2 x atr_14, no target, hold about one month. Approximation: the paper rebalances at the month
end; here the signal is the first session's close and the fill the next open (one session late). Long leg only.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_FLAT, PanelStrategy, finite

NAME = "heston_sadka_seasonality"
SEAS_COL = "seas_month_1_5"
TOM_COL = "tom_day"
FIRST_SESSION = 1


@register("strategy", NAME)
class HestonSadkaSeasonality(PanelStrategy):
    name = NAME
    description = "Month's first session: buy the top decile of same-calendar-month returns over the prior 1-5 years."
    default_params: dict[str, Any] = {
        "top_pct": 0.10,  # card: decile sort, long the top decile
        "min_cross_section": 10,  # engine choice: a decile needs at least 10 ranked names
        "stop_atr_mult": 2.0,  # card replay spec: stop 2 x atr_14
        "max_hold_days": 21,  # card: hold one month (~21 sessions)
        P_MIN_TREND: TREND_FLAT,  # card replay spec: trend_state >= 0
        P_MIN_MARKET_TREND: TREND_FLAT,  # card router note: never opens trades in a correction on its own
        P_MIN_RR: 0.0,  # card: time exit, min_reward_risk 0
    }
    features_required = ["atr_14", "trend_state"]
    extra_features = [SEAS_COL, TOM_COL]

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        rows = rows.loc[(rows[TOM_COL] == FIRST_SESSION) & rows[SEAS_COL].notna()]
        if len(rows) < int(self.params["min_cross_section"]):
            return []
        rank = rows[SEAS_COL].rank(pct=True)
        out: list[Signal] = []
        for idx, row in rows.loc[rank > 1.0 - float(self.params["top_pct"])].iterrows():
            atr = row["atr_14"]
            if not self.trend_ok(row) or not finite(atr):
                continue
            close = float(row["close"])
            sig = self.build_signal(
                row, as_of, entry=close, stop=close - float(self.params["stop_atr_mult"]) * float(atr), target=None,
                score=float(row[SEAS_COL]),
                features={SEAS_COL: row[SEAS_COL], "seas_rank": rank[idx], "atr_14": atr,
                          "max_hold_days": self.params["max_hold_days"]},
                notes=f"same-month mean return {float(row[SEAS_COL]) * 100:.1f}% (rank {rank[idx]:.2f})",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
