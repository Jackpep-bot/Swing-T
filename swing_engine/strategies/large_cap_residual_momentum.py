"""Large-cap residual momentum (Blitz, Huij & Martens 2011): docs/proposals/swing-methods-2026-10/batch3/
large_cap_residual_momentum.md, pre-registered in docs/preregistration/2026-10-10-batch3.md.

`big_ff3_resid_mom_756_231` (features.extra) = `ff3_resid_mom_756_231` (FF3 fit on daily excess returns over 756 bars,
sum / std of the residuals of the last 231, both ending at the end of month t-2: BHM's t-12 .. t-2 and the French
publication lag) on the session's 500 largest names by point-in-time market cap with an as-traded close >= $10 and
>= 756 bars. Month end: buy the top 10% (rank > 0.90), sell at or below the 80th percentile or when the rank is
missing (left the 500 / the price floor). A name with no raw score on a rebalance session (French factors missing:
never the CAPM proxy) is neither bought nor sold: that rebalance is skipped. Rules and exits:
`_rank_band.MonthEndRankBand`. Book: config/prereg_b3.yaml (50 names). The replay loads `warmup_calendar_days` of
bars before its first session (the default 400 days would leave the 756-bar fit NaN for three years). Replay-only
(the share join gives `mcap_pit`).
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from swing_engine.core.registry import register

from ._base import finite
from ._rank_band import ATR, MONTH_END, MonthEndRankBand

NAME = "large_cap_residual_momentum"
RAW = "ff3_resid_mom_756_231"  # card: fit over 756 bars, residuals of the last 231; also the 756-bar history floor
WARMUP_CALENDAR_DAYS = 1200  # 757 bars (~1,100 days) + the two-month French lag, with a margin


@register("strategy", NAME)
class LargeCapResidualMomentum(MonthEndRankBand):
    name = NAME
    description = "Month end: buy the top 10% of the 500 largest stocks by FF3 residual momentum; hold the top 20%."
    SCORE, RANK = f"big_{RAW}", f"big_{RAW}_rank"
    default_params: dict[str, Any] = {
        "buy_rank_min": 0.90,  # card: buy zone = top 10% of the score
        "hold_rank_min": 0.80,  # card: hold zone = top 20%
        **MonthEndRankBand.BAND_PARAMS,
    }
    extra_features = [RAW, SCORE, RANK, MONTH_END, ATR]
    warmup_calendar_days = WARMUP_CALENDAR_DAYS

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return finite(row.get(RAW)) and super().should_exit(row, bars_held)  # no raw score: rebalance skipped
