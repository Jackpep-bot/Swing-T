"""Classic base breakout (long): cup with handle or flat base, O'Neil / Bulkowski rules (docs/methods.md 7b #2).

Rules (docs/methods/04-chart-pattern-base-breakouts.md, "Rules" and "Automatability"): a leader with a prior
advance of 30%+ into the base; a cup at least 7 weeks long and 12-33% deep whose handle (1-5 weeks, no more than
12% deep, on light volume) sits in the upper half of the cup, or a flat base of 5+ weeks no more than 15% deep;
buy the close above the pivot (handle high / base high) on volume >= 1.4x the prior 50-day average, but not more
than 5% above the pivot. Stop = the higher of the handle/base low and entry - 7% (O'Neil 7-8%); target +20%
(IBD 20-25%). `max_hold_days` (40) is a plain time cap, NOT the IBD 8-week rule: doc 04's eight_week_rule (a +20%
gain within ~15 bars means hold at least 40 bars and trail on a close below sma_50) is not implemented, because
`should_exit(row, bars_held)` sees neither the entry price nor the path since entry; the fixed +20% target sells
exactly the fast movers that rule would hold. A close below the 50-day on heavy volume is the failure exit
(methods.md 2f). Geometry comes from features/patterns2.py (`cup_with_handle`, `flat_base`).
"""
from __future__ import annotations

from datetime import date
from typing import Any, NamedTuple

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view, cup_with_handle, flat_base, prior_advance

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

NAME = "base_breakout"
VARIANT_CUP = "cup_handle"
VARIANT_FLAT = "flat_base"
VOL_RATIO_COL = "vol_ratio_50d_prev"
AVG_VOL_PREV_COL = "avg_vol_50d_prev"
RS_COL = "rs_63d_rank"
ARRAYS = ("high", "low", "close", "volume", VOL_RATIO_COL, AVG_VOL_PREV_COL)


class _Base(NamedTuple):
    variant: str
    pivot: float
    floor: float  # handle low (cup) or base low (flat): the structural stop
    start: int  # left lip / first base bar (prior advance is measured before it)
    top: float  # left-lip high / base high
    length: int
    depth: float


@register("strategy", NAME)
class BaseBreakout(PanelStrategy):
    name = NAME
    description = "Cup-with-handle or flat-base pivot breakout on >= 1.4x volume, <= 5% extended; 7% stop, +20% target."
    default_params: dict[str, Any] = {
        "prior_advance_min": 0.30,  # doc 04: prior advance of 30%+ into the base (O'Neil)
        "advance_lookback": 126,  # doc 04: advance measured over the 63-126 bars before the base starts
        "cup_min_bars": 35,  # doc 04 / methods.md 7b: cup at least 7 weeks
        "cup_max_bars": 325,  # doc 04: 7-65 week cups
        "cup_depth_min": 0.12,  # doc 04: cup 12-33% deep
        "cup_depth_max": 0.33,
        "handle_min_bars": 5,  # doc 04: handle 1-3 weeks (proposed handle_min_bars=5, handle_max_bars=25)
        "handle_max_bars": 25,
        "handle_depth_max": 0.12,  # doc 04: handle no more than ~12% deep
        "handle_upper_half": True,  # doc 04: handle low above the cup midpoint
        "handle_vol_ratio_max": 1.0,  # doc 04: light handle volume (mean handle volume / prior 50-day average)
        "flat_min_bars": 25,  # methods.md 2c: flat base 5+ weeks
        "flat_max_bars": 325,  # same 65-week cap as the cup
        "flat_depth_max": 0.15,  # methods.md 2c: no more than 15% deep
        "breakout_vol_mult": 1.4,  # methods.md 7b: volume >= 1.4x avg_vol_50d_prev
        "max_extension": 0.05,  # methods.md 2d: buy within 5% of the pivot (IBD, Minervini)
        "rs_rank_min": 0.80,  # doc 04 proposed rs_rank_min=0.80 (63-day return percentile); None = off
        "stop_pct": 0.07,  # doc 04: stop 7-8% below the buy point (the higher of this and the handle low)
        "target_pct": 0.20,  # doc 04 / methods.md 2f: take 20-25%
        "max_hold_days": 40,  # time cap on every trade (not the IBD 8-week rule; see the module docstring)
        "exit_ma": "sma_50",  # methods.md 2f failure exit: a close below the 50-day on heavy volume
        "exit_volume_mult": 1.4,  # "heavy" = the same 40%-above-average bar the entry requires (doc 04)
        P_MIN_TREND: TREND_FLAT,
        P_MIN_MARKET_TREND: TREND_UP,  # doc 04 proposed min_market_trend_state=1 (M gate on)
        P_MIN_RR: 2.0,
    }
    features_required = ["trend_state", "avg_vol_50d", VOL_RATIO_COL, AVG_VOL_PREV_COL, RS_COL]

    def required_features(self) -> list[str]:
        return [*self.features_required, str(self.params["exit_ma"])]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        ma, avg = row.get(str(self.params["exit_ma"])), row.get("avg_vol_50d")
        if not (finite(ma) and finite(avg)) or float(row["close"]) >= float(ma):
            return False
        return float(row["volume"]) >= float(self.params["exit_volume_mult"]) * float(avg)

    # ------------------------------------------------------------------------------------- base detection
    def _cup(self, w: dict[str, np.ndarray], end: int) -> _Base | None:
        p = self.params
        cup = cup_with_handle(
            w["high"],
            w["low"],
            end,
            cup_min_bars=int(p["cup_min_bars"]),
            cup_max_bars=int(p["cup_max_bars"]),
            handle_min_bars=int(p["handle_min_bars"]),
            handle_max_bars=int(p["handle_max_bars"]),
        )
        if cup is None or not float(p["cup_depth_min"]) <= cup.depth <= float(p["cup_depth_max"]):
            return None
        if cup.handle_depth > float(p["handle_depth_max"]):
            return None
        if bool(p["handle_upper_half"]) and cup.handle_low <= (cup.lip + cup.cup_low) / 2.0:
            return None
        avg = w[AVG_VOL_PREV_COL][end + 1]
        handle_vol = float(np.mean(w["volume"][cup.right : end + 1]))
        if not finite(avg) or avg <= 0 or handle_vol / avg > float(p["handle_vol_ratio_max"]):
            return None
        return _Base(VARIANT_CUP, cup.pivot, cup.handle_low, cup.left, cup.lip, cup.cup_len, cup.depth)

    def _flat(self, w: dict[str, np.ndarray], end: int) -> _Base | None:
        p = self.params
        base = flat_base(w["high"], w["low"], end, float(p["flat_depth_max"]), int(p["flat_max_bars"]))
        if base is None or base.length < int(p["flat_min_bars"]):
            return None
        return _Base(VARIANT_FLAT, base.top, base.low, base.start, base.top, base.length, base.depth)

    def find_base(self, w: dict[str, np.ndarray]) -> _Base | None:
        """The base ending the bar before the last element of ``w`` (cup first, then flat), advance checked."""
        end = len(w["close"]) - 2
        for found in (self._cup(w, end), self._flat(w, end)):
            if found is None:
                continue
            adv = prior_advance(w["low"], found.top, found.start, int(self.params["advance_lookback"]))
            if finite(adv) and adv >= float(self.params["prior_advance_min"]):
                return found
        return None

    # ------------------------------------------------------------------------------------- scan
    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        view = as_of_view(panel, as_of, ["open", *ARRAYS, *self.required_features()])
        cur = view.current
        vol_mult = float(self.params["breakout_vol_mult"])
        rs_min = self.params.get("rs_rank_min")
        keep = cur[VOL_RATIO_COL] >= vol_mult
        if finite(rs_min):
            keep &= cur[RS_COL] >= float(rs_min)
        max_ext = float(self.params["max_extension"])
        stop_pct, target_pct = float(self.params["stop_pct"]), float(self.params["target_pct"])
        out: list[Signal] = []
        for _, row in cur.loc[keep.fillna(False)].iterrows():
            if not self.trend_ok(row):
                continue
            w = view.window(str(row[SYMBOL]), ARRAYS)
            base = self.find_base(w)
            if base is None:
                continue
            close = float(row["close"])
            extension = close / base.pivot - 1.0
            if extension <= 0 or extension > max_ext:
                continue
            stop = max(base.floor, close * (1.0 - stop_pct))
            vol_ratio = float(row[VOL_RATIO_COL])
            sig = self.build_signal(
                row,
                as_of,
                entry=close,
                stop=stop,
                target=close * (1.0 + target_pct),
                score=vol_ratio + float(row[RS_COL]) if finite(row[RS_COL]) else vol_ratio,
                features={
                    "is_cup_handle": float(base.variant == VARIANT_CUP),
                    "pivot": base.pivot,
                    "base_low": base.floor,
                    "base_len": base.length,
                    "base_depth": base.depth,
                    "extension": extension,
                    "volume_ratio": vol_ratio,
                    RS_COL: row[RS_COL],
                    "max_hold_days": self.params["max_hold_days"],
                },
                notes=f"{base.variant} breakout: close {close:.2f} {extension * 100:+.1f}% over pivot "
                f"{base.pivot:.2f} on {vol_ratio:.1f}x vol; base {base.length} bars {base.depth * 100:.0f}% deep",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(cur), len(out))
        return out
