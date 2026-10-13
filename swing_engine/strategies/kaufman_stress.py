"""Kaufman Stress (long): docs/strategies/kaufman_stress.md (thinkorswim StressIndicator strategy).

Stress = stochastic(n) of [stochastic(n) of the stock close - stochastic(n) of the market (SPY) close]
(`stress_60`, features.extra; n = 60 is unverified). Entry when Stress crosses below 10 while the market's 60-day SMA
is rising; after a previous oversold episode it re-arms only once Stress has been above 50 since (re-entry rule).
Entry next open; stop 8% below (engine choice, the article's stop-loss default is unverified); exit when Stress > 50
or after 30 sessions. The index hedge is not modelled. Needs SPY rows in the panel (or the market frame).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "kaufman_stress"
STRESS = "stress_60"
MKT_MA, MKT_MA_PREV = "sma_60_of_market_close", "prev_sma_60_of_market_close"


@register("strategy", NAME)
class KaufmanStress(PanelStrategy):
    name = NAME
    description = "Stress (stock vs SPY stochastic) crosses under 10 with SPY's 60-day SMA rising; out above 50."
    default_params: dict[str, Any] = {
        "entry_level": 10.0,  # card: entry Stress < 10
        "exit_level": 50.0,  # card: exit Stress > 50; re-entry needs Stress above 50 since the last oversold bar
        "lookback_bars": 250,  # engine choice: bars searched for the previous oversold episode
        "stop_pct": 0.08,  # card: stop_pct 0.08 (engine choice)
        "max_hold_days": 30,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,  # the strategy's own index filter (SPY sma60 rising) replaces the gate
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required: list[str] = []
    extra_features = [STRESS, MKT_MA, MKT_MA_PREV]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        s = row.get(STRESS)
        return finite(s) and float(s) > float(self.params["exit_level"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        lvl_in, lvl_out = float(p["entry_level"]), float(p["exit_level"])
        view = as_of_view(panel, as_of, ["open", "high", "low", "close", *self.required_features()])
        cur = view.current
        keep = ((cur[STRESS] < lvl_in) & (cur[MKT_MA] > cur[MKT_MA_PREV])).fillna(False)
        out: list[Signal] = []
        for _, row in cur.loc[keep].iterrows():
            s = view.window(str(row[SYMBOL]), (STRESS,))[STRESS]
            t = len(s) - 1
            if t < 1 or not (finite(s[t - 1]) and s[t - 1] >= lvl_in):
                continue  # not the cross below the entry level
            past = s[max(0, t - int(p["lookback_bars"])) : t]
            low_idx = np.flatnonzero(past < lvl_in)
            if low_idx.size and not np.nanmax(past[low_idx[-1] :], initial=-np.inf) > lvl_out:
                continue  # re-entry rule: Stress must have been above the exit level since the last oversold bar
            close = float(row["close"])
            sig = self.build_signal(
                row, as_of, entry=close, stop=close * (1.0 - float(p["stop_pct"])), target=None,
                score=lvl_in - float(s[t]),
                features={STRESS: s[t], MKT_MA: row[MKT_MA], "max_hold_days": p["max_hold_days"]},
                notes=f"Stress {float(s[t]):.0f} crossed under {lvl_in:.0f} with SPY's 60-day SMA rising",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(cur), len(out))
        return out
