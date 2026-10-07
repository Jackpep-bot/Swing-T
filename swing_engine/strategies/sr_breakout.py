"""Schwab support/resistance breakout (long).

Source: docs/sources-schwab-massive.md. Close beyond the level on expanding volume; target = breakout level
plus the prior range (measured move: SLB $38-$44 range, breakout above $44 -> $50). `resistance_1` on the
as-of row is the nearest pivot level above the PRIOR close (features/levels.py), so `close > resistance_1`
is exactly "close above prior resistance", and `range_width = resistance_1 - support_1` is the prior range.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_FLAT, PanelStrategy, finite

NAME = "sr_breakout"
STOP_MODE_LEVEL = "level"
STOP_MODE_ATR = "atr"


@register("strategy", NAME)
class SRBreakout(PanelStrategy):
    name = NAME
    description = "Close > prior resistance_1 on >= volume_mult x avg_vol_50d; measured-move target."
    default_params: dict[str, Any] = {
        "volume_mult": 1.5,  # volume >= volume_mult * avg_vol_50d (docs/research-monitor.md 52w/level breaks)
        "stop_mode": STOP_MODE_LEVEL,  # "level": just below the breakout level; "atr": entry - atr_stop_mult*ATR
        "level_stop_atr_mult": 0.5,  # stop = level - level_stop_atr_mult * atr_14 in level mode
        "atr_stop_mult": 2.0,  # stop = entry - atr_stop_mult * atr_14 in atr mode
        P_MIN_TREND: TREND_FLAT,
        P_MIN_MARKET_TREND: TREND_FLAT,
        P_MIN_RR: 1.0,
    }
    features_required = ["resistance_1", "range_width", "atr_14", "avg_vol_50d", "trend_state"]

    def _stop(self, entry: float, level: float, atr: float) -> float:
        mode = str(self.params["stop_mode"])
        if mode == STOP_MODE_LEVEL:
            return level - float(self.params["level_stop_atr_mult"]) * atr
        if mode == STOP_MODE_ATR:
            return entry - float(self.params["atr_stop_mult"]) * atr
        raise ValueError(f"{self.name}: unknown stop_mode {mode!r} (use {STOP_MODE_LEVEL!r} or {STOP_MODE_ATR!r})")

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        rows = self.rows_as_of(panel, as_of)
        vol_mult = float(self.params["volume_mult"])
        out: list[Signal] = []
        for _, row in rows.iterrows():
            level, width, atr = row["resistance_1"], row["range_width"], row["atr_14"]
            if not (finite(level) and finite(width) and finite(atr)) or not self.trend_ok(row):
                continue
            level, width, atr = float(level), float(width), float(atr)
            close, prior_close = float(row["close"]), row["prior_close"]
            if width <= 0 or atr <= 0 or not finite(prior_close):
                continue
            if close <= level or float(prior_close) > level:  # first close through the level only
                continue
            vol_ratio = self.volume_ratio(row, "avg_vol_50d")
            if not finite(vol_ratio) or vol_ratio < vol_mult:
                continue
            stop = self._stop(close, level, atr)
            target = level + width
            risk = close - stop
            reward_risk = (target - close) / risk if risk > 0 else math.nan
            sig = self.build_signal(
                row,
                as_of,
                entry=close,
                stop=stop,
                target=target,
                score=vol_ratio + reward_risk,
                features={
                    "breakout_level": level,
                    "range_width": width,
                    "atr_14": atr,
                    "volume_ratio": vol_ratio,
                    "trend_state": row["trend_state"],
                },
                notes=f"close {close:.2f} > resistance {level:.2f} on {vol_ratio:.1f}x vol; measured move {target:.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
