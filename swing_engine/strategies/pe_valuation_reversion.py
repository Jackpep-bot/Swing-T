"""P/E reversion (long), TradeStation P/E Undervalued LE: docs/strategies/pe_valuation_reversion.md, catalog B86.

Source rule: P/E = close / TTM EPS; buy when P/E < 0.90 x its 12-bar average; exit when P/E is back above the
average or EPS <= 0. Approximation: the panel has no TTM EPS (EDGAR XBRL EPS is not ingested and
`fundamentals.edgar_panel_features` carries none). Between earnings reports EPS is constant, so on daily bars the rule
is exactly the price rule the card asks to compare against: close < 0.90 x SMA(close, 12), exit close >= SMA12.
What this misses: the P/E jumps when EPS updates and the EPS <= 0 filter / exit. Stop entry - 2.5 x atr_14 (card's
engine choice), 30-session cap, no target. Short side not built.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, finite

NAME = "pe_valuation_reversion"
AVG = "sma_12"  # card: 12-bar average of P/E (= of price while EPS is constant)


@register("strategy", NAME)
class PEValuationReversion(PanelStrategy):
    name = NAME
    description = "Price proxy for the P/E rule: close 10% under its 12-bar SMA; exit back at the SMA."
    default_params: dict[str, Any] = {
        "pct_below": 0.10,  # card: P/E 10% below its 12-bar average
        "stop_atr_mult": 2.5,  # card: stop entry - 2.5 x atr_14 (engine choice)
        "max_hold_days": 30,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: mean reversion, choppy only via the router
        P_MIN_RR: 0.0,  # card: rule exit
    }
    features_required = ["atr_14"]
    extra_features = [AVG]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        avg = row.get(AVG)
        return finite(avg) and float(row["close"]) >= float(avg)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        keep = (rows["close"] < (1.0 - float(p["pct_below"])) * rows[AVG]).fillna(False)
        out: list[Signal] = []
        for _, row in rows.loc[keep].iterrows():
            close, avg, atr = float(row["close"]), float(row[AVG]), row["atr_14"]
            if not finite(atr):
                continue
            sig = self.build_signal(
                row, as_of, entry=close, stop=close - float(p["stop_atr_mult"]) * float(atr), target=None,
                score=1.0 - close / avg, features={AVG: avg, "dev": close / avg - 1.0, "max_hold_days": p["max_hold_days"]},
                notes=f"close {close:.2f} is {(1 - close / avg) * 100:.1f}% under its 12-bar SMA {avg:.2f} (P/E proxy)",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
