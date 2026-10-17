"""Minervini VCP / SEPA breakout (long), docs/strategies/vcp_sepa_breakout.md (methods.md 1a #7 and 6.3,
docs/methods/03-vcp-minervini-trend-template.md).

Trend Template (all 8): close > sma_150 and sma_200; sma_150 > sma_200; sma_200 rising over 21 sessions; sma_50 >
sma_150 and sma_200; close > sma_50; close >= 30% above the 52-week low; within 25% of the 52-week high; RS rating
>= 70 (`rs_rating_ibd`, the weighted 63/126/189/252-day percentile reconstruction of IBD's proprietary rating).

VCP: from the highest high of the last `base_max_bars`, confirmed swing pivots (`_swing.swing_pivots`) give 2-6
contractions (high-to-next-low depths), the first <= 35% deep, each <= 0.75 x the prior, the last <= 10%; pivot =
the most recent swing high; the last contraction low is not undercut and no close has crossed the pivot since it.
Trigger: close above the pivot, no more than 5% above, on volume >= 1.4 x the prior 50-day average. Optional volume
dry-up (`vol_dryup_max`, no book number) is off. Entry next open (no buy stop at the pivot: the close must confirm).
Stop = max(last contraction low x 0.995, entry x 0.90). No target; exits: close below sma_50 on >= 1.5x volume, 60
sessions, or the failed-breakout exit, a close back under the entry signal's pivot within `fail_exit_bars` = 2 bars
(read from the position's entry features; live, where the ledger keeps no features, it cannot fire). Partial sales,
the climax sale and breakeven at 2-3R are not built; the engine overlay's breakeven stays on.
"""
from __future__ import annotations

from datetime import date
from typing import Any, NamedTuple

import numpy as np
import pandas as pd

from swing_engine.core.models import PositionContext, Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_FLAT, PanelStrategy, entry_feature, finite
from ._swing import alternate, swing_pivots

NAME = "vcp_sepa_breakout"
VOL_BASE = "prev_avg_vol_50d"  # mean volume of the 50 bars before this one
TEMPLATE_COLS = ("sma_50", "sma_150", "sma_200", "sma_200_slope_21", "dist_52w_low", "dist_52w_high", "rs_rating_ibd")


class Vcp(NamedTuple):
    pivot: float
    final_low: float
    final_low_idx: int
    depths: tuple[float, ...]


@register("strategy", NAME)
class VcpSepaBreakout(PanelStrategy):
    name = NAME
    description = "Trend Template + 2-6 shrinking contractions; close through the pivot on 1.4x volume, <= 5% extended."
    default_params: dict[str, Any] = {
        "min_above_low": 0.30,  # template 6: 30%+ above the 52-week low
        "max_below_high": 0.25,  # template 7: within 25% of the 52-week high
        "rs_rating_min": 70.0,  # template 8: RS rating 70+
        "base_max_bars": 65,  # engine choice: VCP base within ~13 weeks of its high
        "swing_width": 3,  # engine choice: bars each side confirming a swing point
        "vcp_min_t": 2,  # card: 2 contractions minimum (3 preferred)
        "vcp_max_t": 6,  # card: 2-6 contractions
        "vcp_first_depth_max": 0.35,  # card
        "vcp_depth_ratio_max": 0.75,  # card: each about half the prior (0.5-0.75)
        "vcp_final_depth_max": 0.10,  # card
        "vol_dryup_max": None,  # card: final-contraction volume / prior 50-day average (no book number); None = off
        "breakout_vol_mult": 1.4,  # card: volume >= 1.4-1.5x average
        "max_extension": 0.05,  # card: not more than ~5% above the pivot
        "stop_buffer": 0.005,  # card: stop = final low x 0.995
        "max_stop_pct": 0.10,  # card: max stop 10%
        "exit_ma": "sma_50",  # card: exit on a heavy-volume close below the 50-day
        "exit_volume_mult": 1.5,  # card: "on volume >= 1.5x"
        "max_hold_days": 60,  # card
        "fail_exit_bars": 2,  # card: exit on a close < the pivot within 2 bars (0 = off)
        P_MIN_MARKET_TREND: TREND_FLAT,
        P_MIN_RR: 0.0,  # card: rule exit
    }
    features_required = ["avg_vol_50d"]
    extra_features = ["sma_150", "sma_200_slope_21", "dist_52w_low", "rs_rating_ibd", VOL_BASE]

    def required_features(self) -> list[str]:
        return list(dict.fromkeys([*super().required_features(), "sma_50", "sma_200", "dist_52w_high",
                                   str(self.params["exit_ma"])]))

    def should_exit(self, row: pd.Series, bars_held: int, position: PositionContext | None = None) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        pivot = entry_feature(position, "pivot")
        if bars_held <= int(self.params["fail_exit_bars"]) and pivot is not None and float(row["close"]) < pivot:
            return True
        ma, avg = row.get(str(self.params["exit_ma"])), row.get("avg_vol_50d")
        if not (finite(ma) and finite(avg)) or float(row["close"]) >= float(ma):
            return False
        return float(row["volume"]) >= float(self.params["exit_volume_mult"]) * float(avg)

    def template_ok(self, row: pd.Series) -> bool:
        if not all(finite(row[c]) for c in TEMPLATE_COLS):
            return False
        p = self.params
        c, s50, s150, s200 = (float(row[x]) for x in ("close", "sma_50", "sma_150", "sma_200"))
        return (
            c > s150 > s200
            and c > s200
            and float(row["sma_200_slope_21"]) > 0
            and s50 > s150
            and c > s50
            and float(row["dist_52w_low"]) >= float(p["min_above_low"])
            and float(row["dist_52w_high"]) >= -float(p["max_below_high"])
            and float(row["rs_rating_ibd"]) >= float(p["rs_rating_min"])
        )

    def find_vcp(self, w: dict[str, np.ndarray], end: int) -> Vcp | None:
        p = self.params
        start = max(0, end - int(p["base_max_bars"]) + 1)
        seg = w["high"][start : end + 1]
        if not np.isfinite(seg).all() or end - start < 2:
            return None
        i0 = start + int(np.argmax(seg))
        piv = swing_pivots(w["high"], w["low"], i0 + 1, end, int(p["swing_width"]))
        seq = alternate([("H", i0, float(w["high"][i0])), *piv])
        highs, lows = seq[0::2], seq[1::2]
        n = len(lows)
        if not int(p["vcp_min_t"]) <= n <= int(p["vcp_max_t"]):
            return None
        depths = tuple((h[2] - lo[2]) / h[2] for h, lo in zip(highs, lows, strict=False))
        if depths[0] > float(p["vcp_first_depth_max"]) or depths[-1] > float(p["vcp_final_depth_max"]):
            return None
        if any(b > float(p["vcp_depth_ratio_max"]) * a for a, b in zip(depths, depths[1:], strict=False)):
            return None
        pivot, (_, li, final_low) = highs[-1][2], lows[-1]
        if w["low"][li : end + 1].min() < final_low or w["close"][li + 1 : end + 1].max(initial=-np.inf) > pivot:
            return None
        return Vcp(pivot, final_low, li, depths)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        arrays = ("high", "low", "close", "volume")
        view = as_of_view(panel, as_of, list(dict.fromkeys([*arrays, *self.required_features()])))
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            base_vol = row[VOL_BASE]
            if not (finite(base_vol) and float(base_vol) > 0) or not self.template_ok(row):
                continue
            vol_ratio = float(row["volume"]) / float(base_vol)
            if vol_ratio < float(p["breakout_vol_mult"]):
                continue
            w = view.window(str(row[SYMBOL]), arrays)
            end = len(w["close"]) - 2
            vcp = self.find_vcp(w, end)
            if vcp is None:
                continue
            close = float(row["close"])
            ext = close / vcp.pivot - 1.0
            if not 0 < ext <= float(p["max_extension"]):
                continue
            dry = p.get("vol_dryup_max")
            if dry is not None and float(np.mean(w["volume"][vcp.final_low_idx : end + 1])) / float(base_vol) > float(dry):
                continue
            stop = max(vcp.final_low * (1.0 - float(p["stop_buffer"])), close * (1.0 - float(p["max_stop_pct"])))
            sig = self.build_signal(
                row,
                as_of,
                entry=close,
                stop=stop,
                target=None,
                score=vol_ratio + float(row["rs_rating_ibd"]) / 100.0,
                features={"pivot": vcp.pivot, "final_low": vcp.final_low, "contractions": len(vcp.depths),
                          "final_depth": vcp.depths[-1], "extension": ext, "volume_ratio": vol_ratio,
                          "rs_rating_ibd": row["rs_rating_ibd"], "max_hold_days": p["max_hold_days"]},
                notes=f"VCP {len(vcp.depths)}T " + "/".join(f"{d * 100:.0f}" for d in vcp.depths)
                + f"%: close {close:.2f} {ext * 100:+.1f}% over pivot {vcp.pivot:.2f} on {vol_ratio:.1f}x vol",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
