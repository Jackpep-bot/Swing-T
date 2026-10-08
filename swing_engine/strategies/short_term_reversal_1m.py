"""Short-term (1-month) reversal, long loser leg inside momentum names: docs/strategies/short_term_reversal_1m.md.

Card spec (engine-adapted, long-only): weekly on Friday's close, screen the top `universe_top_n` names by
dollar_vol_20d whose mom_12_1 is in the top 30% of that screen and trend_state >= 0; buy those whose rev_21d (minus
the 21-bar return) ranks in the top 10% of the screen, skipping names with a |gap| >= 5% in the last 21 bars (news
proxy). Next-open entry, catastrophe stop 2.5 x atr_14, time exit. The low-turnover split (shares outstanding) and
earnings exclusion need data the engine lacks and are omitted. A holiday Friday skips that week.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_FLAT, PanelStrategy, finite

NAME = "short_term_reversal_1m"
GAP_MAX, GAP_MIN, DOW = "max_21_of_gap_pct", "min_21_of_gap_pct", "day_of_week"


@register("strategy", NAME)
class ShortTermReversal1M(PanelStrategy):
    name = NAME
    description = "Friday: biggest 1-month losers (rev_21d top 10%) among liquid momentum names; 5-day hold."
    default_params: dict[str, Any] = {
        "rebalance_weekday": 4,  # card: weekly, Friday close (Monday = 0)
        "universe_top_n": 500,  # card: top 500 by dollar_vol_20d
        "mom_rank_min": 0.70,  # card: mom_12_1 in the top 30% cross-sectionally
        "rev_rank_min": 0.90,  # card: rank_pct(rev_21d) >= 0.9 within the screen
        "max_abs_gap": 0.05,  # card: exclude abs(gap_pct) >= 0.05 on any of the last 21 bars
        "min_cross_section": 10,  # engine choice: percentiles need at least 10 names
        "stop_atr_mult": 2.5,  # card: catastrophe stop entry - 2.5 x atr_14
        "max_hold_days": 5,  # card: 5 (weekly variant); run 21 as the monthly variant
        P_MIN_TREND: TREND_FLAT,  # card: trend_state >= 0
        P_MIN_MARKET_TREND: TREND_FLAT,  # card router note: block in correction
        P_MIN_RR: 0.0,  # card: time exit, min_reward_risk 0
    }
    features_required = ["rev_21d", "mom_12_1", "dollar_vol_20d", "trend_state", "atr_14"]
    extra_features = [GAP_MAX, GAP_MIN, DOW]

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        if rows.empty or rows[DOW].iloc[0] != int(p["rebalance_weekday"]):
            return []
        rows = rows.dropna(subset=["rev_21d", "mom_12_1", "dollar_vol_20d"])
        screen = rows.nlargest(int(p["universe_top_n"]), "dollar_vol_20d")
        screen = screen.loc[screen["mom_12_1"].rank(pct=True) >= float(p["mom_rank_min"])]
        if len(screen) < int(p["min_cross_section"]):
            return []
        rank = screen["rev_21d"].rank(pct=True)
        out: list[Signal] = []
        for idx, row in screen.loc[rank >= float(p["rev_rank_min"])].iterrows():
            atr, gmax, gmin = row["atr_14"], row[GAP_MAX], row[GAP_MIN]
            if not (self.trend_ok(row) and finite(atr) and finite(gmax) and finite(gmin)):
                continue
            if max(abs(float(gmax)), abs(float(gmin))) >= float(p["max_abs_gap"]):
                continue
            close = float(row["close"])
            sig = self.build_signal(
                row, as_of, entry=close, stop=close - float(p["stop_atr_mult"]) * float(atr), target=None,
                score=float(rank[idx]),
                features={"rev_21d": row["rev_21d"], "rev_rank": rank[idx], "mom_12_1": row["mom_12_1"],
                          "atr_14": atr, "max_hold_days": p["max_hold_days"]},
                notes=f"1-month loser {float(row['rev_21d']) * -100:.1f}% (rank {rank[idx]:.2f}) in a momentum name",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
