"""IPO first-base breakout (long): docs/strategies/ipo_first_base_breakout.md; the IPO variant of base_breakout.

Approximation: there is no IPO-date source, so a symbol counts as newly listed when its first bar in the panel comes
after the panel's first session (both known at as_of); a ticker change, spin-off or data gap looks the same. Not
modelled: the lockup-expiry exit. Exits: the stop max(base low, close x 0.92), the 40-day time exit and the card's
failed-breakout exit, a close back below the entry signal's pivot within `fail_exit_bars` = 3 bars (`should_exit`
reads the pivot from the position's entry features; live, where the ledger keeps no features, it cannot fire).
Rules (card, unverified IBD numbers): within `max_days_since_ipo`
sessions of the first bar, a base starting at its left-side high (the pivot) 0-25 sessions after listing, 7-40 bars
long, at most 25% deep (high to low) and ending the bar before today; buy the close above the base high (pivot), no
more than 5% above it, on volume >= 1.5x the mean volume since listing excluding day 1 (50-day averages do not exist
yet). The earliest qualifying start (longest base) is used. Stop = max(base low, close x 0.92); target close x 1.20;
40-day time exit. trend_state / RS are NaN for new issues, so there is no trend gate.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import PositionContext, Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view, local_day

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, TS, PanelStrategy, entry_feature

NAME = "ipo_first_base_breakout"


@register("strategy", NAME)
class IPOFirstBaseBreakout(PanelStrategy):
    name = NAME
    description = "New listing's first base (7-40 bars, <= 25% deep): buy the close over the base high on 1.5x volume."
    default_params: dict[str, Any] = {
        "max_days_since_ipo": 250,  # card (also try 120)
        "base_start_max_days": 25,  # card
        "base_min_bars": 7,  # card
        "base_max_bars": 40,  # card
        "base_max_depth": 0.25,  # card (also 0.35, 0.50)
        "vol_mult": 1.5,  # card
        "max_extension": 0.05,  # card: buy zone pivot to pivot + 5%
        "stop_pct": 0.08,  # card: stop = max(base low, entry x 0.92)
        "target_pct": 0.20,  # card: target entry x 1.20
        "max_hold_days": 40,  # card
        "fail_exit_bars": 3,  # card: exit on a close back below the pivot within 3 bars (0 = off)
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 2.0,  # card
    }
    features_required: list[str] = []

    def should_exit(self, row: pd.Series, bars_held: int, position: PositionContext | None = None) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        pivot = entry_feature(position, "pivot")
        return bars_held <= int(self.params["fail_exit_bars"]) and pivot is not None and float(row["close"]) < pivot

    def _base(self, h: np.ndarray, lo: np.ndarray, t: int) -> tuple[float, float] | None:
        """(pivot, base low) of the longest qualifying base [s, t-1], or None."""
        p = self.params
        for s in range(0, int(p["base_start_max_days"]) + 1):
            n = t - s
            if n > int(p["base_max_bars"]):
                continue
            if n < int(p["base_min_bars"]):
                return None
            top, low = float(np.max(h[s:t])), float(np.min(lo[s:t]))
            if h[s] < top:
                continue  # the base starts at its left-side high (the pivot): nothing inside it trades above
            if top > 0 and 1.0 - low / top <= float(p["base_max_depth"]):
                return top, low
        return None

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        view = as_of_view(panel, as_of, ["high", "low", "close", "volume"])
        if view.frame.empty:
            return []
        first_session = local_day(view.frame[TS]).min()
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            sym = str(row[SYMBOL])
            if local_day(view.frame[TS].iloc[view.positions[sym][:1]]).iloc[0] <= first_session:
                continue  # history starts with the panel: not a known new listing
            w = view.window(sym, ["high", "low", "close", "volume"])
            t = len(w["close"]) - 1
            if t < 2 or t > int(p["max_days_since_ipo"]) or not np.isfinite(np.c_[w["high"], w["low"]]).all():
                continue
            base = self._base(w["high"], w["low"], t)
            if base is None:
                continue
            pivot, base_low = base
            close, vol = float(w["close"][t]), float(w["volume"][t])
            avg_vol = float(np.nanmean(w["volume"][1:t]))
            if not avg_vol > 0 or not (pivot < close <= pivot * (1.0 + float(p["max_extension"]))) or not vol >= float(p["vol_mult"]) * avg_vol:
                continue
            sig = self.build_signal(
                row, as_of, entry=close, stop=max(base_low, close * (1.0 - float(p["stop_pct"]))),
                target=close * (1.0 + float(p["target_pct"])), score=vol / avg_vol,
                features={"days_since_listing": t, "pivot": pivot, "base_low": base_low, "vol_ratio": vol / avg_vol},
                notes=f"IPO first base: close {close:.2f} > pivot {pivot:.2f}, {t} sessions after first bar",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
