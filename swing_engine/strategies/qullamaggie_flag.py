"""Qullamaggie flag breakout (long): docs/methods.md section 7b #4, docs/methods/05-qullamaggie-breakout.md.

Rules: a top-2% momentum leader (63-day return percentile >= 0.98) that rose 30%+ within about 2 months (the
pole, measured into the flag high), with ADR >= 5%; a 10-40 bar flag after the pole top, no more than about 25%
deep (Soreide, methods.md 2c), with higher lows, while the 10- and 20-day SMAs rise and price holds above the
20-day. Trigger = close above the flag high on rvol >= 1.5, no more than 1 ADR above the pivot (doc 05 "when a
stock is up more than its ATR you do not buy it"). Stop = the entry-day low, never wider than 1 ADR. Kullamagi
sells 1/3-1/2 after 3-5 days; the engine has no scale-out hook, so the whole position trails on the first close
below the 20-day SMA (`should_exit`), with a far reference target and a time stop.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view, flag, prior_advance

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

NAME = "qullamaggie_flag"
RS_COL = "rs_63d_rank"
ADR_COL = "adr_pct_20"


@register("strategy", NAME)
class QullamaggieFlag(PanelStrategy):
    name = NAME
    description = "Top-2% RS leader, 30%+ pole, ADR >= 5%, 10-40 bar flag on rising 10/20 SMA; buy the flag-high break."
    default_params: dict[str, Any] = {
        "rs_rank_min": 0.98,  # doc 05 / methods.md 7b #4: top 1-2% performers (rank_ret_63d >= 98th pct)
        "prior_move_min": 0.30,  # doc 05: "a big move higher ... 30-100%+"
        "pole_max_bars": 42,  # task / methods.md 2b: the move happened within <= 2 months (~42 sessions)
        "adr_min": 0.05,  # methods.md 2b: ADR% above 5
        "flag_min_bars": 10,  # methods.md 7b #4: 10-40 bar flag
        "flag_max_bars": 40,
        "flag_depth_max": 0.25,  # methods.md 2c (Soreide): flag no deeper than about 25%
        "require_higher_lows": True,  # methods.md 7b #4: "flag with higher lows"
        "ma_fast": "sma_10",  # doc 05: price surfs the rising 10/20-day MAs
        "ma_slow": "sma_20",
        "ma_slope_bars": 5,  # "rising" = above its value 5 bars earlier (features/regime.py slope lookback)
        "breakout_rvol_min": 1.5,  # methods.md 7b #4: rvol_day >= 1.5
        "max_extension_adr": 1.0,  # methods.md 7b #4: no more than 1 ADR above the pivot
        "max_stop_adr": 1.0,  # doc 05: stop at the low of the day, never wider than the ADR
        "trail_ma": "sma_20",  # methods.md 7b #4: trail on a close < sma_20 (1/3 off at bar 4 is not modelable)
        "target_r": 10.0,  # reference target only (doc 05: "10-20x+ your initial risk"); the MA trail exits
        "max_hold_days": 60,  # weeks-long holds for winners (doc 05 holding period); same cap as doc 02/13
        P_MIN_TREND: TREND_FLAT,
        P_MIN_MARKET_TREND: TREND_UP,  # doc 05 proposed min_market_trend_state=1
        P_MIN_RR: 2.0,
    }
    features_required = ["rvol_day", "trend_state", RS_COL, ADR_COL]

    def required_features(self) -> list[str]:
        mas = {str(self.params[k]) for k in ("ma_fast", "ma_slow", "trail_ma")}
        return [*self.features_required, *sorted(mas)]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        ma = row.get(str(self.params["trail_ma"]))
        return finite(ma) and float(row["close"]) < float(ma)

    def _mas_rising(self, w: dict[str, np.ndarray], t: int) -> bool:
        back = t - int(self.params["ma_slope_bars"])
        if back < 0:
            return False
        for col in (str(self.params["ma_fast"]), str(self.params["ma_slow"])):
            now, then = w[col][t], w[col][back]
            if not (finite(now) and finite(then) and now > then):
                return False
        return True

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        fast, slow = str(p["ma_fast"]), str(p["ma_slow"])
        arrays = ("high", "low", "close", fast, slow)
        view = as_of_view(panel, as_of, ["open", *arrays, *self.required_features()])
        cur = view.current
        keep = (
            (cur[RS_COL] >= float(p["rs_rank_min"]))
            & (cur[ADR_COL] >= float(p["adr_min"]))
            & (cur["rvol_day"] >= float(p["breakout_rvol_min"]))
            & (cur["close"] > cur[slow])
            & (cur[fast] >= cur[slow])
        ).fillna(False)
        out: list[Signal] = []
        for _, row in cur.loc[keep].iterrows():
            if not self.trend_ok(row):
                continue
            w = view.window(str(row[SYMBOL]), arrays)
            t = len(w["close"]) - 1
            fl = flag(w["high"], w["low"], t - 1, int(p["flag_max_bars"]))
            if fl is None or fl.length < int(p["flag_min_bars"]) or fl.depth > float(p["flag_depth_max"]):
                continue
            if bool(p["require_higher_lows"]) and not fl.higher_lows:
                continue
            close, adr = float(w["close"][t]), float(row[ADR_COL])
            if close <= fl.pivot or close - fl.pivot > float(p["max_extension_adr"]) * adr * close:
                continue
            pole = prior_advance(w["low"], fl.pivot, fl.top_idx + 1, int(p["pole_max_bars"]))
            if not (finite(pole) and pole >= float(p["prior_move_min"])) or not self._mas_rising(w, t):
                continue
            stop = max(float(w["low"][t]), close * (1.0 - float(p["max_stop_adr"]) * adr))
            sig = self.build_signal(
                row,
                as_of,
                entry=close,
                stop=stop,
                target=close + float(p["target_r"]) * (close - stop),
                score=float(row[RS_COL]) + pole,
                features={
                    "pivot": fl.pivot,
                    "flag_len": fl.length,
                    "flag_depth": fl.depth,
                    "pole_gain": pole,
                    RS_COL: row[RS_COL],
                    ADR_COL: adr,
                    "rvol_day": row["rvol_day"],
                    "extension_adr": (close - fl.pivot) / (adr * close) if adr > 0 else np.nan,
                    "max_hold_days": p["max_hold_days"],
                },
                notes=f"flag breakout: {fl.length}-bar flag {fl.depth * 100:.0f}% deep after a {pole * 100:.0f}% pole; "
                f"close {close:.2f} > {fl.pivot:.2f}, RS {float(row[RS_COL]):.2f}, ADR {adr * 100:.1f}%",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(cur), len(out))
        return out
