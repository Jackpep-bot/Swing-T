"""Pullback to a rising moving average inside an uptrend (long).

Sources (docs/research-raw/methods-sweeps): Raschke "Holy Grail" (price touches the 20 EMA in a trend, buy
stop above the high of the touch bar, stop below that bar's low / the swing low, target = prior swing high)
and Qullamaggie flags "surfing the 10/20-day MAs with volume drying up". Trend = features/regime.py
trend_state == 1 (close > sma_50 > sma_200 and sma_50 rising).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import (
    P_MIN_MARKET_TREND,
    P_MIN_RR,
    P_MIN_TREND,
    TREND_FLAT,
    TREND_UP,
    PanelStrategy,
    RollingSpec,
    finite,
)

NAME = "pullback_trend"
TARGET_R_MULTIPLE = "r_multiple"
TARGET_SWING_HIGH = "swing_high"


@register("strategy", NAME)
class PullbackTrend(PanelStrategy):
    name = NAME
    description = "trend_state==1, pullback low touches the MA on drying volume, entry on close > prior high."
    default_params: dict[str, Any] = {
        "pullback_ma": "ema_21",  # or "sma_20"
        "touch_pct": 0.01,  # pullback low <= ma * (1 + touch_pct)
        "pullback_bars": 4,  # bars before the as-of bar that form the pullback
        "max_pullback_volume_ratio": 1.0,  # mean volume over the pullback bars / avg_vol_20d (drying up)
        "stop_atr_buffer": 0.1,  # stop = pullback low - stop_atr_buffer * atr_14
        "target_mode": TARGET_R_MULTIPLE,  # or TARGET_SWING_HIGH (falls back to r_multiple if not above entry)
        "target_r": 2.0,
        "swing_high_bars": 20,  # lookback (excluding the as-of bar) for the prior swing high
        P_MIN_TREND: TREND_UP,
        P_MIN_MARKET_TREND: TREND_FLAT,
        P_MIN_RR: 1.0,
    }
    features_required = ["atr_14", "avg_vol_20d", "trend_state"]

    def required_features(self) -> list[str]:
        return [*self.features_required, str(self.params["pullback_ma"])]

    def _rolling(self) -> list[RollingSpec]:
        n = int(self.params["pullback_bars"])
        return [
            RollingSpec("low", "min", n + 1),  # includes the as-of bar
            RollingSpec("volume", "mean", n, prior=True),
            RollingSpec("high", "max", int(self.params["swing_high_bars"]), prior=True),
        ]

    def _target(self, entry: float, risk: float, swing_high: Any) -> tuple[float, str]:
        mode = str(self.params["target_mode"])
        if mode not in (TARGET_R_MULTIPLE, TARGET_SWING_HIGH):
            raise ValueError(f"{self.name}: unknown target_mode {mode!r}")
        r_target = entry + float(self.params["target_r"]) * risk
        if mode == TARGET_SWING_HIGH and finite(swing_high) and float(swing_high) > entry:
            return float(swing_high), TARGET_SWING_HIGH
        return r_target, TARGET_R_MULTIPLE

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        specs = self._rolling()
        low_col, vol_col, high_col = (s.out for s in specs)
        rows = self.rows_as_of(panel, as_of, rolling=specs, required=self.required_features())
        ma_col = str(self.params["pullback_ma"])
        touch = float(self.params["touch_pct"])
        max_vol_ratio = float(self.params["max_pullback_volume_ratio"])
        buffer = float(self.params["stop_atr_buffer"])
        out: list[Signal] = []
        for _, row in rows.iterrows():
            ma, atr, avg_vol = row[ma_col], row["atr_14"], row["avg_vol_20d"]
            pb_low, pb_vol, prior_high = row[low_col], row[vol_col], row["prior_high"]
            if not all(finite(x) for x in (ma, atr, avg_vol, pb_low, pb_vol, prior_high)):
                continue
            if not self.trend_ok(row):
                continue
            ma, atr, avg_vol = float(ma), float(atr), float(avg_vol)
            pb_low, pb_vol, prior_high = float(pb_low), float(pb_vol), float(prior_high)
            close = float(row["close"])
            if atr <= 0 or avg_vol <= 0:
                continue
            if close <= prior_high or close <= ma:  # entry trigger: close above the prior bar's high, back over MA
                continue
            if pb_low > ma * (1.0 + touch):  # the pullback never reached the MA
                continue
            vol_ratio = pb_vol / avg_vol
            if vol_ratio > max_vol_ratio:
                continue
            stop = pb_low - buffer * atr
            risk = close - stop
            if risk <= 0:
                continue
            target, target_kind = self._target(close, risk, row[high_col])
            reward_risk = (target - close) / risk
            mom = row.get("ret_63d")
            score = reward_risk + (max(float(mom), 0.0) if finite(mom) else 0.0)
            sig = self.build_signal(
                row,
                as_of,
                entry=close,
                stop=stop,
                target=target,
                score=score,
                features={
                    "pullback_ma": ma,
                    "pullback_low": pb_low,
                    "pullback_volume_ratio": vol_ratio,
                    "prior_high": prior_high,
                    "atr_14": atr,
                    "trend_state": row["trend_state"],
                },
                notes=f"pullback to {ma_col} {ma:.2f}, close {close:.2f} > prior high {prior_high:.2f}; target {target_kind}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
