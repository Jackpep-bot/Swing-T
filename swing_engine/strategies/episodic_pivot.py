"""Episodic pivot, delayed day-2 entry (long): docs/methods.md section 7b #5, docs/methods/02-episodic-pivot.md.

Rules: day 1 (the EP day) gaps up 10%+ (Kullamagi) on rvol >= 3 (Bonde's 3x+ volume) and closes in the upper half
of its range, after a neglected period (the 126-bar return up to the bar BEFORE the gap is <= 30%) and with no
other EP in the prior 252 bars. On day 2 the stock must trade above the day-1 high; daily bars cannot see the
intraday break, so the trigger is a day-2 close above the day-1 high and the backtest / execution fills it at the
next open. Stop = the day-1 low; skip the trade when that is more than 1.5 ADR below the entry (doc 02 "max
1-1.5 ADR"). Exit: first close below the 10-day SMA once 3 bars have passed (doc 02 "trail the 10/20-day"; use
`trail_ma: sma_20` for the slower variant), plus a time stop. Catalyst quality is not modelled: no point-in-time
earnings/news dates exist in the panel, so `features["catalyst_verified"]` is 0 (methods.md 8 #3).
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
    TREND_DOWN,
    TREND_FLAT,
    PanelStrategy,
    finite,
)

NAME = "episodic_pivot"
ADR_COL = "adr_pct_20"
NEGLECT_COL = "ret_126d"
ARRAYS = ("high", "low", "close", "gap_pct", "rvol_day", NEGLECT_COL)
CATALYST_VERIFIED = 0.0  # no point-in-time catalyst data in the panel (methods.md 8 #3)


@register("strategy", NAME)
class EpisodicPivot(PanelStrategy):
    name = NAME
    description = "Day-2 EP: 10%+ gap on 3x rvol after a neglected 126 bars; close over the day-1 high; stop day-1 low."
    default_params: dict[str, Any] = {
        "min_gap_pct": 0.10,  # doc 02: gap of at least 10% (Kullamagi)
        "min_rvol": 3.0,  # doc 02 / methods.md 7b #5: rvol_day >= 3 on the EP day
        "min_close_pos": 0.5,  # methods.md 7b #5: EP-day close in the upper half (gap not faded)
        "neglect_max_ret": 0.30,  # methods.md 7b #5: prior-row ret_126d <= 30% (no rally in the prior 3-6 months)
        "repeat_lookback": 252,  # methods.md 7b #5: no EP in the prior 252 bars
        "max_stop_adr": 1.5,  # doc 02: stop low of day, max 1-1.5 ADR -> skip wider setups
        "trail_ma": "sma_10",  # doc 02: trail the 10/20-day (sma_20 = slower variant)
        "trail_after_bars": 3,  # doc 02 / methods.md 7b #5: trail after 3 bars
        "target_r": 10.0,  # reference target only (doc 05 framework: "10-20x+ your initial risk"); trail exits
        "max_hold_days": 60,  # doc 02 proposed max_hold_days=60
        P_MIN_TREND: TREND_DOWN,  # neglected names are often flat or down before the pivot
        P_MIN_MARKET_TREND: TREND_FLAT,  # doc 02 proposed min_market_trend_state=0
        P_MIN_RR: 2.0,
    }
    features_required = ["gap_pct", "rvol_day", "close_pos", "trend_state", NEGLECT_COL, ADR_COL]

    def required_features(self) -> list[str]:
        return [*self.features_required, str(self.params["trail_ma"])]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        if bars_held < int(self.params["trail_after_bars"]):
            return False
        ma = row.get(str(self.params["trail_ma"]))
        return finite(ma) and float(row["close"]) < float(ma)

    def _is_ep(self, gap: np.ndarray, rvol: np.ndarray) -> np.ndarray:
        with np.errstate(invalid="ignore"):
            return (gap >= float(self.params["min_gap_pct"])) & (rvol >= float(self.params["min_rvol"]))

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        view = as_of_view(panel, as_of, ["open", *ARRAYS, *self.required_features()])
        cur = view.current
        frame = view.frame
        prior = cur.index.to_numpy() - 1
        same = (prior >= 0) & (frame[SYMBOL].to_numpy()[np.maximum(prior, 0)] == cur[SYMBOL].to_numpy())
        safe = np.maximum(prior, 0)
        day1 = same & self._is_ep(view.array("gap_pct")[safe], view.array("rvol_day")[safe])
        day1 &= frame["close_pos"].to_numpy(dtype=float, na_value=np.nan)[safe] >= float(p["min_close_pos"])
        day1 &= cur["close"].to_numpy() > view.array("high")[safe]
        out: list[Signal] = []
        for (_, row), ok in zip(cur.iterrows(), day1, strict=True):
            if not ok or not self.trend_ok(row):
                continue
            w = view.window(str(row[SYMBOL]), ARRAYS)
            t = len(w["close"]) - 1
            e = t - 1
            neglect = w[NEGLECT_COL][e - 1] if e >= 1 else np.nan
            if not (finite(neglect) and neglect <= float(p["neglect_max_ret"])):
                continue
            lo = max(0, e - int(p["repeat_lookback"]))
            if self._is_ep(w["gap_pct"][lo:e], w["rvol_day"][lo:e]).any():
                continue  # a recent EP already moved this stock (doc 02: higher failure rate)
            close, stop, adr = float(w["close"][t]), float(w["low"][e]), row[ADR_COL]
            if not finite(adr) or close - stop > float(p["max_stop_adr"]) * float(adr) * close:
                continue
            sig = self.build_signal(
                row,
                as_of,
                entry=close,
                stop=stop,
                target=close + float(p["target_r"]) * (close - stop),
                score=float(w["rvol_day"][e]) * (1.0 + float(w["gap_pct"][e])),
                features={
                    "catalyst_verified": CATALYST_VERIFIED,
                    "ep_gap_pct": w["gap_pct"][e],
                    "ep_rvol": w["rvol_day"][e],
                    "ep_high": w["high"][e],
                    "ep_low": stop,
                    "prior_ret_126d": neglect,
                    ADR_COL: adr,
                    "stop_adr": (close - stop) / (float(adr) * close) if float(adr) > 0 else np.nan,
                    "max_hold_days": p["max_hold_days"],
                },
                notes=f"day-2 EP (catalyst not verified): day-1 gap {w['gap_pct'][e] * 100:+.1f}% on "
                f"{w['rvol_day'][e]:.1f}x rvol after {neglect * 100:+.0f}% over 126 bars; close {close:.2f} > "
                f"day-1 high {w['high'][e]:.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(cur), len(out))
        return out
