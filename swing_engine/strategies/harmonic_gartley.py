"""Bullish Gartley (long), Carney / ChartSchool: docs/strategies/harmonic_gartley.md, catalog P37.

Swings X (low) -> A (high) -> B (low) -> C (high) come from a causal zigzag of confirmed pivots (width 5, each known
5 bars later; consecutive same-side pivots keep the extreme). D is the lowest low since C, made 1-3 bars ago.
Ratios (tolerance 0.05): (A - D) / (A - X) = 0.786; (C - D) / (C - B) in [1.27, 1.618]; AB = CD within 5%.
Trigger: the first close above the D-bar high (the card's "confirmation" in place of a blind limit at D); entry
next open. Stop D - 0.25 x atr_14; target zone 1 = D + 0.618 x (A - X); 20-session time stop. Bat, Butterfly, Crab,
Shark and Cypher ratio matrices are not in the sources and are not built.
"""
from __future__ import annotations

from datetime import date
from typing import Any, NamedTuple

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "harmonic_gartley"


class Swing(NamedTuple):
    idx: int
    price: float
    high: bool


def zigzag(high: np.ndarray, low: np.ndarray, width: int, t: int) -> list[Swing]:
    """Alternating swing points from pivots confirmed by bar ``t`` (pivot i needs bars i-width .. i+width)."""
    span = 2 * width + 1
    if t + 1 < span:
        return []
    pts: list[Swing] = []
    for arr, is_high in ((high[: t + 1], True), (low[: t + 1], False)):
        win = sliding_window_view(arr, span)
        centre, others = win[:, width], np.delete(win, width, axis=1)
        mask = centre > others.max(axis=1) if is_high else centre < others.min(axis=1)
        pts += [Swing(int(i) + width, float(arr[int(i) + width]), is_high) for i in np.flatnonzero(mask)]
    out: list[Swing] = []
    for s in sorted(pts):
        if out and out[-1].high == s.high:
            better = s.price > out[-1].price if s.high else s.price < out[-1].price
            if better:
                out[-1] = s
            continue
        out.append(s)
    return out


@register("strategy", NAME)
class HarmonicGartley(PanelStrategy):
    name = NAME
    description = "Bullish Gartley XABCD from a causal zigzag; D at 0.786 XA; buy the first close over the D-bar high."
    default_params: dict[str, Any] = {
        "pivot_width": 5,  # card: causal zigzag, pivot width 5
        "tol": 0.05,  # card: ratio tolerance 0.05
        "xa_retrace": 0.786,  # card: D near the 0.786 retracement of XA
        "cd_bc_min": 1.27,  # card: CD = 1.27-1.618 x BC
        "cd_bc_max": 1.618,
        "d_max_age": 3,  # card: D is the lowest low of the last 1-3 bars
        "max_pattern_bars": 120,  # card: max pattern length 20-120 bars
        "stop_atr_buffer": 0.25,  # card: stop = D - 0.25 x atr_14
        "target_xa": 0.618,  # card: target = D + 0.618 x (A - X)
        "max_hold_days": 20,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,  # counter-trend entry; the router decides
        P_MIN_RR: 1.5,  # card: min_reward_risk 1.5
    }
    features_required = ["atr_14"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def match(self, high: np.ndarray, low: np.ndarray, close: np.ndarray) -> dict[str, float] | None:
        """Gartley points and ratios when bar ``len - 1`` triggers, else None."""
        p, t = self.params, len(close) - 1
        sw = zigzag(high, low, int(p["pivot_width"]), t)
        if len(sw) < 4 or not sw[-1].high:
            return None
        x, a, b, c = sw[-4:]
        if x.high or t - x.idx > int(p["max_pattern_bars"]) or c.idx >= t - 1:
            return None
        seg = low[c.idx + 1 : t + 1]
        d_idx = c.idx + 1 + int(np.argmin(seg))
        if not (t - int(p["d_max_age"]) <= d_idx < t):
            return None
        d = float(low[d_idx])
        if not (x.price < b.price < a.price and b.price < c.price < a.price and x.price < d < b.price):
            return None
        tol = float(p["tol"])
        xa, ab, bc, cd = a.price - x.price, a.price - b.price, c.price - b.price, c.price - d
        retr = (a.price - d) / xa
        if abs(retr - float(p["xa_retrace"])) > tol or not float(p["cd_bc_min"]) <= cd / bc <= float(p["cd_bc_max"]):
            return None
        if abs(ab - cd) / ab > tol:
            return None
        d_high = float(high[d_idx])
        if not close[t] > d_high or (close[d_idx + 1 : t] > d_high).any():
            return None  # not a trigger, or not the first close over the D-bar high
        return {"x": x.price, "a": a.price, "b": b.price, "c": c.price, "d": d, "xa_retrace": retr,
                "cd_bc": cd / bc, "ab_cd": cd / ab, "d_age": t - d_idx}

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        cols = ["high", "low", "close"]
        view = as_of_view(panel, as_of, ["open", *cols, *self.required_features()])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            w = view.window(str(row[SYMBOL]), cols)
            m = self.match(w["high"], w["low"], w["close"])
            if m is None or not finite(row["atr_14"]):
                continue
            close = float(row["close"])
            stop = m["d"] - float(p["stop_atr_buffer"]) * float(row["atr_14"])
            target = m["d"] + float(p["target_xa"]) * (m["a"] - m["x"])
            sig = self.build_signal(
                row, as_of, entry=close, stop=stop, target=target, score=-abs(m["xa_retrace"] - float(p["xa_retrace"])),
                features={**m, "max_hold_days": p["max_hold_days"]},
                notes=f"Gartley X {m['x']:.2f} A {m['a']:.2f} B {m['b']:.2f} C {m['c']:.2f} D {m['d']:.2f} "
                f"(XA {m['xa_retrace']:.3f}, CD/BC {m['cd_bc']:.2f}); close over D-bar high",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
