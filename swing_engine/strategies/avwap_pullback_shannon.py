"""Anchored-VWAP pullback (long), Shannon: docs/strategies/avwap_pullback_shannon.md, methods.md 6.8 / 7b #6.

Daily-bar version of the card's spec. Anchor = the latest confirmed pivot low (width 5, known 5 bars later, so no
look-ahead); AVWAP = cumulative (px x volume) / volume from the anchor, px = the bar `vwap` when present else
(H+L+C)/3. Setup: trend_state up, AVWAP rising over 5 bars and tested at most twice, a 2-6 bar pullback of lower
highs on below-average volume that reached the AVWAP or the 5-day SMA. Trigger: close above the prior high, the
5-day SMA and the AVWAP ("buy strength after the dip"). Stop: pullback low - 0.1 x atr_14, skipped when wider than
3%. Target: prior 20-bar swing high. Exits: 5-day SMA rolling over with the close under it, or 30 bars.

Approximations: the taught trigger is intraday (65/15-minute higher low); the earnings / max-volume / YTD anchors
and the R2 first-third scale-out are not built; the "lost the AVWAP" exit is not available to `should_exit`
(per-row hook) so the SMA-5 exit stands in.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.features.extra import last_pivot
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

NAME = "avwap_pullback_shannon"
MA_COL = "sma_5"


def avwap_from(anchor: int, high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray,
               vwap: np.ndarray | None) -> np.ndarray:
    """AVWAP for bars anchor..end (array aligned to that slice)."""
    px = (high + low + close) / 3.0
    if vwap is not None:
        px = np.where(np.isfinite(vwap), vwap, px)
    pv, v = np.cumsum((px * volume)[anchor:]), np.cumsum(volume[anchor:])
    return np.where(v > 0, pv / np.where(v > 0, v, 1.0), np.nan)


@register("strategy", NAME)
class AvwapPullbackShannon(PanelStrategy):
    name = NAME
    description = "Stage-2 name above a rising pivot-low AVWAP; 2-6 bar quiet pullback; buy the close back over prior high."
    default_params: dict[str, Any] = {
        "pivot_width": 5,  # card: pivot low width 5 as in features/levels.py, confirmed 5 bars later
        "avwap_slope_bars": 5,  # card: avwap[t] - avwap[t-5] > 0
        "max_touches": 2,  # card: level tested at most 1-2 times
        "touch_pct": 0.01,  # card: low <= avwap x 1.01 counts as a touch; pullback low within 1% of avwap / sma_5
        "pullback_min_bars": 2,  # card: 2-6 day pullback
        "pullback_max_bars": 6,
        "max_pullback_volume_ratio": 1.0,  # card: mean pullback volume / avg_vol_20d <= 1.0
        "stop_atr_buffer": 0.1,  # card: stop = pullback low - 0.1 x atr_14
        "max_stop_pct": 0.03,  # card: skip if (entry - stop) / entry > 3%
        "swing_high_bars": 20,  # card: target = prior 20-bar swing high
        "max_hold_days": 30,  # card: 30-bar time stop
        P_MIN_TREND: TREND_UP,  # card: Stage 2 (trend_state == 1)
        P_MIN_MARKET_TREND: TREND_FLAT,
        P_MIN_RR: 1.0,  # card: min_reward_risk 1.0 with the swing-high target
    }
    features_required = ["atr_14", "avg_vol_20d", "trend_state"]
    extra_features = [MA_COL, f"prev_{MA_COL}"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        ma, prev = row.get(MA_COL), row.get(f"prev_{MA_COL}")
        return finite(ma) and finite(prev) and float(ma) < float(prev) and float(row["close"]) < float(ma)

    def _pullback_len(self, high: np.ndarray, t: int) -> int:
        p, cap = 0, int(self.params["pullback_max_bars"]) + 1
        while p < cap and t - 2 - p >= 0 and high[t - 1 - p] < high[t - 2 - p]:
            p += 1
        return p

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        has_vwap = "vwap" in panel.columns
        cols = ["high", "low", "close", "volume", MA_COL, "avg_vol_20d", *(["vwap"] if has_vwap else [])]
        view = as_of_view(panel, as_of, ["open", *cols, *self.required_features()])
        touch, slope_n = float(p["touch_pct"]), int(p["avwap_slope_bars"])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            if not self.trend_ok(row):
                continue
            w = view.window(str(row[SYMBOL]), cols)
            hi, lo, cl, vol, ma = w["high"], w["low"], w["close"], w["volume"], w[MA_COL]
            t = len(cl) - 1
            n_pb = self._pullback_len(hi, t)
            if not int(p["pullback_min_bars"]) <= n_pb <= int(p["pullback_max_bars"]):
                continue
            a = int(last_pivot(lo, int(p["pivot_width"]), int(p["pivot_width"]), highs=False)[1][t])
            if a < 0 or t - slope_n < a:
                continue
            av = avwap_from(a, hi, lo, cl, vol, w.get("vwap"))
            seg_lo, seg_cl = lo[a:], cl[a:]
            touches = int(np.sum((seg_lo[1:] <= av[1:] * (1 + touch)) & (seg_cl[1:] >= av[1:])))
            av_t, av_prev, av_back = av[-1], av[-2], av[-1 - slope_n]
            pb = slice(t - n_pb, t)
            pb_low = float(np.min(lo[pb]))
            vol_ratio = float(np.mean(vol[pb])) / w["avg_vol_20d"][t - 1] if w["avg_vol_20d"][t - 1] > 0 else np.nan
            close = float(cl[t])
            if not (av_t > av_back and touches <= int(p["max_touches"]) and finite(ma[t]) and finite(ma[t - 1])):
                continue
            if pb_low > max(av_prev, ma[t - 1]) * (1 + touch) or not vol_ratio <= float(p["max_pullback_volume_ratio"]):
                continue
            if not (close > hi[t - 1] and close > ma[t] and close > av_t):
                continue
            stop = pb_low - float(p["stop_atr_buffer"]) * float(row["atr_14"])
            if (close - stop) / close > float(p["max_stop_pct"]):
                continue
            n_sw = int(p["swing_high_bars"])
            target = float(np.max(hi[max(0, t - n_sw) : t]))
            sig = self.build_signal(
                row, as_of, entry=close, stop=stop, target=target, score=(target - close) / (close - stop),
                features={"avwap": av_t, "anchor_age": t - a, "touches": touches, "pullback_bars": n_pb,
                          "pullback_low": pb_low, "pullback_vol_ratio": vol_ratio, MA_COL: ma[t],
                          "max_hold_days": p["max_hold_days"]},
                notes=f"AVWAP {av_t:.2f} (pivot low {t - a} bars ago, {touches} touch(es)) rising; {n_pb}-bar quiet "
                f"pullback to {pb_low:.2f}; close {close:.2f} > prior high {hi[t - 1]:.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
