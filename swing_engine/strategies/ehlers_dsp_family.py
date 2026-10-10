"""Ehlers DSP family (long), docs/strategies/ehlers_dsp_family.md (thinkorswim EhlersStoch etc., catalog B46).

One module, `variant` x `mode` (each pair a separate trial):
- `roof_zero`: the roofing filter (super smoother(10) of a 48-bar 2-pole high-pass, `roof_48_10`) crosses above 0
  (`mode: trend`) or below 0 (`mode: reversal`).
- `ehlers_stoch` (EhlersStoch): stochastic of the roofing filter over `stoch_len` bars, from the rolling extremes
  `max/min_20_of_roof_48_10`; `mode: trend` (thinkorswim "conventional") buys a cross above `oversold`, `mode:
  reversal` ("predictive") buys a cross below it. The article's final super-smoothing of the stochastic is omitted.
Geometry per card: trend mode stop = 10-bar low - 0.1 x atr_14, target 3R; reversal mode stop = entry - 2 x atr_14,
target 1.5R. Rule exit (roof_zero trend only): roof back below 0. Filters warm up for 100 bars (features.extra).
Not built: OnsetTrend, UniversalOscillator, ReverseEMA, SimpleROC, ElegantOscillator (AGC / quotient-transform /
reverse-EMA formulas must first be ported and checked against a published series, card).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "ehlers_dsp_family"
ROOF_ZERO, EHLERS_STOCH = "roof_zero", "ehlers_stoch"
TREND, REVERSAL = "trend", "reversal"
ROOF = "roof_48_10"


@register("strategy", NAME)
class EhlersDSPFamily(PanelStrategy):
    name = NAME
    description = "Roofing-filter zero cross or roofing stochastic cross, trend or reversal mode."
    default_params: dict[str, Any] = {
        "variant": ROOF_ZERO,  # card: one module, variant param
        "mode": TREND,  # card: trend | reversal (predictive)
        "stoch_len": 20,  # card: roof_stoch_20
        "oversold": 0.2,  # EhlersStoch oversold level (0-1 scale)
        "trend_low_bars": 10,  # card: trend stop = min(low, 10 bars) - 0.1 x atr_14
        "trend_stop_atr_buffer": 0.1,
        "reversal_stop_atr_mult": 2.0,  # card: reversal stop = entry - 2 x atr_14
        "trend_target_r": 3.0,  # card: trend target_r 3.0
        "reversal_target_r": 1.5,  # card: reversal target_r 1.5
        "max_hold_days": 15,  # card: 15 (reversal mode 7 -> set in settings)
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 1.0,  # card
    }
    features_required = ["atr_14"]
    extra_features = [ROOF, f"max_20_of_{ROOF}", f"min_20_of_{ROOF}"]

    def _cols(self) -> list[str]:
        n = int(self.params["stoch_len"])
        return [ROOF, f"max_{n}_of_{ROOF}", f"min_{n}_of_{ROOF}"]

    def required_features(self) -> list[str]:
        return [*self.features_required, *self._cols()]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if self.params["variant"] != ROOF_ZERO or self.params["mode"] != TREND:
            return False
        roof = row.get(ROOF)
        return finite(roof) and float(roof) < 0

    def _crossed(self, w: dict[str, Any]) -> bool:
        roof, hi, lo = (w[c][-2:] for c in self._cols())
        if len(roof) < 2:
            return False
        trend = self.params["mode"] == TREND
        if self.params["variant"] == ROOF_ZERO:
            level, x = 0.0, roof
        else:
            level, x = float(self.params["oversold"]), (roof - lo) / (hi - lo)
        if not (finite(x[0]) and finite(x[1])):
            return False
        return bool(x[0] <= level < x[1]) if trend else bool(x[0] >= level > x[1])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        cols = self._cols()
        view = c1.view(self, panel, as_of, cols)
        trend = self.params["mode"] == TREND
        p = self.params
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            atr = row["atr_14"]
            if not finite(atr):
                continue
            w = view.window(str(row[SYMBOL]), [*cols, "low"])
            if not self._crossed(w):
                continue
            close = float(row["close"])
            if trend:
                stop = float(w["low"][-int(p["trend_low_bars"]):].min()) - float(p["trend_stop_atr_buffer"]) * float(atr)
                tr = float(p["trend_target_r"])
            else:
                stop, tr = close - float(p["reversal_stop_atr_mult"]) * float(atr), float(p["reversal_target_r"])
            sig = self.build_signal(row, as_of, entry=close, stop=stop, target=close + tr * (close - stop), score=0.0,
                                    features={ROOF: w[ROOF][-1], "max_hold_days": p["max_hold_days"]},
                                    notes=f"Ehlers {p['variant']} ({p['mode']} mode) cross")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
