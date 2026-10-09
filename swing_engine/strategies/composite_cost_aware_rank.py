"""Cost-aware composite rank with a 10%/20% buy/hold band (Novy-Marx-Velikov 2016; DeMiguel et al. 2020):
docs/strategies/composite_cost_aware_rank.md, pre-registered in docs/preregistration/2026-10-09-three-picks.md.

`ccr_score` (features.extra) = equal-weight mean of same-session percentiles of 12-1 momentum, gross profitability
(EDGAR), 52-week-high proximity and low 252-day volatility, among names with close >= $5, 63-day median dollar volume
>= $20M and market cap above the session's 20th percentile; `ccr_score_rank` is its same-session percentile (the
replay re-ranks it among its point-in-time universe). On the last NYSE session of each month: buy rank > 0.90 (next
open = first session of the month); a held name is sold at the next open when its rank is <= 0.80 or missing. That
is `risk.selection.rank_hysteresis(ranked, held, 0.10, 0.20)` split into the entry rule and `should_exit`, because a
strategy has no held set (equivalence tested in tests/test_strategy_three_picks.py). Catastrophe stop 3 x ATR(63)
(card rule 5; the engine sizes on it). No time stop. Replay-only: the CLI scan and nightly attach extras before
`join_edgar`, so the score is NaN there and the strategy is silent.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, finite

NAME = "composite_cost_aware_rank"
SCORE, RANK, MONTH_END = "ccr_score", "ccr_score_rank", "month_end"  # features.extra


@register("strategy", NAME)
class CompositeCostAwareRank(PanelStrategy):
    name = NAME
    description = "Month end: buy the top 10% of a 4-signal composite rank; sell when it leaves the top 20%."
    default_params: dict[str, Any] = {
        "buy_rank_above": 0.90,  # card rule 3: buy zone top 10%
        "hold_rank_above": 0.80,  # card rule 3: hold zone top 20%
        "stop_atr_mult": 3.0,  # card rule 5: catastrophe stop 3 x ATR(63)
        "max_hold_days": 10_000,  # card: the rank is the exit (finite so the 20-bar backtest default never applies)
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: crash filter optional, not registered
        P_MIN_RR: 0.0,  # no target
    }
    extra_features = [SCORE, RANK, MONTH_END, "atr_63"]
    prior_columns: list[str] = []
    engine_trail = False  # rank exit only

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        """On a rebalance row: sell when the name left the hold zone or has no rank (rank_hysteresis drops it)."""
        flag = row.get(MONTH_END)
        if not finite(flag) or float(flag) != 1.0:
            return False
        rank = row.get(RANK)
        return not finite(rank) or float(rank) <= float(self.params["hold_rank_above"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        rows = c1.rows(self, panel, as_of)
        if rows.empty or not (rows[MONTH_END] == 1.0).any():
            return []
        mult = float(self.params["stop_atr_mult"])
        out: list[Signal] = []
        for _, row in rows.loc[rows[RANK] > float(self.params["buy_rank_above"])].iterrows():
            atr, close = row["atr_63"], float(row["close"])
            if not finite(atr):
                continue
            sig = self.build_signal(row, as_of, entry=close, stop=close - mult * float(atr), target=None,
                                    score=float(row[RANK]), features={SCORE: row[SCORE], RANK: row[RANK]},
                                    notes=f"composite rank {float(row[RANK]):.2f}")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
