"""EMA-zone pullback (long), docs/strategies/pullback_ema_zone.md (methods.md 7b #1; pullback_trend family).

Setup on the signal bar t: trend_state up; ema_20 > ema_50 with both rising over 5 bars; a zone touch on one of the
last 3 bars k (low <= ema_20 x 1.01 and low >= ema_50 x 0.99, i.e. into the zone without slicing the 50); at least 2
earlier respected tests of the zone in the 60 bars before k, each at least 5 bars after the previous one with a new
20-bar high in between (so the touch is the third or later). Trigger: close > the prior bar's high and > ema_20, on
pullback volume (mean of bars k .. t-1) no more than the 20-day average. Entry next open; stop entry - 2 x atr_14;
no target; exit on a close below ema_50 or after 60 sessions. "Do not rush stops to breakeven" (card), so the
engine's breakeven / N-day-low overlay is off (`engine_trail = False`). Score = 63-day return rank (leaders first).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view

from ._base import (
    P_MIN_MARKET_TREND,
    P_MIN_RR,
    P_MIN_TREND,
    SYMBOL,
    TREND_FLAT,
    TREND_UP,
    PanelStrategy,
    finite,
)

NAME = "pullback_ema_zone"
FAST, SLOW = "ema_20", "ema_50"  # card: 20 / 50 EMA zone
RANK_COL = "ret_63d_rank"
ARRAYS = ("high", "low", "close", "volume", FAST, SLOW)


@register("strategy", NAME)
class PullbackEmaZone(PanelStrategy):
    name = NAME
    description = "Third+ touch of the rising ema_20-ema_50 zone, close over the prior high; 2 ATR stop, ema_50 exit."
    default_params: dict[str, Any] = {
        "slope_bars": 5,  # card: ema_20[t] > ema_20[t-5], same for ema_50
        "touch_pct": 0.01,  # card: low <= ema_20 x (1 + touch) and low >= ema_50 x (1 - touch)
        "max_touch_age": 3,  # card: zone touch in the last 1-3 bars
        "min_prior_tests": 2,  # card: zone respected at least twice before
        "test_lookback": 60,  # card
        "test_separation": 5,  # card: 5 bars and a new 20-bar high between tests
        "new_high_bars": 20,
        "max_pullback_vol_ratio": 1.0,  # card: pullback volume / avg_vol_20d <= 1.0
        "stop_atr_mult": 2.0,  # card
        "max_hold_days": 60,  # card
        P_MIN_TREND: TREND_UP,  # card: trend_state == 1
        P_MIN_MARKET_TREND: TREND_FLAT,
        P_MIN_RR: 0.0,  # card: no target
    }
    engine_trail = False  # card: "do not rush stops to breakeven"
    features_required = ["atr_14", "trend_state", "avg_vol_20d"]
    extra_features = [FAST, SLOW, RANK_COL]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        slow = row.get(SLOW)
        return finite(slow) and float(row["close"]) < float(slow)

    def _touch(self, w: dict[str, np.ndarray], j: int) -> bool:
        tp = float(self.params["touch_pct"])
        return bool(w["low"][j] <= w[FAST][j] * (1.0 + tp) and w["low"][j] >= w[SLOW][j] * (1.0 - tp))

    def prior_tests(self, w: dict[str, np.ndarray], k: int) -> int:
        """Separated zone tests in the ``test_lookback`` bars before ``k`` (each after a new ``new_high_bars`` high)."""
        p = self.params
        sep, nh = int(p["test_separation"]), int(p["new_high_bars"])
        count, last = 0, None
        for j in range(max(nh, k - int(p["test_lookback"])), k):
            if not self._touch(w, j):
                continue
            if last is None or (j - last >= sep and any(
                w["high"][i] >= w["high"][i - nh : i].max() for i in range(last + 1, j)
            )):
                count, last = count + 1, j
        return count

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        sb = int(p["slope_bars"])
        view = as_of_view(panel, as_of, list(dict.fromkeys([*ARRAYS, *self.required_features()])))
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            atr, avg_vol = row["atr_14"], row["avg_vol_20d"]
            if not (finite(atr) and finite(avg_vol) and float(avg_vol) > 0) or not self.trend_ok(row):
                continue
            w = view.window(str(row[SYMBOL]), ARRAYS)
            t = len(w["close"]) - 1
            if t < sb + 1 or not np.isfinite(np.r_[w[FAST][t - sb :], w[SLOW][t - sb :]]).all():
                continue
            fast, slow, close = w[FAST][t], w[SLOW][t], w["close"][t]
            if not (fast > slow and fast > w[FAST][t - sb] and slow > w[SLOW][t - sb]):
                continue
            if not (close > w["high"][t - 1] and close > fast):
                continue
            k = next((j for j in range(t - 1, max(0, t - 1 - int(p["max_touch_age"])), -1) if self._touch(w, j)), None)
            if k is None or float(np.mean(w["volume"][k:t])) / float(avg_vol) > float(p["max_pullback_vol_ratio"]):
                continue
            tests = self.prior_tests(w, k)
            if tests < int(p["min_prior_tests"]):
                continue
            rank = row[RANK_COL]
            sig = self.build_signal(
                row,
                as_of,
                entry=float(close),
                stop=float(close) - float(p["stop_atr_mult"]) * float(atr),
                target=None,
                score=float(rank) if finite(rank) else 0.0,
                features={"touch_low": w["low"][k], FAST: fast, SLOW: slow, "prior_tests": tests, "atr_14": atr,
                          RANK_COL: rank, "max_hold_days": p["max_hold_days"]},
                notes=f"ema zone test #{tests + 1} {t - k} bar(s) ago, close {float(close):.2f} over the prior high; "
                f"exit close < {SLOW}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
