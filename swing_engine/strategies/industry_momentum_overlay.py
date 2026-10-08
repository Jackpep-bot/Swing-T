"""Industry momentum (long top third of sectors): docs/strategies/industry_momentum_overlay.md, catalog E03
(Moskowitz-Grinblatt 1999, HXZ replication).

Rule: at each month end rank industries on their 6-month return (t-6..t-1, no skip month), hold the top bucket for
one month. Approximation: the engine has no SIC -> industry map or market-cap history, so this uses the card's
fallback, sector ETFs as the industries (SPDR sectors, financials dropped as in HXZ), equal weight, ranked on
`ret_126d` on the last session of the month (`tom_day == -1`); buy the top third, hold 21 sessions. The card's
overlay use (industry rank broadcast to member stocks) needs the SIC ingest and is not built. Stop: `3 x atr_14`
(engine choice; the factor has no stop); the engine trail is off so the monthly hold is not cut short.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "industry_momentum_overlay"
RET_COL = "ret_126d"  # 6 months, no skip month (MG / HXZ)
MONTH_END = -1.0  # features.extra tom_day of the last session of the month


@register("strategy", NAME)
class IndustryMomentumOverlay(PanelStrategy):
    name = NAME
    description = "Sector-ETF proxy for industry momentum: month-end top third by 6-month return, hold 1 month."
    default_params: dict[str, Any] = {
        # card fallback: 11 SPDR sector ETFs; HXZ drop financials (XLF, XLRE)
        "symbols": ["XLB", "XLC", "XLE", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"],
        "top_frac": 1.0 / 3.0,  # card: top third (9 portfolios of 5 in HXZ; coarser with sector ETFs)
        "min_members": 5,  # card: need enough industries ranked on the session
        "max_hold_days": 21,  # card: 1-month hold (strongest horizon)
        "stop_atr_mult": 3.0,  # engine choice: catastrophic stop
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # time exit, no target
    }
    features_required = [RET_COL, "atr_14"]
    extra_features = ["tom_day"]
    engine_trail = False  # monthly factor hold: the breakeven / N-day-low overlay would change the test

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        rows = rows[rows[SYMBOL].isin(list(self.params["symbols"])) & rows[RET_COL].notna()]
        if len(rows) < int(self.params["min_members"]) or not (rows["tom_day"] == MONTH_END).all():
            return []
        n_top = max(1, math.floor(len(rows) * float(self.params["top_frac"])))
        rank = rows[RET_COL].rank(ascending=False, method="first")
        out: list[Signal] = []
        for _, row in rows.loc[rank <= n_top].iterrows():
            close, atr = float(row["close"]), row["atr_14"]
            if not finite(atr):
                continue
            sig = self.build_signal(
                row, as_of, entry=close, stop=close - float(self.params["stop_atr_mult"]) * float(atr), target=None,
                score=float(row[RET_COL]),
                features={RET_COL: row[RET_COL], "rank": rank[row.name], "n_ranked": len(rows),
                          "max_hold_days": self.params["max_hold_days"]},
                notes=f"month-end sector rank {int(rank[row.name])}/{len(rows)}, 6-month return "
                f"{float(row[RET_COL]) * 100:.1f}%; hold {int(self.params['max_hold_days'])} sessions",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
