"""Opportunistic insider purchases (long), docs/strategies/opportunistic_insider_purchases_cmp.md (catalog E26,
Cohen-Malloy-Pomorski 2012).

Thin variant of `insider_cluster` (catalog maps_to): it consumes the OPTIONAL column `opp_buy_value_21d` (dollar
value of open-market code-P buys by non-routine insiders filed in the last 21 sessions, per the card's feature spec)
and returns no signals while that column is absent. Signals fire only on the session the filing becomes public:
`fresh_column` (`opp_buy_flag`, the card's 1-if-a-filing-landed-on-as_of flag) must be >= 1 on the as-of row, so one
filing does not re-signal for the 21 sessions it stays in the rolling sum; no flag column, no signals. The
producer is `data.insiders` (`swing ingest-insiders`; CMP routine classifier on owner CIKs, joined via
`data.fundamentals.join_edgar`). Exits: the card's proposed CMP params, 2 ATR stop, 2R target and a 21-session (one
calendar month) time exit.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import SYMBOL
from .insider_cluster import InsiderCluster

NAME = "opportunistic_insider_purchases_cmp"


@register("strategy", NAME)
class OpportunisticInsiderPurchases(InsiderCluster):
    name = NAME
    description = "Optional opp_buy_value_21d >= $25k (non-routine Form 4 buys); 2 ATR stop, 2R target, 21-day hold."
    default_params: dict[str, Any] = {
        **InsiderCluster.default_params,
        "score_column": "opp_buy_value_21d",  # card feature spec (opportunistic code-P buys, last 21 sessions)
        "min_score": 25_000.0,  # card: proposed min_value_usd 25000 (replay value, not a paper number)
        "max_hold_days": 21,  # card: paper holds about one month
        "fresh_column": "opp_buy_flag",  # card: opp_buy_flag = 1 if a filing landed on as_of
    }

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        sigs = super().signals(panel, as_of, regime)
        col = str(self.params["fresh_column"])
        if not sigs or col not in panel.columns:
            return []
        rows = self.rows_as_of(panel, as_of, required=[col])
        fresh = set(rows.loc[pd.to_numeric(rows[col], errors="coerce") >= 1, SYMBOL])
        return [s for s in sigs if s.symbol in fresh]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])
