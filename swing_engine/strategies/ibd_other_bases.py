"""IBD / MarketSurge other bases (long): double bottom and ascending base, docs/strategies/ibd_other_bases.md
(catalog P66/P67); variants of `base_breakout` (catalog maps_to), which supplies the breakout, stop, target and
exits unchanged (prior advance 30%+, volume >= 1.4x the prior 50-day average, <= 5% above the pivot, RS rank 80+,
stop max(base floor, entry x 0.93), +20% target, heavy-volume sma_50 exit, 40-session cap, M gate on).

Double bottom: a W whose second swing low undercuts the first, at least 35 bars from the left-side high, no more
than 33% deep (card, unverified depth); pivot = the middle peak; floor = the second low; a confirmed handle (swing
high <= the middle peak, swing low above the second low) moves the pivot to the handle high and the floor to the
handle low. Ascending base: three pullbacks of 10-20% each with higher highs and higher lows over 45-80 bars; pivot
= the high before the third pullback; floor = the third low. Swing points come from `_swing.swing_pivots` (confirmed
`swing_width` bars after the pivot). Both must be the first close over the pivot since the last low. Saucer and
consolidation are left out (card: no verified numbers). The pivot is crossed at the close (no intraday stop entry),
as in base_breakout.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from swing_engine.core.registry import register
from swing_engine.features.patterns2 import prior_advance

from ._base import finite
from ._swing import swing_pivots, trim_to_last_low
from .base_breakout import BaseBreakout, _Base

NAME = "ibd_other_bases"
VARIANT_DOUBLE = "double_bottom"
VARIANT_ASCENDING = "ascending_base"
ASCENDING_PULLBACKS = 3  # card: three pullbacks


@register("strategy", NAME)
class IbdOtherBases(BaseBreakout):
    name = NAME
    description = "Double-bottom (middle-peak pivot) or ascending-base breakout with base_breakout's entry and exits."
    default_params: dict[str, Any] = {
        **BaseBreakout.default_params,
        "swing_width": 5,  # bars each side that confirm a swing high / low (engine choice, one trading week)
        "db_min_bars": 35,  # card: double bottom at least ~7 weeks
        "db_max_bars": 325,  # same 65-week cap as base_breakout's cup
        "db_max_depth": 0.33,  # card: unverified depth limit
        "db_undercut_min": 0.0,  # card: the second low must undercut the first (even slightly)
        "db_handle": True,  # card: a handle variant moves the pivot to the handle high
        "ab_depth_min": 0.10,  # card: each pullback 10-20%
        "ab_depth_max": 0.20,
        "ab_min_bars": 45,  # card: about 9-16 weeks
        "ab_max_bars": 80,
    }

    def _pivots(self, w: dict[str, np.ndarray], end: int, max_bars: int) -> list[tuple[str, int, float]]:
        start = max(0, end - max_bars + 1)
        return trim_to_last_low(swing_pivots(w["high"], w["low"], start, end, int(self.params["swing_width"])))

    @staticmethod
    def _fresh(w: dict[str, np.ndarray], low_idx: int, floor: float, pivot: float, end: int) -> bool:
        """No undercut of the floor and no close over the pivot between the last low and ``end``."""
        lows, closes = w["low"][low_idx : end + 1], w["close"][low_idx + 1 : end + 1]
        return bool(lows.min() >= floor and (closes.size == 0 or closes.max() <= pivot))

    def _double_bottom(self, w: dict[str, np.ndarray], end: int) -> _Base | None:
        p = self.params
        seq = self._pivots(w, end, int(p["db_max_bars"]))
        handle = None
        if bool(p["db_handle"]) and len(seq) >= 5 and seq[-1][2] > seq[-3][2] and seq[-2][2] <= seq[-4][2]:
            handle, seq = seq[-2:], seq[:-2]
        if len(seq) < 3:
            return None
        (_, i1, l1), (_, _, mid), (_, _, l2) = seq[-3:]
        if not l2 < l1 * (1.0 - float(p["db_undercut_min"])):
            return None
        start = max(0, end - int(p["db_max_bars"]) + 1)
        seg = w["high"][start : i1 + 1]
        if not np.isfinite(seg).all():
            return None
        top_idx = start + int(np.argmax(seg))
        top = float(w["high"][top_idx])
        length, depth = end - top_idx + 1, (top - l2) / top
        if length < int(p["db_min_bars"]) or depth > float(p["db_max_depth"]) or mid >= top:
            return None
        (_, _, pivot), (_, low_idx, floor) = handle or (seq[-2], seq[-1])
        if not self._fresh(w, low_idx, floor, pivot, end):
            return None
        return _Base(VARIANT_DOUBLE, pivot, floor, top_idx, top, length, depth)

    def _ascending(self, w: dict[str, np.ndarray], end: int) -> _Base | None:
        p = self.params
        seq = self._pivots(w, end, int(p["ab_max_bars"]))
        if len(seq) < 2 * ASCENDING_PULLBACKS:
            return None
        legs = seq[-2 * ASCENDING_PULLBACKS :]
        highs, lows = [x[2] for x in legs[0::2]], [x[2] for x in legs[1::2]]
        if np.any(np.diff(highs) <= 0) or np.any(np.diff(lows) <= 0):
            return None
        depths = [(h - lo) / h for h, lo in zip(highs, lows, strict=True)]
        if not all(float(p["ab_depth_min"]) <= d <= float(p["ab_depth_max"]) for d in depths):
            return None
        start, length = legs[0][1], end - legs[0][1] + 1
        if not int(p["ab_min_bars"]) <= length <= int(p["ab_max_bars"]):
            return None
        pivot, floor, low_idx = highs[-1], lows[-1], legs[-1][1]
        if not self._fresh(w, low_idx, floor, pivot, end):
            return None
        return _Base(VARIANT_ASCENDING, pivot, floor, start, highs[0], length, max(depths))

    def find_base(self, w: dict[str, np.ndarray]) -> _Base | None:
        end = len(w["close"]) - 2
        for found in (self._double_bottom(w, end), self._ascending(w, end)):
            if found is None:
                continue
            adv = prior_advance(w["low"], found.top, found.start, int(self.params["advance_lookback"]))
            if finite(adv) and adv >= float(self.params["prior_advance_min"]):
                return found
        return None
