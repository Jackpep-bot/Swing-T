"""Vitali Apirine Rate of Change with Bands (long), docs/strategies/apirine_roc_bands.md (catalog B42, thinkorswim
RateOfChangeWithBandsStrat).

Uptrend = close > EMA (ema_21). avgROC = EMA3 of ROC(12) (percent); bands = +/- k x RMS of avgROC over 20 bars
(card's assumed zero-centred form, formula_status approximation; `features.extra` `rms_<n>_of_<col>`). Buy when in
an uptrend avgROC crosses above the lower band. Sell when avgROC crosses below the upper band or the close falls
below the EMA. The tos pages state no default lengths: (12, 3, 20, 21, k 1) are engine picks inside the card's
ranges, untuned. Stop (engine choice): lowest low of the last 5 bars - 0.1 x atr_14; reference target 3R; 30-session
cap. Long only.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, PanelStrategy, RollingSpec, finite

NAME = "apirine_roc_bands"


def roc_names(params: dict[str, Any]) -> tuple[str, str]:
    """(avgROC column, RMS column) for the params."""
    avg = f"ema_{int(params['avg_len'])}_of_roc_{int(params['roc_len'])}"
    return avg, f"rms_{int(params['rms_len'])}_of_{avg}"


@register("strategy", NAME)
class ApirineRocBands(PanelStrategy):
    name = NAME
    description = "close > ema_21 and EMA3(ROC12) crosses above -1 x RMS20; exit on the upper-band cross or close < EMA."
    default_params: dict[str, Any] = {
        "roc_len": 12,  # card range 9-20 (default unverified)
        "avg_len": 3,  # card range 3-10
        "rms_len": 20,  # card range 10-30
        "band_mult": 1.0,  # card: num_rmss range 1-2
        "trend_ema": "ema_21",  # card range 20-50 (panel's ema_21)
        "stop_lookback": 5,  # card: lowest low of the last 5 bars ...
        "stop_atr_buffer": 0.1,  # ... minus 0.1 x atr_14
        "target_r": 3.0,  # card: reference target 3R; exits are by rule
        "max_hold_days": 30,  # card
        P_MIN_TREND: TREND_DOWN,
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 1.0,  # card
    }
    features_required = ["atr_14", "ema_21"]
    extra_features = [*roc_names(default_params), *(f"prev_{c}" for c in roc_names(default_params))]

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        cols = roc_names(self.params)
        self.extra_features = [*cols, *(f"prev_{c}" for c in cols)]

    def required_features(self) -> list[str]:
        return list(dict.fromkeys([*super().required_features(), str(self.params["trend_ema"])]))

    def _band(self, row: pd.Series) -> tuple[float, float, float, float] | None:
        """(avg, rms, prev avg, prev rms) or None while warming up."""
        vals = [row.get(c) for c in self.extra_features]
        return tuple(float(v) for v in vals) if all(finite(v) for v in vals) else None  # type: ignore[return-value]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        ema = row.get(str(self.params["trend_ema"]))
        if finite(ema) and float(row["close"]) < float(ema):
            return True
        b, k = self._band(row), float(self.params["band_mult"])
        return b is not None and b[2] >= k * b[3] and b[0] < k * b[1]

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        k, ema_col = float(p["band_mult"]), str(p["trend_ema"])
        spec = RollingSpec("low", "min", int(p["stop_lookback"]))
        rows = self.rows_as_of(panel, as_of, rolling=[spec], required=self.required_features())
        out: list[Signal] = []
        for _, row in rows.iterrows():
            b, ema, atr, low_n = self._band(row), row[ema_col], row["atr_14"], row[spec.out]
            if b is None or not all(finite(x) for x in (ema, atr, low_n)):
                continue
            avg, rms, prev_avg, prev_rms = b
            close = float(row["close"])
            if not (close > float(ema) and prev_avg <= -k * prev_rms and avg > -k * rms):
                continue
            stop = float(low_n) - float(p["stop_atr_buffer"]) * float(atr)
            sig = self.build_signal(
                row,
                as_of,
                entry=close,
                stop=stop,
                target=close + float(p["target_r"]) * (close - stop),
                score=(avg + k * rms) / rms if rms > 0 else 0.0,
                features={"roc_avg": avg, "roc_rms": rms, ema_col: ema, "atr_14": atr, "max_hold_days": p["max_hold_days"]},
                notes=f"avgROC {prev_avg:.2f} -> {avg:.2f} back over the lower band {-k * rms:.2f} above {ema_col}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
