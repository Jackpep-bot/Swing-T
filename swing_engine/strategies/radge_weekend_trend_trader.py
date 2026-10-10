"""Nick Radge Weekend Trend Trader (long), docs/strategies/radge_weekend_trend_trader.md (usethinkscript forum port;
methods.md 1b).

Weekly bars (completed W-FRI weeks, `features.extra` `wk_*`), reviewed on the session a week completes
(`wk_fresh`), bought at the next open: weekly close above the highest weekly close of the prior 20 weeks; ROC(20
weeks) >= 30%; the market proxy's (SPY) weekly close above its 10-week SMA (NaN without SPY -> no signal).
Initial stop 40% under the entry close. Trailing stop (`trail_stop`, engine ratchets it up only): 40% under the
weekly close while the index is above its 10-week MA, 10% under it when the index is below, updated only when a week
completes. APPROXIMATION: the forum rule trails the highest weekly close since entry and exits at the next open after
a weekly close through the stop; here the ratcheted level is max over weeks of close x (1 - width), and the engine
treats it as a resting stop. The daily breakeven / N-day-low overlay is off (`engine_trail = False`). No target;
365-session cap. Forum testers found the 40/10 exit fragile (card): shadow only.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, finite

NAME = "radge_weekend_trend_trader"


def weekly_names(params: dict[str, Any]) -> list[str]:
    n, r, m = (int(params[k]) for k in ("breakout_weeks", "roc_weeks", "index_ma_weeks"))
    return ["wk_close", f"wk_close_max_{n}", f"wk_roc_{r}", f"mkt_wk_above_{m}", "wk_fresh"]


@register("strategy", NAME)
class RadgeWeekendTrendTrader(PanelStrategy):
    name = NAME
    description = "Weekly close at a 20-week closing high, ROC20w >= 30%, SPY over its 10-week MA; 40%/10% trail."
    default_params: dict[str, Any] = {
        "breakout_weeks": 20,  # card: new 20-week closing high
        "roc_weeks": 20,  # card: ROC(20 weeks)
        "roc_min_pct": 30.0,  # card: ROC >= 30% (forum testers 10-20%)
        "index_ma_weeks": 10,  # card: index weekly close above its 10-week MA
        "trail_up": 0.40,  # card: 40% under the highest weekly close while the index is up
        "trail_down": 0.10,  # card: tightened to 10% when the index closes below its MA
        "max_hold_days": 365,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,  # the weekly index filter replaces the daily regime gate
        P_MIN_RR: 0.0,  # card: no target
    }
    engine_trail = False
    features_required: list[str] = []
    extra_features = weekly_names(default_params)

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        self.extra_features = weekly_names(self.params)

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def trail_stop(self, row: pd.Series) -> float | None:
        wc, _, _, up, fresh = (row.get(c) for c in self.extra_features)
        if not (finite(fresh) and float(fresh) == 1.0 and finite(wc)):
            return None
        width = self.params["trail_up"] if finite(up) and float(up) == 1.0 else self.params["trail_down"]
        return float(wc) * (1.0 - float(width))

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        out: list[Signal] = []
        for _, row in rows.iterrows():
            wc, top, roc, up, fresh = (row[c] for c in self.extra_features)
            if not all(finite(x) for x in (wc, top, roc, up, fresh)) or float(fresh) != 1.0:
                continue
            if not (float(wc) > float(top) and float(roc) >= float(p["roc_min_pct"]) and float(up) == 1.0):
                continue
            close = float(row["close"])
            sig = self.build_signal(
                row,
                as_of,
                entry=close,
                stop=close * (1.0 - float(p["trail_up"])),
                target=None,
                score=float(roc),
                features={"wk_close": wc, "wk_close_max": top, "wk_roc": roc, "max_hold_days": p["max_hold_days"]},
                notes=f"weekly close {float(wc):.2f} > {int(p['breakout_weeks'])}-week closing high {float(top):.2f}, "
                f"ROC {float(roc):.0f}%, index above its {int(p['index_ma_weeks'])}-week MA",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
