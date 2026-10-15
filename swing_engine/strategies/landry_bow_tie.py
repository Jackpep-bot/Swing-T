"""Dave Landry Bow Tie (long), docs/strategies/landry_bow_tie.md (catalog C24); pullback_trend family.

Proper Order up = sma_10 > ema_20 > ema_30. Bow Tie = the three averages converge (spread (max - min) / close <=
1% on some bar in the 10 bars before the Proper Order run began) and then fan out into Proper Order; the run must be
no older than 15 bars (card engine choices). Setup: the first Landry pullback since then, >= 2 consecutive lower
lows ending on the signal bar. Entry: buy stop a tick above the signal bar's high (entry_type stop); stop = the
pullback low - 0.1 x atr_14. Landry's 2-for-1 (half off at 1R, trail the rest) needs a scale-out hook: this is the
card's single-exit variant, target 2R, plus an exit when Proper Order turns down and a 30-session cap.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import EntryType, Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "landry_bow_tie"
MAS = ("sma_10", "ema_20", "ema_30")  # card: 10 SMA / 20 EMA / 30 EMA (fixed)


def lower_low_runs(low: np.ndarray) -> np.ndarray:
    """Count of consecutive bars ending at each index whose low is below the prior bar's low."""
    out = np.zeros(len(low), dtype=int)
    for i in range(1, len(low)):
        out[i] = out[i - 1] + 1 if low[i] < low[i - 1] else 0
    return out


@register("strategy", NAME)
class LandryBowTie(PanelStrategy):
    name = NAME
    description = "First >= 2-bar lower-low pullback after a bow tie into sma_10 > ema_20 > ema_30; buy stop over high."
    default_params: dict[str, Any] = {
        "converge_pct": 0.01,  # card: MA spread / close <= 1% (engine choice)
        "converge_bars": 10,  # card: convergence within 10 bars before the fan-out
        "max_trend_age": 15,  # card: pullback within 15 bars of the Proper Order start
        "min_lower_lows": 2,  # card: >= 2 bars of lower lows
        "tick": 0.01,  # card: buy stop at high + 0.01
        "stop_atr_buffer": 0.1,  # card: pullback low - 0.1 x atr_14
        "target_r": 2.0,  # card: single-exit variant, target 2R
        "max_hold_days": 30,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 1.0,  # card
    }
    features_required = ["atr_14", "sma_10"]
    extra_features = ["ema_20", "ema_30"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        a, b, c = (row.get(m) for m in MAS)
        return all(finite(x) for x in (a, b, c)) and float(a) < float(b) < float(c)

    def _setup(self, w: dict[str, np.ndarray]) -> int:
        """Length of the qualifying lower-low run ending on the last bar of ``w`` (0 = no setup)."""
        p = self.params
        keep = int(p["max_trend_age"]) + int(p["converge_bars"]) + 2  # older bars cannot matter
        w = {k: v[-keep:] for k, v in w.items()}
        t = len(w["close"]) - 1
        mas = np.vstack([w[m] for m in MAS])
        order = (mas[0] > mas[1]) & (mas[1] > mas[2])
        if not order[t]:
            return 0
        s = t
        while s > 0 and order[s - 1]:
            s -= 1
        if t - s > int(p["max_trend_age"]) or s == 0:
            return 0
        lo = max(0, s - int(p["converge_bars"]))
        spread = (mas[:, lo:s].max(axis=0) - mas[:, lo:s].min(axis=0)) / w["close"][lo:s]
        if not (np.isfinite(spread).any() and np.nanmin(spread) <= float(p["converge_pct"])):
            return 0
        runs = lower_low_runs(w["low"])
        need = int(p["min_lower_lows"])
        if runs[t] < need:
            return 0
        first = t - runs[t] + 1  # first bar of the current pullback
        return 0 if (runs[s + 1 : first] >= need).any() else int(runs[t])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        arrays = ("high", "low", "close", *MAS)
        view = as_of_view(panel, as_of, list(dict.fromkeys([*arrays, *self.required_features()])))
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            atr = row["atr_14"]
            a, b, c = (row[m] for m in MAS)
            if not all(finite(x) for x in (atr, a, b, c)) or not float(a) > float(b) > float(c):
                continue
            run = self._setup(view.window(str(row[SYMBOL]), arrays))
            if not run:
                continue
            pull_low = float(row["low"])  # the last of the descending lows
            entry = float(row["high"]) + float(p["tick"])
            stop = pull_low - float(p["stop_atr_buffer"]) * float(atr)
            sig = self.build_signal(
                row,
                as_of,
                entry=entry,
                stop=stop,
                target=entry + float(p["target_r"]) * (entry - stop),
                score=float(row["sma_10"]) / float(row["ema_30"]) - 1.0,
                features={"pullback_low": pull_low, "lower_lows": run, "atr_14": atr,
                          "max_hold_days": p["max_hold_days"]},
                notes=f"bow tie first pullback ({run} lower lows): buy stop {entry:.2f}, stop {stop:.2f}",
            )
            if sig:
                out.append(sig.model_copy(update={"entry_type": EntryType.STOP}))
        self.log_scan(as_of, len(view.current), len(out))
        return out
