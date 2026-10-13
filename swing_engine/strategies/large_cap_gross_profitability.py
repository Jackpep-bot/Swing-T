"""Large-cap gross profitability (Novy-Marx 2013): docs/proposals/swing-methods-2026-10/batch3/
large_cap_gross_profitability.md, pre-registered in docs/preregistration/2026-10-10-batch3.md.

`big_gross_prof` (features.extra) = TTM gross profit / latest total assets (`gross_prof`, data.fundamentals.join_edgar,
usable from the session after the filing) on the session's 500 largest names by point-in-time market cap; names
without a gross profit (the card's stand-in for financials) drop out. Month end: buy the top third (rank > 2/3),
sell at or below the median (rank <= 0.5) or when the rank is missing (left the 500 or lost its gross profit).
Rules and exits: `_rank_band.MonthEndRankBand`. Book: config/prereg_b3_gp.yaml (60 names). Replay-only: the CLI scan
and nightly do not run the share join (`mcap_pit`), so the rank is NaN there and the strategy is silent.
"""
from __future__ import annotations

from typing import Any

from swing_engine.core.registry import register

from ._rank_band import ATR, MONTH_END, MonthEndRankBand

NAME = "large_cap_gross_profitability"


@register("strategy", NAME)
class LargeCapGrossProfitability(MonthEndRankBand):
    name = NAME
    description = "Month end: buy the top third of the 500 largest stocks by gross profit / assets; hold the top half."
    SCORE, RANK = "big_gross_prof", "big_gross_prof_rank"
    default_params: dict[str, Any] = {
        "buy_rank_min": 2.0 / 3.0,  # card: buy zone = top third of GP/A
        "hold_rank_min": 0.5,  # card: hold zone = top half
        **MonthEndRankBand.BAND_PARAMS,
    }
    extra_features = [SCORE, RANK, MONTH_END, ATR]
