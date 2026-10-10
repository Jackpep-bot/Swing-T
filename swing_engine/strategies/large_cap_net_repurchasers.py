"""Large-cap net repurchasers (Pontiff & Woodgate 2008; Fama & French 2008): docs/proposals/swing-methods-2026-10/
batch2/large_cap_net_repurchasers.md, pre-registered in docs/preregistration/2026-10-10-batch2.md.

`big_net_issuance` (features.extra) = ln(split-adjusted shares usable 126 sessions ago / 378 sessions ago) from
EDGAR cover-page counts and the splits table (data.fundamentals.join_share_issuance), for the session's 500 largest
names by point-in-time market cap with an as-traded close >= $10 and >= 504 bars; `big_net_issuance_rank` is its
same-session percentile (the replay re-ranks it among its point-in-time universe; low = largest net repurchase). On
the last NYSE session of each month: buy rank <= 0.10 (next open); a held name is sold at the next open when its
rank is > 0.20 or missing (left the hold zone, the 500, or lost its signal). Catastrophe stop 3 x ATR(63) (card; the
engine sizes on it). No target, no time stop, no regime gate, `engine_trail = False`. Equal weight and the 50-name
cap come from the book (config/prereg_b2.yaml). Replay-only: the CLI scan and nightly do not run the share join, so
the rank is NaN there and the strategy is silent.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, finite

NAME = "large_cap_net_repurchasers"
NSI, RANK, MONTH_END, ATR = "big_net_issuance", "big_net_issuance_rank", "month_end", "atr_63"  # features.extra


@register("strategy", NAME)
class LargeCapNetRepurchasers(PanelStrategy):
    name = NAME
    description = "Month end: buy the 10% of the 500 largest stocks with the largest net share reduction; hold to 20%."
    default_params: dict[str, Any] = {
        "buy_rank_max": 0.10,  # card: buy zone = bottom 10% of net issuance
        "hold_rank_max": 0.20,  # card: hold zone = bottom 20%
        "stop_atr_mult": 3.0,  # card: catastrophe stop 3 x atr_63
        "max_hold_days": 10_000,  # the rank is the exit (finite so the 20-bar backtest default never applies)
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: no regime gate
        P_MIN_RR: 0.0,  # card: no target
    }
    extra_features = [NSI, RANK, MONTH_END, ATR]
    prior_columns: list[str] = []
    engine_trail = False  # rank exit only

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        """On a rebalance row: sell when the name left the hold zone or has no rank."""
        flag = row.get(MONTH_END)
        if not finite(flag) or float(flag) != 1.0:
            return False
        rank = row.get(RANK)
        return not finite(rank) or float(rank) > float(self.params["hold_rank_max"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        rows = c1.rows(self, panel, as_of)
        if rows.empty or not (rows[MONTH_END] == 1.0).any():
            return []
        mult = float(self.params["stop_atr_mult"])
        out: list[Signal] = []
        for _, row in rows.loc[rows[RANK] <= float(self.params["buy_rank_max"])].iterrows():
            atr, close = row[ATR], float(row["close"])
            if not finite(atr):
                continue
            sig = self.build_signal(row, as_of, entry=close, stop=close - mult * float(atr), target=None,
                                    score=1.0 - float(row[RANK]), features={NSI: row[NSI], RANK: row[RANK]},
                                    notes=f"net issuance {float(row[NSI]):+.3f}, rank {float(row[RANK]):.2f} of the 500 largest")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
