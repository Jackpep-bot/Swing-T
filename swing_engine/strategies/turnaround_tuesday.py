"""Turnaround Tuesday (long SPY): docs/strategies/turnaround_tuesday.md, catalog E37 (Quantified Strategies).

Rule: on the first session of a week, if the close is at least 1% below the prior session's close (Friday), buy
and sell one session later. No stop or target in the source; the engine adds a catastrophic `3 x atr_14` stop.

Approximation: the source buys Monday's close (MOC); the engine fills at the next open, so replay tests Tuesday
open -> Tuesday close (the card flags this as a different trade until an MOC entry hook exists). `symbols` limits
it to the index ETF (the rule is untested on single stocks).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy, _local_day, finite

NAME = "turnaround_tuesday"


@register("strategy", NAME)
class TurnaroundTuesday(PanelStrategy):
    name = NAME
    description = "SPY: first session of the week closes <= -1% vs the prior close; hold one session."
    default_params: dict[str, Any] = {
        "symbols": ["SPY"],  # card: SPY only
        "max_ret": -0.01,  # card: Monday close <= 0.99 x Friday close
        "max_hold_days": 1,  # card: sell at Tuesday's close
        "stop_atr_mult": 3.0,  # card: catastrophic stop entry - 3 x atr_14 (engine choice)
        P_MIN_MARKET_TREND: TREND_DOWN,  # no market gate in the source; the router disables it in selloffs
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["atr_14"]
    prior_columns = ["close", "ts"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        rows = self.rows_as_of(panel, as_of)
        rows = rows[rows[SYMBOL].isin(list(self.params["symbols"]))]
        out: list[Signal] = []
        for _, row in rows.iterrows():
            prev_close, atr = row["prior_close"], row["atr_14"]
            if not (finite(prev_close) and finite(atr)) or pd.isna(row["prior_ts"]):
                continue
            day, prev_day = (_local_day(pd.Series([row[c]])).iloc[0] for c in ("ts", "prior_ts"))
            if day.isocalendar()[:2] == prev_day.isocalendar()[:2]:
                continue  # not the first session of the week
            close = float(row["close"])
            ret = close / float(prev_close) - 1.0
            if ret > float(self.params["max_ret"]):
                continue
            sig = self.build_signal(
                row, as_of, entry=close, stop=close - float(self.params["stop_atr_mult"]) * float(atr), target=None,
                score=-ret, features={"ret_week_open": ret, "atr_14": atr, "max_hold_days": self.params["max_hold_days"]},
                notes=f"first session of the week {ret * 100:.1f}% vs prior close; hold 1 session",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
