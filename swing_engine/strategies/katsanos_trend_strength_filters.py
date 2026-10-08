"""Katsanos trend-strength filter family (long): docs/strategies/katsanos_trend_strength_filters.md, catalog B18
(thinkorswim ADXTrend / ERTrend / R2Trend / VHFTrend).

Meter X (param `meter`): ADX(14), Kaufman ER(10), VHF(28) or R-squared(20). Gate for adx/er/vhf: developing
(X > crit and X > mult x lowest X of the prior `lag` bars) or strong (trend < X < max). R2: R2(20) > 0.42, rising,
and the 20-bar regression slope (as a fraction of the close) above `r2_slope_min`. Entry: the close crosses above
SMA(20) with the gate on; next open. The ADX meter also requires +DI > -DI (card's declared deviation: ADX is
direction-blind). Stop entry - 2 x atr_14; exit a close below SMA(20) or 40 sessions; no target. Levels other than
R2 0.42 are the card's engine assumptions (Katsanos defaults are not published). ER smoothing is not applied.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "katsanos_trend_strength_filters"
METERS = {"adx": "adx_14", "er": "er_10", "vhf": "vhf_28", "r2": "r2_20"}
MA, SLOPE = "sma_20", "linreg_slope_20"


@register("strategy", NAME)
class KatsanosTrendStrengthFilters(PanelStrategy):
    name = NAME
    description = "Close crosses above SMA20 while a trend meter (ADX / ER / VHF / R2) says trend; exit below SMA20."
    default_params: dict[str, Any] = {
        "meter": "adx",  # card: replay all four meters and report all
        "lag": 10,  # card engine assumption: lag 10
        "mult": 1.1,  # card engine assumption: mult 1.1
        "adx_crit": 20.0, "adx_trend": 25.0, "adx_max": 50.0,  # card: ADX(14) crit 20 trend 25 max 50
        "er_crit": 0.3, "er_trend": 0.5, "er_max": 1.0,  # card: ER(10) crit 0.3 trend 0.5 (ER <= 1)
        "vhf_crit": 0.35, "vhf_trend": 0.4, "vhf_max": None,  # card: VHF(28) crit 0.35 trend 0.4; no max given
        "r2_trend": 0.42,  # card: thinkorswim R2Trend default 0.42
        "r2_slope_min": 0.0,  # card: slope > +critical (critical unpublished; 0 = rising regression line)
        "stop_atr_mult": 2.0,  # card: stop entry - 2 x atr_14
        "max_hold_days": 40,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,  # regime-gating experiment: no extra market gate
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["atr_14", "prev_close", MA]
    extra_features = [f"prev_{MA}", *METERS.values(), "plus_di_14", "minus_di_14", SLOPE]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        ma = row.get(MA)
        return finite(ma) and float(row["close"]) < float(ma)

    def gate(self, x: np.ndarray, row: pd.Series) -> bool:
        p, meter, t = self.params, str(self.params["meter"]), len(x) - 1
        if meter not in METERS:
            raise ValueError(f"{self.name}: unknown meter {meter!r}; expected one of {sorted(METERS)}")
        lag = int(p["lag"])
        if t < lag or not np.isfinite(x[t - lag :]).all():
            return False
        if meter == "r2":
            slope = row.get(SLOPE)
            return (x[t] > float(p["r2_trend"]) and x[t] > x[t - 1] and finite(slope)
                    and float(slope) / float(row["close"]) > float(p["r2_slope_min"]))
        if meter == "adx" and not float(row["plus_di_14"]) > float(row["minus_di_14"]):
            return False
        crit, trend, top = p[f"{meter}_crit"], p[f"{meter}_trend"], p[f"{meter}_max"]
        developing = x[t] > float(crit) and x[t] > float(p["mult"]) * float(np.min(x[t - lag : t]))
        strong = x[t] > float(trend) and (top is None or x[t] < float(top))
        return bool(developing or strong)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        col = METERS.get(str(p["meter"]), METERS["adx"])
        view = as_of_view(panel, as_of, ["open", "high", "low", "close", *self.required_features()])
        cur = view.current
        cross = ((cur["close"] > cur[MA]) & (cur["prev_close"] <= cur[f"prev_{MA}"])).fillna(False)
        out: list[Signal] = []
        for _, row in cur.loc[cross].iterrows():
            x = view.window(str(row[SYMBOL]), [col])[col]
            if not self.gate(x, row) or not finite(row["atr_14"]):
                continue
            close = float(row["close"])
            sig = self.build_signal(
                row, as_of, entry=close, stop=close - float(p["stop_atr_mult"]) * float(row["atr_14"]), target=None,
                score=float(x[-1]), features={col: x[-1], MA: row[MA], "max_hold_days": p["max_hold_days"]},
                notes=f"{p['meter']} meter {x[-1]:.2f} on; close {close:.2f} crossed above {MA} {float(row[MA]):.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(cur), len(out))
        return out
