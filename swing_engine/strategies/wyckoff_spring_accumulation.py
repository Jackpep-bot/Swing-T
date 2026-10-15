"""Wyckoff accumulation entries (long): docs/strategies/wyckoff_spring_accumulation.md, catalog C26.

Trading-range box approximation from the card: TR = min low / max high of the 60 bars before the event bar, no wider
than 35% of price, after a decline of more than 15% over the 126 bars before the box.
- `spring_test` (Phase C): a spring in the last 10 bars (low under the TR low by at most 1 ATR, close back inside),
  then today is the first test: low holds the spring low (within 1 ATR of it) on below-average volume with the close
  in the upper half of the range. Stop spring low - 0.25 x atr_14; target TR high + TR height (measured-move proxy for
  the point-and-figure count).
- `lps` (Phase D): a sign of strength in the last 10 bars (close over the TR high on rvol >= 1.5), then today is
  the first quiet pullback (volume below average, close under the SOS close) that holds within -2% / +3% of the TR
  high. Stop pullback low - 0.25 x atr_14; target TR high + 2 x TR height.
Entry next open; `min_reward_risk` 3 (the nine buying tests' 3x). Exits: target, stop, a close below sma_50 once
markup had `markup_bars` sessions, or 60 sessions. Not built: P&F count, the other buying tests, the phase labels.
"""
from __future__ import annotations

from datetime import date
from typing import Any, NamedTuple

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "wyckoff_spring_accumulation"
COLS = ("high", "low", "close", "volume", "avg_vol_20d", "atr_14")


class Box(NamedTuple):
    low: float
    high: float


@register("strategy", NAME)
class WyckoffSpringAccumulation(PanelStrategy):
    name = NAME
    description = "Trading-range box after a decline: buy the first low-volume test of a spring, or the LPS after an SOS."
    default_params: dict[str, Any] = {
        "entries": ["spring_test", "lps"],  # card: two signal types, logged separately
        "tr_bars": 60,  # card: TR box over the prior 60 bars
        "max_tr_width": 0.35,  # card: (tr_high - tr_low) / close <= 0.35
        "decline_bars": 126,  # card: prior decline ret_126d < -0.15 measured at TR start
        "max_prior_ret": -0.15,
        "event_window": 10,  # card: spring within the last 10 bars (same window for the SOS)
        "max_spring_depth_atr": 1.0,  # card: spring depth <= 1 ATR below the TR low
        "test_max_dist_atr": 1.0,  # engine choice: the test low is within 1 ATR of the spring low
        "test_close_pos_min": 0.5,  # card: close in the upper half
        "sos_rvol_min": 1.5,  # card: SOS close > TR high with rvol >= 1.5
        "lps_min_frac": 0.98,  # card: LPS low >= tr_high x 0.98
        "lps_max_frac": 1.03,  # engine choice: the pullback reaches within 3% of the old TR high
        "stop_atr_buffer": 0.25,  # card: stop = spring / pullback low - 0.25 x atr_14
        "spring_target_heights": 1.0,  # card: target tr_high + (tr_high - tr_low)
        "lps_target_heights": 2.0,  # card: target tr_high + 2 x (tr_high - tr_low)
        "exit_ma": "sma_50",  # card: close < sma_50 after markup
        "markup_bars": 10,  # engine choice: "after markup" = held at least 10 sessions
        "max_hold_days": 60,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: springs allowed in choppy; router gates LPS
        P_MIN_RR: 3.0,  # card: min_reward_risk 3.0
    }
    features_required = [*COLS[4:], "sma_50"]

    def required_features(self) -> list[str]:
        return list(dict.fromkeys([*self.features_required, str(self.params["exit_ma"])]))

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        ma = row.get(str(self.params["exit_ma"]))
        return bars_held >= int(self.params["markup_bars"]) and finite(ma) and float(row["close"]) < float(ma)

    def box(self, w: dict[str, np.ndarray], s: int) -> Box | None:
        """TR box of the bars before ``s`` when it is narrow enough and follows a decline."""
        p = self.params
        start = s - int(p["tr_bars"])
        back = start - int(p["decline_bars"])
        if back < 0:
            return None
        lo, hi = float(np.min(w["low"][start:s])), float(np.max(w["high"][start:s]))
        c = w["close"]
        if (hi - lo) / c[s] > float(p["max_tr_width"]) or not c[start] / c[back] - 1.0 < float(p["max_prior_ret"]):
            return None
        return Box(lo, hi)

    def _spring_test(self, w: dict[str, np.ndarray], t: int) -> tuple[float, Box, int] | None:
        p, lo, cl = self.params, w["low"], w["close"]
        for s in range(t - 1, max(t - 1 - int(p["event_window"]), 0), -1):
            b = self.box(w, s)
            if b is None or not (lo[s] < b.low < cl[s]) or b.low - lo[s] > float(p["max_spring_depth_atr"]) * w["atr_14"][s]:
                continue
            tests = [k for k in range(s + 1, t + 1) if self._is_test(w, k, lo[s])]
            return (float(lo[s]), b, s) if tests and tests[0] == t else None
        return None

    def _is_test(self, w: dict[str, np.ndarray], k: int, spring_low: float) -> bool:
        p, hi, lo, cl = self.params, w["high"], w["low"], w["close"]
        rng = hi[k] - lo[k]
        pos = (cl[k] - lo[k]) / rng if rng > 0 else np.nan
        return bool(spring_low <= lo[k] <= spring_low + float(p["test_max_dist_atr"]) * w["atr_14"][k]
                    and w["volume"][k] < w["avg_vol_20d"][k] and pos >= float(p["test_close_pos_min"]))

    def _lps(self, w: dict[str, np.ndarray], t: int) -> tuple[float, Box, int] | None:
        p, lo, cl, vol, avg = self.params, w["low"], w["close"], w["volume"], w["avg_vol_20d"]
        for o in range(t - 1, max(t - 1 - int(p["event_window"]), 0), -1):
            b = self.box(w, o)
            # rvol_day: volume over the prior bar's 20-day average (box() is None unless o >= tr_bars + decline_bars, so o >= 1)
            if b is None or not (cl[o] > b.high and avg[o - 1] > 0 and vol[o] / avg[o - 1] >= float(p["sos_rvol_min"])):
                continue
            ok = [k for k in range(o + 1, t + 1)
                  if b.high * float(p["lps_min_frac"]) <= lo[k] <= b.high * float(p["lps_max_frac"])
                  and vol[k] < avg[k] and cl[k] < cl[o]]
            return (float(np.min(lo[o + 1 : t + 1])), b, o) if ok and ok[0] == t else None
        return None

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        view = as_of_view(panel, as_of, ["open", *COLS, *self.required_features()])
        kinds = list(p["entries"])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            w = view.window(str(row[SYMBOL]), COLS)
            t = len(w["close"]) - 1
            for kind in kinds:
                hit = self._spring_test(w, t) if kind == "spring_test" else self._lps(w, t) if kind == "lps" else None
                if hit is None:
                    continue
                base, b, ev = hit
                heights = float(p["spring_target_heights"] if kind == "spring_test" else p["lps_target_heights"])
                close, atr = float(w["close"][t]), float(w["atr_14"][t])
                sig = self.build_signal(
                    row, as_of, entry=close, stop=base - float(p["stop_atr_buffer"]) * atr,
                    target=b.high + heights * (b.high - b.low), score=(b.high - b.low) / close,
                    features={"tr_low": b.low, "tr_high": b.high, "event_age": t - ev, "lps": float(kind == "lps"),
                              "max_hold_days": p["max_hold_days"]},
                    notes=f"Wyckoff {kind}: TR {b.low:.2f}-{b.high:.2f}, event {t - ev} bar(s) ago, base {base:.2f}",
                )
                if sig:
                    out.append(sig)
                    break  # one signal per symbol per day
        self.log_scan(as_of, len(view.current), len(out))
        return out
