"""52-week-high breakout on volume (long), Minervini / O'Neil lineage.

Sources (docs/research-raw/methods-sweeps, docs/research-monitor.md): 52w/ATH break on >= 1.5x volume;
Minervini VCP = successive contractions each roughly half the prior, so an optional tightness filter on
`vcp_contraction` (ratio of last contraction range to first, lower = tighter) can be enabled. Stop is an
ATR multiple, target a fixed R multiple; the close must sit near the high (not a reversal bar).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_FLAT, PanelStrategy, finite

NAME = "breakout_52w"
VCP_COLUMN = "vcp_contraction"


@register("strategy", NAME)
class Breakout52w(PanelStrategy):
    name = NAME
    description = "breakout_52w flag on >= volume_mult x avg_vol_50d, close near the high; ATR stop, R target."
    default_params: dict[str, Any] = {
        "volume_mult": 1.5,  # explicit volume gate (the flag also embeds it)
        "stop_atr_mult": 2.0,  # stop = close - stop_atr_mult * atr_14
        "target_r": 2.0,  # target = entry + target_r * risk
        "max_close_below_high": 0.03,  # dist_52w_high (close/high_52w - 1) must be >= -max_close_below_high
        "vcp_max_contraction": None,  # e.g. 0.5 (Minervini: each contraction ~half the prior); None = off
        P_MIN_TREND: TREND_FLAT,
        P_MIN_MARKET_TREND: TREND_FLAT,
        P_MIN_RR: 1.0,
    }
    features_required = ["breakout_52w", "dist_52w_high", "avg_vol_50d", "atr_14", "trend_state"]

    def _vcp_limit(self) -> float | None:
        v = self.params.get("vcp_max_contraction")
        return float(v) if finite(v) else None

    def required_features(self) -> list[str]:
        cols = list(self.features_required)
        if self._vcp_limit() is not None:
            cols.append(VCP_COLUMN)
        return cols

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        vol_mult = float(self.params["volume_mult"])
        stop_mult = float(self.params["stop_atr_mult"])
        target_r = float(self.params["target_r"])
        max_below = float(self.params["max_close_below_high"])
        vcp_limit = self._vcp_limit()
        out: list[Signal] = []
        for _, row in rows.iterrows():
            flag, dist, atr = row["breakout_52w"], row["dist_52w_high"], row["atr_14"]
            if not (finite(flag) and float(flag) >= 1.0):
                continue
            if not (finite(dist) and finite(atr)) or not self.trend_ok(row):
                continue
            dist, atr = float(dist), float(atr)
            if atr <= 0 or dist < -max_below:
                continue
            vol_ratio = self.volume_ratio(row, "avg_vol_50d")
            if not finite(vol_ratio) or vol_ratio < vol_mult:
                continue
            vcp = row.get(VCP_COLUMN)
            if vcp_limit is not None and not (finite(vcp) and float(vcp) <= vcp_limit):
                continue
            close = float(row["close"])
            stop = close - stop_mult * atr
            target = close + target_r * (close - stop)
            tightness = (1.0 - float(vcp)) if finite(vcp) else 0.0
            sig = self.build_signal(
                row,
                as_of,
                entry=close,
                stop=stop,
                target=target,
                score=vol_ratio + tightness,
                features={
                    "dist_52w_high": dist,
                    "volume_ratio": vol_ratio,
                    "atr_14": atr,
                    VCP_COLUMN: vcp,
                    "trend_state": row["trend_state"],
                },
                notes=f"52w breakout on {vol_ratio:.1f}x vol, close {dist * 100:+.1f}% vs 52w high",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
