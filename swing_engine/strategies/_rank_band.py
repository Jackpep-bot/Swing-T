"""Month-end rank band shared by the batch-3 large-cap portfolios (docs/preregistration/2026-10-10-batch3.md): the
mirror image of large_cap_net_repurchasers (which buys LOW ranks and is left untouched as pre-registered).

On the last NYSE session of a month (`month_end` = 1): buy rows whose `RANK` (same-session percentile of `SCORE`,
high = best; the replay re-ranks it among its point-in-time universe) is above `buy_rank_min`, at the next open; a
held name is sold at the next open when its rank is at or below `hold_rank_min` or missing. Catastrophe stop
`stop_atr_mult` x ATR(63). No target, no time stop, no regime gate, no engine trail. Equal weight and the name cap
come from the book.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, finite

MONTH_END, ATR = "month_end", "atr_63"  # features.extra


class MonthEndRankBand(PanelStrategy):
    SCORE = RANK = ""  # features.extra columns, set by the subclass
    BAND_PARAMS: dict[str, Any] = {
        "stop_atr_mult": 3.0,  # cards: catastrophe stop 3 x atr_63
        "max_hold_days": 10_000,  # the rank is the exit (finite so the 20-bar backtest default never applies)
        P_MIN_MARKET_TREND: TREND_DOWN,  # cards: no regime gate
        P_MIN_RR: 0.0,  # cards: no target
    }
    prior_columns: list[str] = []
    engine_trail = False  # rank exit only

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        """On a rebalance row: sell when the name left the hold zone or has no rank."""
        flag = row.get(MONTH_END)
        if not finite(flag) or float(flag) != 1.0:
            return False
        rank = row.get(self.RANK)
        return not finite(rank) or float(rank) <= float(self.params["hold_rank_min"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        rows = c1.rows(self, panel, as_of)
        if rows.empty or not (rows[MONTH_END] == 1.0).any():
            return []
        mult = float(self.params["stop_atr_mult"])
        out: list[Signal] = []
        for _, row in rows.loc[rows[self.RANK] > float(self.params["buy_rank_min"])].iterrows():
            atr, close = row[ATR], float(row["close"])
            if not finite(atr):
                continue
            sig = self.build_signal(row, as_of, entry=close, stop=close - mult * float(atr), target=None,
                                    score=float(row[self.RANK]),
                                    features={self.SCORE: row[self.SCORE], self.RANK: row[self.RANK]},
                                    notes=f"{self.SCORE} {float(row[self.SCORE]):+.3f}, rank {float(row[self.RANK]):.2f}")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
