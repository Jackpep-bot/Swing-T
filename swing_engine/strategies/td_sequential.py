"""DeMark TD Sequential buy signals (long): docs/strategies/td_sequential.md.

Counters come from features.extra (`td_buy_setup`, `td_buy_perfected`, `td_tdst`, `td_buy_countdown`,
`td_risk_level`; see `_td_np` there for the setup / perfection / countdown-13 qualifier / cancellation rules).
`trigger: countdown` (default): buy countdown 13 on bar t. `trigger: setup`: a perfected buy setup 9 with trend_state
>= 0 (card variant B). Entry next open; stop = TD risk level, capped at entry - 3 x atr_14; target = TDST when it is
above the entry, else none. `max_hold_days` 20 (countdown) or 10 (setup, set in settings). Sell setups only cancel
countdowns here (long-only engine).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, TREND_FLAT, PanelStrategy, finite

NAME = "td_sequential"
SETUP, PERF, TDST, COUNTDOWN, RISK = "td_buy_setup", "td_buy_perfected", "td_tdst", "td_buy_countdown", "td_risk_level"
COUNTDOWN_DONE, SETUP_DONE = 13, 9


@register("strategy", NAME)
class TDSequential(PanelStrategy):
    name = NAME
    description = "TD Sequential buy countdown 13 (or perfected setup 9); stop at the TD risk level, target TDST."
    default_params: dict[str, Any] = {
        "trigger": "countdown",  # card: countdown 13 (variant B: "setup", perfected setup 9 with trend_state >= 0)
        "setup_min_trend": TREND_FLAT,  # card variant B: trend_state >= 0
        "max_stop_atr": 3.0,  # card: stop capped at entry - 3 x atr_14
        "max_hold_days": 20,  # card: 20 for countdown 13, 10 for setup 9
        P_MIN_TREND: TREND_DOWN,  # countdown 13 is a reversal after a decline: no trend gate
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 1.0,  # card (applies when TDST gives a target)
    }
    features_required = ["atr_14", "trend_state"]
    extra_features = [SETUP, PERF, TDST, COUNTDOWN, RISK]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        if p["trigger"] == "setup":
            ts = rows["trend_state"]
            keep = (rows[SETUP] == SETUP_DONE) & (rows[PERF] == 1.0) & (ts >= int(p["setup_min_trend"]))
        else:
            keep = rows[COUNTDOWN] == COUNTDOWN_DONE
        out: list[Signal] = []
        for _, row in rows.loc[keep.fillna(False)].iterrows():
            close, atr, risk, tdst = float(row["close"]), row["atr_14"], row[RISK], row[TDST]
            if not (finite(atr) and finite(risk)) or not self.trend_ok(row):
                continue
            stop = max(float(risk), close - float(p["max_stop_atr"]) * float(atr))
            target = float(tdst) if finite(tdst) and tdst > close else None
            sig = self.build_signal(
                row, as_of, entry=close, stop=stop, target=target, score=-(close - stop) / float(atr),
                features={RISK: risk, TDST: tdst, COUNTDOWN: row[COUNTDOWN], SETUP: row[SETUP]},
                notes=f"TD buy {p['trigger']} complete; risk level {float(risk):.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
