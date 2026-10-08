"""Ken Calhoun ADX breakout (long), docs/strategies/calhoun_adx_breakout.md (catalog B7, thinkorswim ADXBreakoutsLE +
ADXBreakoutsFilter).

Rule: ADX(14) crosses above 40 while the bar's high is the 15-bar high, +DI > -DI; filter: 15-bar (max high - min
low) / close >= 10% (card's percentage version of the $5 range rule; the $20-70 price band is left to the engine
universe). Entry: buy stop at the trigger high + 0.15 x atr_14 (card: offset as a fraction of ATR instead of
$0.50). The tos order stays live until filled; the engine's stop orders expire after one session (card proposed 3).
Stop = entry - 2 x atr_14, target 2R, 15-session time exit.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import EntryType, Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, PanelStrategy, finite

NAME = "calhoun_adx_breakout"


@register("strategy", NAME)
class CalhounAdxBreakout(PanelStrategy):
    name = NAME
    description = "ADX14 crosses 40 at a 15-bar high, +DI > -DI, 15-bar range >= 10%; buy stop over the high."
    default_params: dict[str, Any] = {
        "adx_level": 40.0,  # card / tos: ADX crosses above 40
        "highest_len": 15,  # card / tos: price at its 15-bar high (also the range-filter window)
        "min_range_pct": 0.10,  # card: 15-bar range / close >= 10% (replaces >= $5)
        "entry_offset_atr": 0.15,  # card: buy stop at trigger high + 0.15 x atr_14 (tos: $0.50)
        "stop_atr_mult": 2.0,  # card: stop = entry - 2 x atr_14
        "target_r": 2.0,  # card: target 2R
        "max_hold_days": 15,  # card
        P_MIN_TREND: TREND_DOWN,
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 2.0,  # card
    }
    features_required = ["atr_14"]
    extra_features = ["adx_14", "plus_di_14", "minus_di_14", "prev_adx_14", "high_15", "low_15"]

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        n = int(self.params["highest_len"])
        self.extra_features = ["adx_14", "plus_di_14", "minus_di_14", "prev_adx_14", f"high_{n}", f"low_{n}"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        n = int(p["highest_len"])
        level = float(p["adx_level"])
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        out: list[Signal] = []
        for _, row in rows.iterrows():
            adx, prev_adx, pdi, mdi = row["adx_14"], row["prev_adx_14"], row["plus_di_14"], row["minus_di_14"]
            hi, lo, atr = row[f"high_{n}"], row[f"low_{n}"], row["atr_14"]
            if not all(finite(x) for x in (adx, prev_adx, pdi, mdi, hi, lo, atr)):
                continue
            high, close = float(row["high"]), float(row["close"])
            if not (float(prev_adx) < level <= float(adx) and high >= float(hi) and float(pdi) > float(mdi)):
                continue
            if (float(hi) - float(lo)) / close < float(p["min_range_pct"]):
                continue
            entry = high + float(p["entry_offset_atr"]) * float(atr)
            stop = entry - float(p["stop_atr_mult"]) * float(atr)
            sig = self.build_signal(
                row,
                as_of,
                entry=entry,
                stop=stop,
                target=entry + float(p["target_r"]) * (entry - stop),
                score=float(adx),
                features={"adx_14": adx, "plus_di_14": pdi, "minus_di_14": mdi, "atr_14": atr,
                          "range_pct": (float(hi) - float(lo)) / close, "max_hold_days": p["max_hold_days"]},
                notes=f"ADX {float(prev_adx):.0f} -> {float(adx):.0f} through {level:g} at the {n}-bar high; buy stop "
                f"{entry:.2f}",
            )
            if sig:
                out.append(sig.model_copy(update={"entry_type": EntryType.STOP}))
        self.log_scan(as_of, len(rows), len(out))
        return out
