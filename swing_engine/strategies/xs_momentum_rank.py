"""Cross-sectional momentum rank (long), docs/strategies/xs_momentum_rank.md (E01 12-1 / E02 JT 6-1).

Month-end replay of the card's "Use 2": on the last NYSE session of the month (`rebalance_day` -1, NYSE calendar) buy every symbol whose
same-session percentile of `mom_12_1` (close[t-21] / close[t-252] - 1) is >= 0.90; hold 21 sessions, leaving early
only when the rank drops below 0.70 (card hysteresis). JT variant: `rank_col: mom_7_1_rank` (close[t-21] /
close[t-147] - 1). Ranks are over the symbols in the panel (no NYSE breakpoints or value weights: no market cap);
price momentum on split-adjusted closes, dividends excluded (card note). The stop is an engine disaster stop.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, finite
from ._catalog3 import month_offsets, session_day

NAME = "xs_momentum_rank"


@register("strategy", NAME)
class XSMomentumRank(PanelStrategy):
    name = NAME
    description = "Month end: buy the top decile of 12-1 momentum rank; exit below rank 0.70 or after 21 sessions."
    default_params: dict[str, Any] = {
        "rank_col": "mom_12_1_rank",  # card: 12-1 signal, same-session percentile (JT 6-1: "mom_7_1_rank")
        "entry_rank_min": 0.90,  # card: entry rank >= 0.90
        "exit_rank_below": 0.70,  # card: hysteresis exit < 0.70
        "rebalance_day": -1,  # card: month-end rebalance
        "stop_atr_mult": 3.0,  # engine disaster stop (none in the factor definition)
        "max_hold_days": 21,  # card: max_hold_days 21 per cohort
        P_MIN_MARKET_TREND: TREND_DOWN,  # crash filter is a separate catalog item (momentum_crash_filter_dm)
        P_MIN_RR: 0.0,  # card: min reward:risk n/a
    }
    features_required = ["atr_14"]
    extra_features = ["mom_12_1_rank"]
    engine_trail = False  # monthly hold with a rank exit

    def required_features(self) -> list[str]:
        return [*self.features_required, str(self.params["rank_col"])]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        rank = row.get(str(self.params["rank_col"]))
        return finite(rank) and float(rank) < float(self.params["exit_rank_below"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        rows = c1.rows(self, panel, as_of)
        day = session_day(rows)
        if day is None or int(self.params["rebalance_day"]) not in month_offsets(day):
            return []
        col = str(self.params["rank_col"])
        rows = rows.loc[rows[col] >= float(self.params["entry_rank_min"])]
        mult = float(self.params["stop_atr_mult"])
        out: list[Signal] = []
        for _, row in rows.iterrows():
            atr, close = row["atr_14"], float(row["close"])
            if not finite(atr):
                continue
            sig = self.build_signal(row, as_of, entry=close, stop=close - mult * float(atr), target=None,
                                    score=float(row[col]),
                                    features={col: row[col], "max_hold_days": self.params["max_hold_days"]},
                                    notes=f"month-end momentum: {col} {float(row[col]):.2f}")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
