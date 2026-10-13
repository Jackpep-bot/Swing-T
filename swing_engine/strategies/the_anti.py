"""Raschke "The Anti" stochastic hook (long), docs/strategies/the_anti.md (catalog C4, Street Smarts / LBR).

Stochastic %K 7 smoothed 4 (slow K = SMA4 of fast K7) and %D = SMA10 of slow K (Street Smarts; the later manual's
%D 12 is `d_len`). Setup: %D rising for the last 4 bars; %K falling for the 3 bars before the signal bar (pulling
back against %D); trigger: %K hooks back up on the signal bar. Bar counts are forum restatements (card:
approximation); %K must be at or near %D before the hook (slowK[t-1] <= slowD[t-1] + 5); price trend gate
trend_state == 1 (card, engine choice). Entry: buy stop a tick above the hook bar's high (entry_type stop); stop a
tick under its low; no target; exit within 4 sessions. Long only.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import EntryType, Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, SYMBOL, TREND_DOWN, TREND_UP, PanelStrategy

NAME = "the_anti"


def stoch_names(params: dict[str, Any]) -> tuple[str, str]:
    k, s, d = (int(params[x]) for x in ("k_len", "k_smooth", "d_len"))
    return f"stoch_k_{k}_{s}", f"stoch_d_{k}_{s}_{d}"


@register("strategy", NAME)
class TheAnti(PanelStrategy):
    name = NAME
    description = "Slow %D(7,4,10) rising, %K pulls back 3 bars then hooks up; buy stop over the hook bar, 4-day exit."
    default_params: dict[str, Any] = {
        "k_len": 7,  # card: %K period 7
        "k_smooth": 4,  # card: %K smoothing 4
        "d_len": 10,  # card: %D 10 (Street Smarts; 12 in the later manual)
        "d_rising_bars": 4,  # card: %D rising for roughly 4+ bars
        "k_pullback_bars": 3,  # card: %K pulls back for about 3+ bars
        "k_near_d_max": 5.0,  # card: slowK_{t-1} <= slowD_{t-1} + 5 (pullback toward/against %D)
        "tick": 0.01,  # card: buy stop above the hook bar / stop below its low
        "max_hold_days": 4,  # card: exit within 2-4 bars
        P_MIN_TREND: TREND_UP,  # card: price trend gate trend_state == 1
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no target taught
    }
    features_required = ["trend_state"]
    extra_features = list(stoch_names(default_params))

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        self.extra_features = list(stoch_names(self.params))

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        k_col, d_col = self.extra_features
        nd, nk, tick = int(p["d_rising_bars"]), int(p["k_pullback_bars"]), float(p["tick"])
        view = as_of_view(panel, as_of, ["high", "low", "trend_state", k_col, d_col])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            if not self.trend_ok(row):
                continue
            w = view.window(str(row[SYMBOL]), (k_col, d_col))
            kk, dd = w[k_col], w[d_col]
            if len(kk) < max(nd, nk + 1) + 1:
                continue
            d_seg, k_seg = dd[-(nd + 1) :], kk[-(nk + 2) : -1]
            if not (np.isfinite(d_seg).all() and np.isfinite(kk[-(nk + 2) :]).all()):
                continue
            near_d = kk[-2] <= dd[-2] + float(p["k_near_d_max"])
            if not ((np.diff(d_seg) > 0).all() and (np.diff(k_seg) < 0).all() and kk[-1] > kk[-2] and near_d):
                continue
            entry, stop = float(row["high"]) + tick, float(row["low"]) - tick
            sig = self.build_signal(
                row,
                as_of,
                entry=entry,
                stop=stop,
                target=None,
                score=float(dd[-1] - dd[-1 - nd]),
                features={k_col: kk[-1], d_col: dd[-1], "max_hold_days": p["max_hold_days"]},
                notes=f"Anti: %D rising {nd} bars, %K hooked up from {kk[-2]:.0f} to {kk[-1]:.0f}; buy stop {entry:.2f}",
            )
            if sig:
                out.append(sig.model_copy(update={"entry_type": EntryType.STOP}))
        self.log_scan(as_of, len(view.current), len(out))
        return out
