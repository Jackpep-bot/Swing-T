"""Opportunistic insider purchases (long), docs/strategies/opportunistic_insider_purchases_cmp.md (catalog E26,
Cohen-Malloy-Pomorski 2012).

Thin variant of `insider_cluster` (catalog maps_to): it consumes the OPTIONAL column `opp_buy_value_21d` (dollar
value of open-market code-P buys by non-routine insiders filed in the last 21 sessions, per the card's feature spec)
and returns no signals while that column is absent. The producer (full Form 4 ingest with owner CIKs and the
routine-trader classifier) does not exist yet, so this module is wiring only until it does. Exits: the card's
proposed CMP params, 2 ATR stop, 2R target and a 21-session (one calendar month) time exit.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from swing_engine.core.registry import register

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
    }

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])
