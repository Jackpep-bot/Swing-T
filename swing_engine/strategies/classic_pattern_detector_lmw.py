"""Objective bullish chart patterns (Lo-Mamaysky-Wang kernel detector) with a breakout trading layer (long):
docs/strategies/classic_pattern_detector_lmw.md.

Detector (LMW 2000): the `window` closes before today are smoothed with a Nadaraya-Watson Gaussian kernel whose
bandwidth is `bandwidth_mult` x the leave-one-out cross-validated optimum over `bandwidth_grid`, floored at
`min_bandwidth` (on noisy closes CV picks 1 bar, and 0.3 bars just echoes every close reversal); local extrema are
sign changes of the smoothed slope (the last `lag` bars cannot hold one), each mapped to the actual extreme close
within one bar. On the last five alternating extrema E1..E5 (E1 a minimum) the bullish patterns are: inverse head and
shoulders (E3 below E1 and E5, E1/E5 and E2/E4 within 1.5% of their means), rectangle bottom (tops within 0.75%,
bottoms within 0.75%, lowest top above highest bottom) and double bottom (a later minimum within 1.5% of E1, at least
22 bars apart). Bearish patterns (H&S, tops, broadening, triangles) are not used by a long-only engine.
Trading layer (ours, card): the first close above the neckline with E5 at most `max_age` bars old; entry next open;
stop = max(last swing low, entry - 2 x atr_14); target = neckline + pattern height.
"""
from __future__ import annotations

from datetime import date
from typing import Any, NamedTuple

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "classic_pattern_detector_lmw"


class Pattern(NamedTuple):
    kind: str
    neckline: float
    height: float
    swing_low: float


def kernel_smooth(x: np.ndarray, grid: tuple[float, ...], mult: float, floor: float = 0.0) -> np.ndarray:
    """Gaussian Nadaraya-Watson fit of ``x`` on its bar index, bandwidth = max(mult x the LOO-CV best of ``grid``, floor)."""
    idx = np.arange(len(x), dtype=float)
    dist = (idx[:, None] - idx[None, :]) ** 2

    def weights(h: float) -> np.ndarray:
        return np.exp(-0.5 * dist / (h * h))

    errs = []
    for h in grid:
        k = weights(h)
        np.fill_diagonal(k, 0.0)
        errs.append(np.mean((x - k @ x / k.sum(axis=1)) ** 2))
    k = weights(max(mult * grid[int(np.argmin(errs))], floor))
    return k @ x / k.sum(axis=1)


def extrema(x: np.ndarray, smooth: np.ndarray, lag: int) -> list[tuple[int, float, bool]]:
    """(index, actual close, is_max) at sign changes of the smoothed slope, oldest first."""
    d = np.sign(np.diff(smooth))
    out: list[tuple[int, float, bool]] = []
    for i in range(1, len(d)):
        if d[i - 1] == d[i] or d[i] == 0 or i > len(x) - 1 - lag:
            continue
        is_max = d[i - 1] > 0
        lo, hi = max(0, i - 1), min(len(x), i + 2)
        j = lo + int(np.argmax(x[lo:hi]) if is_max else np.argmin(x[lo:hi]))
        out.append((j, float(x[j]), is_max))
    return out


def _near(vals: list[float], tol: float) -> bool:
    m = float(np.mean(vals))
    return all(abs(v - m) <= tol * m for v in vals)


@register("strategy", NAME)
class ClassicPatternLMW(PanelStrategy):
    name = NAME
    description = "LMW kernel-detected inverse H&S / rectangle bottom / double bottom; buy the neckline breakout."
    default_params: dict[str, Any] = {
        "window": 38,  # card: rolling 38 bars (35 + 3-bar lag)
        "lag": 3,  # card: the last extremum must be confirmed
        "bandwidth_mult": 0.3,  # card: 0.3 x the cross-validated optimum (LMW)
        "bandwidth_grid": (1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0),  # engine choice: CV search grid (bars)
        "min_bandwidth": 1.5,  # engine choice: floor on the final kernel bandwidth (bars); 0.3 x CV on noisy closes collapses to 0.3 bars
        "tol_hs": 0.015,  # card: within 1.5% (H&S shoulders / troughs, double bottom)
        "tol_rect": 0.0075,  # card: rectangle tops / bottoms within 0.75%
        "dbot_min_gap": 22,  # card: double bottom extrema at least 22 bars apart
        "max_age": 10,  # card: pattern detected within 10 bars
        "stop_atr_mult": 2.0,  # card: stop = max(last swing low, entry - 2 x atr_14)
        "max_hold_days": 30,  # card
        P_MIN_TREND: TREND_DOWN,
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 2.0,  # card
    }
    features_required = ["atr_14", "trend_state"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def detect(self, x: np.ndarray) -> Pattern | None:
        p = self.params
        smooth = kernel_smooth(x, tuple(p["bandwidth_grid"]), float(p["bandwidth_mult"]), float(p["min_bandwidth"]))
        ext = extrema(x, smooth, int(p["lag"]))
        if len(ext) < 5 or ext[-5][2]:
            return None
        (i1, e1, _), (_, e2, _), (i3, e3, _), (_, e4, _), (i5, e5, _) = ext[-5:]
        if len(x) - 1 - i5 > int(p["max_age"]):
            return None
        hs, rect = float(p["tol_hs"]), float(p["tol_rect"])
        if e3 < e1 and e3 < e5 and _near([e1, e5], hs) and _near([e2, e4], hs):
            neck = max(e2, e4)
            return Pattern("inverse_hs", neck, neck - e3, e5)
        if _near([e2, e4], rect) and _near([e1, e3, e5], rect) and min(e2, e4) > max(e1, e3, e5):
            neck = max(e2, e4)
            return Pattern("rectangle_bottom", neck, neck - min(e1, e3, e5), e5)
        for ij, ej, peaks in ((i3, e3, [e2]), (i5, e5, [e2, e4])):
            if ij - i1 >= int(p["dbot_min_gap"]) and _near([e1, ej], hs):
                neck = max(peaks)
                return Pattern("double_bottom", neck, neck - min(e1, ej), ej)
        return None

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        n = int(self.params["window"])
        view = as_of_view(panel, as_of, ["close", *self.required_features()])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            atr = row["atr_14"]
            if not (finite(atr) and self.trend_ok(row)):
                continue
            c = view.window(str(row[SYMBOL]), ["close"])["close"]
            if len(c) < n + 1 or not np.isfinite(c[-n - 1 :]).all():
                continue
            pat = self.detect(c[-n - 1 : -1])
            if pat is None or not (c[-2] <= pat.neckline < c[-1]):
                continue
            close = float(c[-1])
            sig = self.build_signal(
                row, as_of, entry=close, stop=max(pat.swing_low, close - float(self.params["stop_atr_mult"]) * float(atr)),
                target=pat.neckline + pat.height, score=pat.height / float(atr),
                features={"neckline": pat.neckline, "pattern_height": pat.height, "swing_low": pat.swing_low},
                notes=f"LMW {pat.kind}: close {close:.2f} over neckline {pat.neckline:.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
