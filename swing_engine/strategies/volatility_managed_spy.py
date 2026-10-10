"""Volatility-managed SPY, capped at 100% (Moreira & Muir, JF 2017): docs/proposals/swing-methods-2026-10/batch2/
volatility_managed_spy.md, pre-registered in docs/preregistration/2026-10-10-batch2.md.

Target weight w = min(1, c / RV) with RV = `rvar_22` (sum of squared daily SPY log returns over 22 sessions) at the
latest month-end session on or before the signal day and c = 0.16^2 / 12 (fixed in advance, card). The target holds
until the next month end.

How the engine holds a fraction (it sizes by stop distance and keeps one position per symbol):
- Size. The sizer buys equity x risk% / (entry x (1 + limit buffer) - stop) shares, so the signal's catastrophe stop
  is placed at close x (1 + buffer - (risk% / 100) / w): the position is w x equity. `book_risk_pct` must equal the
  book's `risk.risk_per_trade_pct` (config/prereg_b2_spy.yaml, tested). With 20% the stop is 19% below the close at
  w = 1 and further away for smaller w; a weight below 0.20 has no positive stop, so 0.10 <= w < 0.20 is held as
  0.20 and w < 0.10 as cash (`min_weight`).
- Rebalance. `should_exit` fires at a month-end close when |w_new - w at entry| >= `rebalance_band` 0.10 (card
  no-trade band); the whole position is sold at the next open. An entry signal is emitted every session at the
  current target (the engine ignores it while SPY is held), so the new weight is bought at the open after that: a
  rebalance is a full round trip with one session in cash, not a trade of the difference. The same signal re-enters
  after a stop-out and opens the first position of a run.
No target, no regime gate, `engine_trail = False`. Live: no entry features, so no rebalance exit (replay-only).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import PositionContext, Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy, entry_feature, finite

NAME = "volatility_managed_spy"
RV, MONTH_END = "rvar_22", "month_end"  # features.extra; card: one month = 22 sessions
WEIGHT = "weight"
BAND_TOLERANCE = 1e-9


@register("strategy", NAME)
class VolatilityManagedSpy(PanelStrategy):
    name = NAME
    description = "SPY at weight min(1, c / last month's realized variance); monthly, 10-point no-trade band."
    default_params: dict[str, Any] = {
        "symbols": ["SPY"],  # card: SPY only
        "target_variance": 0.16**2 / 12.0,  # card: c = monthly variance of 16% annualised vol, fixed in advance
        "max_weight": 1.0,  # card: capped at 100% (cash account)
        "rebalance_band": 0.10,  # card: trade only if |w_new - w_held| >= 0.10
        "min_weight": 0.20,  # engine: smallest weight a positive stop can express at book_risk_pct 20
        "book_risk_pct": 20.0,  # engine: = risk.risk_per_trade_pct of the book (config/prereg_b2_spy.yaml)
        "limit_buffer_pct": 1.0,  # engine: = risk.sizing.ENTRY_LIMIT_BUFFER_PCT (the sizer's worst-case fill)
        "max_hold_days": 10_000,  # the weight is the exit (finite so the 20-bar backtest default never applies)
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: no regime gate
        P_MIN_RR: 0.0,  # card: no target
    }
    extra_features = [RV, MONTH_END]
    prior_columns: list[str] = []
    engine_trail = False  # monthly weight only

    def target_weight(self, rv: Any) -> float | None:
        """min(max_weight, c / RV), held as min_weight when in [min_weight / 2, min_weight) and 0 below that."""
        if not finite(rv):
            return None
        p = self.params
        cap, floor = float(p["max_weight"]), float(p["min_weight"])
        w = cap if float(rv) <= 0 else min(cap, float(p["target_variance"]) / float(rv))
        return 0.0 if w < floor / 2.0 else max(w, floor)

    def should_exit(self, row: pd.Series, bars_held: int, position: PositionContext | None = None) -> bool:
        """Month end: the target weight moved >= the band away from the weight bought (unknown live: no exit)."""
        flag, held = row.get(MONTH_END), entry_feature(position, WEIGHT)
        if held is None or not finite(flag) or float(flag) != 1.0:
            return False
        new = self.target_weight(row.get(RV))
        return new is not None and abs(new - held) >= float(self.params["rebalance_band"]) - BAND_TOLERANCE

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        p = self.params
        rows = c1.rows(self, panel, as_of)
        rows = rows.loc[rows[SYMBOL].isin([str(s) for s in p["symbols"]])]
        if rows.empty:
            return []
        view = c1.view(self, panel, as_of, [])
        out: list[Signal] = []
        for _, row in rows.iterrows():
            hist = view.window(str(row[SYMBOL]), [RV, MONTH_END])
            ends = np.flatnonzero(hist[MONTH_END] == 1.0)
            if not len(ends):
                continue
            rv = hist[RV][ends[-1]]
            w = self.target_weight(rv)
            if not w:
                continue
            close = float(row["close"])
            stop = close * (1.0 + float(p["limit_buffer_pct"]) / 100.0 - float(p["book_risk_pct"]) / 100.0 / w)
            sig = self.build_signal(row, as_of, entry=close, stop=stop, target=None, score=0.0,
                                    features={WEIGHT: w, RV: rv}, notes=f"target weight {w:.2f}")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
