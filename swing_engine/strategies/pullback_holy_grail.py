"""Raschke/Connors "Holy Grail" pullback (long), the pullback-family variant of docs/methods.md section 7b #1.

Rules (docs/methods/01-pullback-20-50-ma-uptrend.md, Holy Grail rows): the 14-period ADX is "initially above 30
and rising" with +DI > -DI (checked on the prior swing-high bar, i.e. before the retracement); price then
retraces so the bar low touches the 20 EMA (touch, not slice); the buy is "above the high of the candlestick"
that touched it, the stop "below its low", and the target the retest of the prior swing high. Daily bars have
no buy-stop orders, so the trigger is the first close above the touch-bar high (filled at the next open by the
backtest / execution), exactly as `pullback_trend` approximates its trigger. Hold 2-10 sessions (doc 01
"Holding period") via `max_hold_days`; the 20/50/ADX columns come from features/patterns2.py.

Leaders only (docs/methods.md 6.1 rules, 3c "leaders-only, RS-filtered pullbacks"): trend_state must be up
(close > sma_50 > sma_200, sma_50 rising) and the name must be a leader, `rs_63d_rank >= rs_rank_min` (RS 96+)
or within `max_dist_52w_high_pct` of its 52-week high. Either leader param set to None drops that test; both
None turns the leader gate off.
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

NAME = "pullback_holy_grail"
ADX_COL = "adx_14"
PLUS_DI_COL = "plus_di_14"
MINUS_DI_COL = "minus_di_14"
RS_COL = "rs_63d_rank"  # features/patterns2.py: same-session percentile of the 63-bar return
DIST_HIGH_COL = "dist_52w_high"  # features/cross_section.py: close / high_52w - 1
PCT = 100.0
BAR_ARRAYS = ("high", "low", "close")


@register("strategy", NAME)
class PullbackHolyGrail(PanelStrategy):
    name = NAME
    description = "ADX14 > 30 rising, low touches ema_20, close over touch-bar high; stop touch low, target swing high."
    default_params: dict[str, Any] = {
        "pullback_ma": "ema_20",  # doc 01: "retraces to touch the 20 EMA" (tradingsetupsreview says 20 SMA: sma_20)
        "adx_min": 30.0,  # doc 01: 14-period ADX "initially above 30 and rising"
        "adx_rising_bars": 1,  # ADX at the swing-high bar must exceed its value this many bars earlier
        "touch_pct": 0.01,  # low <= ma * (1 + touch_pct) and close >= ma * (1 - touch_pct) (doc 01: within ~1-2%)
        "max_touch_age": 3,  # the touch bar is one of the last N bars before the as-of (trigger) bar
        "swing_high_bars": 20,  # prior swing high = highest high of the N bars before the touch bar (doc 01)
        "stop_atr_buffer": 0.0,  # stop = touch-bar low - buffer * atr_14 (doc 01: "below its low")
        "max_hold_days": 10,  # doc 01: Holy Grail to the swing high holds 2-10 sessions
        "exit_ma": None,  # optional rule exit on a close below this column (e.g. "sma_50"); None = time stop only
        P_MIN_TREND: TREND_UP,  # methods.md 6.1: close > SMA50 > SMA200 with the 50 rising (Landry proper order)
        "rs_rank_min": 0.96,  # methods.md 6.1: "RS rank 96+" ...
        "max_dist_52w_high_pct": 10.0,  # ... "or within 5-10% of the 52-week high" (leader test passes on either)
        P_MIN_MARKET_TREND: TREND_FLAT,
        P_MIN_RR: 1.0,  # target is the prior swing high, not an R multiple (doc 01); settings may raise it
    }
    features_required = ["atr_14", "trend_state", ADX_COL, PLUS_DI_COL, MINUS_DI_COL, RS_COL, DIST_HIGH_COL]

    def required_features(self) -> list[str]:
        cols = [*self.features_required, str(self.params["pullback_ma"])]
        exit_ma = self.params.get("exit_ma")
        return [*cols, str(exit_ma)] if exit_ma else cols

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        exit_ma = self.params.get("exit_ma")
        level = row.get(str(exit_ma)) if exit_ma else None
        return finite(level) and float(row["close"]) < float(level)

    def leader_ok(self, row: pd.Series) -> bool:
        """RS rank at or above ``rs_rank_min`` or close within ``max_dist_52w_high_pct`` of the 52-week high."""
        rs_min, max_dist = self.params.get("rs_rank_min"), self.params.get("max_dist_52w_high_pct")
        if rs_min is None and max_dist is None:
            return True
        rs, dist = row.get(RS_COL), row.get(DIST_HIGH_COL)
        if rs_min is not None and finite(rs) and float(rs) >= float(rs_min):
            return True
        return max_dist is not None and finite(dist) and float(dist) >= -float(max_dist) / PCT

    def _touch_bar(self, w: dict[str, np.ndarray], t: int, ma_col: str) -> int | None:
        touch = float(self.params["touch_pct"])
        for k in range(t - 1, max(-1, t - 1 - int(self.params["max_touch_age"])), -1):
            ma, low, close = w[ma_col][k], w["low"][k], w["close"][k]
            if not (finite(ma) and finite(low) and finite(close)):
                return None
            if low <= ma * (1.0 + touch) and close >= ma * (1.0 - touch):
                return k
        return None

    def _adx_ok(self, w: dict[str, np.ndarray], s: int) -> bool:
        back = s - int(self.params["adx_rising_bars"])
        if back < 0:
            return False
        adx_s, adx_b, pdi, mdi = w[ADX_COL][s], w[ADX_COL][back], w[PLUS_DI_COL][s], w[MINUS_DI_COL][s]
        if not all(finite(x) for x in (adx_s, adx_b, pdi, mdi)):
            return False
        return adx_s >= float(self.params["adx_min"]) and adx_s > adx_b and pdi > mdi

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        ma_col = str(self.params["pullback_ma"])
        cols = [*BAR_ARRAYS, ma_col, ADX_COL, PLUS_DI_COL, MINUS_DI_COL]
        view = as_of_view(panel, as_of, ["open", *cols, *self.required_features()])
        swing_n = int(self.params["swing_high_bars"])
        buffer = float(self.params["stop_atr_buffer"])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            if not self.trend_ok(row) or not self.leader_ok(row):
                continue
            w = view.window(str(row[SYMBOL]), cols)
            t = len(w["close"]) - 1
            k = self._touch_bar(w, t, ma_col)
            if k is None or k - swing_n < 0:
                continue
            touch_high, touch_low, close = w["high"][k], w["low"][k], w["close"][t]
            if not close > touch_high or (w["close"][k + 1 : t] > touch_high).any():
                continue  # not a trigger, or not the first close over the touch-bar high
            seg = w["high"][k - swing_n : k]
            if not np.isfinite(seg).all():
                continue
            s = k - swing_n + int(np.argmax(seg))
            if not self._adx_ok(w, s):
                continue
            atr = row["atr_14"]
            stop = touch_low - (buffer * float(atr) if finite(atr) else 0.0)
            swing_high = float(w["high"][s])
            risk = close - stop
            rr = (swing_high - close) / risk if risk > 0 else 0.0
            sig = self.build_signal(
                row,
                as_of,
                entry=close,
                stop=stop,
                target=swing_high,
                score=rr,
                features={
                    "pullback_ma": w[ma_col][k],
                    "touch_low": touch_low,
                    "touch_high": touch_high,
                    "touch_age": t - k,
                    "swing_high": swing_high,
                    "adx_14": w[ADX_COL][s],
                    "plus_di_14": w[PLUS_DI_COL][s],
                    "minus_di_14": w[MINUS_DI_COL][s],
                    RS_COL: row.get(RS_COL),
                    DIST_HIGH_COL: row.get(DIST_HIGH_COL),
                    "max_hold_days": self.params["max_hold_days"],
                },
                notes=f"Holy Grail: ADX {w[ADX_COL][s]:.0f} rising, touch {ma_col} {t - k} bar(s) ago, close "
                f"{close:.2f} > touch high {touch_high:.2f}; target swing high {swing_high:.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
