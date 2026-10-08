"""Fundamental setup + technical trigger (long), docs/strategies/fundamental_setup_technical_trigger.md (catalog B85,
TradeStation Fundamntl & Chan LE).

Pre-registered card variant: EPS-diluted momentum (latest quarter vs the same quarter a year earlier) with the Chan
6-bar trigger. APPROXIMATION: the setup reads the OPTIONAL panel column `sue` (data.fundamentals: seasonal-random-
walk standardized unexpected EPS, diluted, from 10-Q/10-K filings, visible the session after `filed`); its sign is the
sign of EPS(q) - EPS(q-4), i.e. the card's `fund_mom > 0`. No `sue` column -> no signals. Trigger: close above the
highest high of the prior 6 bars (daily approximation of the intraday break). Stop: the tighter of the prior 6-bar
low and entry - 2 x atr_14, but at least 1 x atr_14 below entry. No target; exit on a close below the prior 6-bar
low (Chan LX) or after 40 sessions. Other triggers (MACD, RSI, Stoch, Volty) and the acceleration mode are not built.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import structlog

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, PanelStrategy, finite

log = structlog.get_logger(__name__)

NAME = "fundamental_setup_technical_trigger"
SUE_COL = "sue"  # data.fundamentals.FEATURE_COLUMNS (optional panel join)


@register("strategy", NAME)
class FundamentalSetupTechnicalTrigger(PanelStrategy):
    name = NAME
    description = "Optional sue > 0 (EPS yoy up) and close over the prior 6-bar high; Chan 6-bar-low exit."
    default_params: dict[str, Any] = {
        "min_sue": 0.0,  # card: fund_mom > 0 (sign of the SUE numerator)
        "channel_len": 6,  # card: Chan LE 6-bar highest high / LX 6-bar lowest low
        "stop_atr_mult": 2.0,  # card: entry - 2 x atr_14 when tighter than the channel low
        "min_stop_atr": 1.0,  # card: stop at least 1 x atr_14 below entry
        "max_hold_days": 40,  # card
        P_MIN_TREND: TREND_DOWN,
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["atr_14"]
    extra_features = ["dc_high_6", "dc_low_6"]

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        n = int(self.params["channel_len"])
        self.extra_features = [f"dc_high_{n}", f"dc_low_{n}"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        low = row.get(self.extra_features[1])
        return finite(low) and float(row["close"]) < float(low)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if SUE_COL not in panel.columns:
            log.debug("strategy.skip", strategy=self.name, reason=f"panel has no {SUE_COL!r} column")
            return []
        if not self.market_ok(regime):
            return []
        p = self.params
        hi_col, lo_col = self.extra_features
        rows = self.rows_as_of(panel, as_of, required=[*self.required_features(), SUE_COL])
        out: list[Signal] = []
        for _, row in rows.iterrows():
            sue, hi, lo, atr = row[SUE_COL], row[hi_col], row[lo_col], row["atr_14"]
            if not all(finite(x) for x in (sue, hi, lo, atr)) or float(sue) <= float(p["min_sue"]):
                continue
            close = float(row["close"])
            if close <= float(hi):
                continue
            stop = min(max(float(lo), close - float(p["stop_atr_mult"]) * float(atr)),
                       close - float(p["min_stop_atr"]) * float(atr))
            sig = self.build_signal(
                row,
                as_of,
                entry=close,
                stop=stop,
                target=None,
                score=float(sue),
                features={SUE_COL: sue, hi_col: hi, lo_col: lo, "atr_14": atr, "max_hold_days": p["max_hold_days"]},
                notes=f"EPS momentum (SUE {float(sue):.2f}) and close {close:.2f} over the {hi_col} {float(hi):.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
