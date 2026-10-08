"""Bollinger Band mean reversion (long), docs/strategies/bollinger_band_mean_reversion.md (catalog B77 TradeStation
BollingerBandsLE, P3/P4 TradingView, thinkorswim BollingerBandsLE, B68 Webull).

Rule: BB(20, 2 SD). After a close below the lower band, the close crosses back above it (prior close <= prior lower
band, close > lower band); a buy stop for the next session sits at the lower band value (entry_type stop). The
built-ins have no stop, so the engine adds a catastrophic entry - 2 x atr_14; exit on a close at or above the mid
band (sma_20, card default; `exit_col` bb_upper_20 is the Webull variant) or after 10 sessions. Optional
`trend_ma` (e.g. sma_200, Connors) filter is off by default. Webull's engulfing / double-bottom confirmation is
discretionary and not coded. Long only.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import EntryType, Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, PanelStrategy, finite

NAME = "bollinger_band_mean_reversion"
LOWER = "bb_lower_20"


@register("strategy", NAME)
class BollingerBandMeanReversion(PanelStrategy):
    name = NAME
    description = "Close crosses back above bb_lower_20: buy stop at the band; exit at sma_20 or 10 days; 2 ATR stop."
    default_params: dict[str, Any] = {
        "exit_col": "sma_20",  # card: exit at the mid band (conservative); "bb_upper_20" = Webull variant
        "trend_ma": None,  # card optional filter close > sma_200 (Connors %b); None = off
        "stop_atr_mult": 2.0,  # card: catastrophic entry - 2 x atr_14 (no source stop)
        "max_hold_days": 10,  # card implementation spec
        P_MIN_TREND: TREND_DOWN,
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: rule exit
    }
    features_required = ["atr_14", "trend_state", "sma_20"]
    extra_features = [LOWER, f"prev_{LOWER}", "bb_upper_20"]  # contract columns, attached when a panel lacks them

    def required_features(self) -> list[str]:
        cols = [*super().required_features(), str(self.params["exit_col"])]
        trend = self.params.get("trend_ma")
        return list(dict.fromkeys([*cols, str(trend)] if trend else cols))

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        level = row.get(str(self.params["exit_col"]))
        return finite(level) and float(row["close"]) >= float(level)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        trend = p.get("trend_ma")
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        out: list[Signal] = []
        for _, row in rows.iterrows():
            lower, prev_lower, prev_close, atr = row[LOWER], row[f"prev_{LOWER}"], row["prior_close"], row["atr_14"]
            if not all(finite(x) for x in (lower, prev_lower, prev_close, atr)) or not self.trend_ok(row):
                continue
            close = float(row["close"])
            if not (float(prev_close) <= float(prev_lower) and close > float(lower)):
                continue
            if trend and not (finite(row[str(trend)]) and close > float(row[str(trend)])):
                continue
            entry = float(lower)
            sig = self.build_signal(
                row,
                as_of,
                entry=entry,
                stop=entry - float(p["stop_atr_mult"]) * float(atr),
                target=None,
                score=(close - entry) / float(atr) if float(atr) > 0 else 0.0,
                features={LOWER: lower, "sma_20": row["sma_20"], "atr_14": atr, "max_hold_days": p["max_hold_days"]},
                notes=f"close {close:.2f} back above the lower band {entry:.2f}: buy stop at the band, exit at "
                f"{p['exit_col']}",
            )
            if sig:
                out.append(sig.model_copy(update={"entry_type": EntryType.STOP}))
        self.log_scan(as_of, len(rows), len(out))
        return out
