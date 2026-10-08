"""Elder MA-penetration channel swing (long; Fidelity Learning Center): docs/strategies/elder_ma_penetration_channel.md.

On close t (for day t+1): trend_state >= 1 (stand-in for the weekly uptrend; there is no weekly resampler) and
close > ema_21. A dip starts on a bar whose low is below the EMA after at least `min_closes_above` consecutive closes
above it and lasts while lows stay below; its depth = max (ema_21 - low) / ema_21. `pen_depth_avg` = mean over the
last `n_penetrations` completed dips within `pen_lookback` bars. Entry: limit buy at
ema_21 x (1 - depth_frac x pen_depth_avg), valid one session (`EntryType.LIMIT`: fills at min(open, limit) when the
low reaches it). Stop: limit - 1 x atr_14. Target: the upper channel ema_21 x (1 + k), k = the `channel_cover`
quantile of high / ema_21 - 1 over `lookback` bars (fit to contain ~95% of them). The discretionary "sooner in a weak
market / hold while new highs" exits are not modelled; 10-day time exit.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import EntryType, Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view

from ._base import (
    P_MIN_MARKET_TREND,
    P_MIN_RR,
    P_MIN_TREND,
    SYMBOL,
    TREND_DOWN,
    TREND_UP,
    PanelStrategy,
    finite,
)

NAME = "elder_ma_penetration_channel"
MA = "ema_21"


def penetration_depths(low, close, ma, min_above: int) -> list[float]:
    """Max relative depth of each completed dip (oldest first). A dip starts on a bar whose low is below ma after at
    least `min_above` consecutive closes above ma, and lasts while lows stay below; a dip still open is excluded."""
    depths: list[float] = []
    cur, above = None, 0
    for lo, c, m in zip(low, close, ma, strict=True):
        if lo < m and (cur is not None or above >= min_above):
            cur, above = max(cur or 0.0, (m - lo) / m), 0
            continue
        if cur is not None:
            depths.append(cur)
            cur = None
        above = above + 1 if c > m else 0
    return depths


@register("strategy", NAME)
class ElderMAPenetration(PanelStrategy):
    name = NAME
    description = "Limit buy below ema_21 at ~2/3 of the average recent penetration depth; target the upper channel."
    default_params: dict[str, Any] = {
        "n_penetrations": 3,  # card: Fidelity example averages 3 penetrations
        "depth_frac": 0.67,  # card: order ~1% below the MA vs 1.5% average depth
        "lookback": 100,  # card: channel fit over the last 100 bars
        "pen_lookback": 60,  # card: average the last 3 penetrations within 60 bars
        "min_closes_above": 3,  # card: a penetration needs at least 3 closes above ema_21 before it
        "channel_cover": 0.95,  # card: channel contains ~90-95% of the last 100 bars
        "stop_atr_mult": 1.0,  # card: stop = limit - 1.0 x atr_14
        "max_hold_days": 10,  # card
        P_MIN_TREND: TREND_UP,  # card: trend gate passes (weekly-uptrend stand-in)
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 1.5,  # card
    }
    features_required = ["atr_14", "trend_state", MA]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        n = int(p["lookback"])
        view = as_of_view(panel, as_of, ["high", "low", "close", *self.required_features()])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            ema, atr = row[MA], row["atr_14"]
            if not (finite(ema) and finite(atr) and float(row["close"]) > ema and self.trend_ok(row)):
                continue
            w = view.window(str(row[SYMBOL]), ["high", "low", "close", MA])
            hi, ma = w["high"][-n:], w[MA][-n:]
            if len(ma) < n or not np.isfinite(ma).all():
                continue
            m = int(p["pen_lookback"])
            depths = penetration_depths(w["low"][-m:], w["close"][-m:], w[MA][-m:], int(p["min_closes_above"]))[
                -int(p["n_penetrations"]) :
            ]
            if len(depths) < int(p["n_penetrations"]):
                continue
            pen = float(np.mean(depths))
            k = float(np.quantile(hi / ma - 1.0, float(p["channel_cover"])))
            limit = float(ema) * (1.0 - float(p["depth_frac"]) * pen)
            upper = float(ema) * (1.0 + k)
            sig = self.build_signal(
                row, as_of, entry=limit, stop=limit - float(p["stop_atr_mult"]) * float(atr), target=upper,
                score=(upper - limit) / float(atr),
                features={"pen_depth_avg": pen, "channel_k": k, MA: ema, "upper_channel": upper},
                notes=f"limit {limit:.2f} ({pen:.1%} avg penetration of {MA}), target channel {upper:.2f}",
            )
            if sig:
                out.append(sig.model_copy(update={"entry_type": EntryType.LIMIT}))
        self.log_scan(as_of, len(view.current), len(out))
        return out
