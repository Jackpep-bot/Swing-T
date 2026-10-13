"""Turtle breakout systems (long), docs/strategies/turtle_breakout_systems.md (Dennis/Eckhardt, Faith; catalog C31).

Default System 2 (always taken): each close arms a buy stop one tick above the 55-day high (the channel the next bar
must exceed: highest high of the last 55 bars including today). N = Wilder 20-bar ATR (`atr_20`: N = (19 N + TR) /
20). Initial stop = entry - 2N. Exit on a 20-day low: the trailing stop is the lowest low of the last 20 bars
(`trail_stop`, live from the next session like the Turtles' resting stop). No target; 120-session cap. System 1
(`system: 1`, 20/10, 60 sessions) is coded WITHOUT its skip-after-a-winner filter (needs a shadow-trade ledger) and
without pyramiding (no add-on hook); both are documented gaps. `max_trigger_n` (engine choice) only arms stops within
that many N of the close, so the scan does not emit an order for every symbol every day.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, PanelStrategy, finite

NAME = "turtle_breakout_systems"
N_COL = "atr_20"
#: system -> (entry channel, exit channel); card: S1 20/10, S2 55/20
SYSTEMS: dict[int, tuple[int, int]] = {1: (20, 10), 2: (55, 20)}


@register("strategy", NAME)
class TurtleBreakoutSystems(PanelStrategy):
    name = NAME
    description = "Turtle System 2: buy stop over the 55-day high, 2N stop, exit on a 20-day low (S1 20/10 optional)."
    default_params: dict[str, Any] = {
        "system": 2,  # card: S2 always taken (S1 needs the skip-rule ledger)
        "tick": 0.01,  # card: exceed the channel by a tick
        "stop_n": 2.0,  # card: initial stop 2N
        "max_trigger_n": 1.0,  # engine choice: arm the stop only when it is within 1 N of the close
        "max_hold_days": 120,  # card: 120 (S2); set 60 with system 1
        P_MIN_TREND: TREND_DOWN,  # card: no filter
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["trend_state"]
    extra_features = [N_COL, "high_55", "low_20", "high_20", "low_10"]
    engine_trail = False  # the opposite channel is the exit (card)

    @property
    def channels(self) -> tuple[str, str]:
        entry, exit_ = SYSTEMS[int(self.params["system"])]
        return f"high_{entry}", f"low_{exit_}"

    def required_features(self) -> list[str]:
        return [*self.features_required, N_COL, *self.channels]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def trail_stop(self, row: pd.Series) -> float | None:
        low = row.get(self.channels[1])
        return float(low) if finite(low) else None

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        rows = c1.rows(self, panel, as_of)
        hi_col, _ = self.channels
        out: list[Signal] = []
        for _, row in rows.iterrows():
            n, level, close = row[N_COL], row[hi_col], float(row["close"])
            if not (finite(n) and finite(level)) or float(n) <= 0 or not self.trend_ok(row):
                continue
            entry = float(level) + float(p["tick"])
            if entry - close > float(p["max_trigger_n"]) * float(n):
                continue
            sig = self.build_signal(row, as_of, entry=entry, stop=entry - float(p["stop_n"]) * float(n), target=None,
                                    score=-(entry - close) / float(n),
                                    features={"turtle_n": n, "channel_high": level, "max_hold_days": p["max_hold_days"]},
                                    notes=f"Turtle S{p['system']}: buy stop {entry:.2f} over the {hi_col} channel, N {float(n):.2f}")
            sig = c1.stop_entry(sig)
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
