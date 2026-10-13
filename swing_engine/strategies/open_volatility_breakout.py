"""Williams open volatility breakout (long), docs/strategies/open_volatility_breakout.md (catalog C12 Williams
volatility breakout; C18 Crabel stretch variant).

Rule: buy stop at the next open + k x today's high-low range; the opposite stop (open - k x range) protects it.
APPROXIMATION: the engine's stop entries are fixed at signal time and the next open is unknown, so today's close
stands in for the next open: buy stop = close + k x range, protective stop = close - k x range (a stop 2 x the
offset below the trigger). Gaps shift the real levels; this is the daily-bar proxy until a "stop off the open" entry
type exists. The GSV and Crabel stretch offsets are not built (Williams' range only).
Williams' bailout (exit at the first profitable open) is not built: rule exits are decided at a close, so an exit
at the open cannot be expressed; only the 5-session time exit applies. Filters: trend_state up (engine choice, card
reuses trend_state); optional NR7 / ID-NR4 pre-filter on the signal bar (card variant, off). Long only.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import EntryType, Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, TREND_UP, PanelStrategy, finite

NAME = "open_volatility_breakout"


@register("strategy", NAME)
class OpenVolatilityBreakout(PanelStrategy):
    name = NAME
    description = "Buy stop at close + k x range (next-open proxy), protective stop at close - k x range; 5-day exit."
    default_params: dict[str, Any] = {
        "k": 0.5,  # card: k chosen by testing; broker 0.25, Korean retail 0.5-0.6 (untuned midpoint)
        "prefilter": None,  # card variant: "nr7" or "id_nr4" on the signal bar; None = off
        "max_hold_days": 5,  # card: max_hold_days 5
        P_MIN_TREND: TREND_UP,  # engine choice: trade the breakout with the trend (card reuses trend_state)
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["trend_state"]

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        pre = self.params.get("prefilter")
        self.extra_features = [str(pre)] if pre else []

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        pre = p.get("prefilter")
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        out: list[Signal] = []
        for _, row in rows.iterrows():
            if not self.trend_ok(row) or (pre and not (finite(row[str(pre)]) and float(row[str(pre)]) == 1.0)):
                continue
            rng = float(row["high"]) - float(row["low"])
            if not rng > 0:
                continue
            close, offset = float(row["close"]), float(p["k"]) * rng
            sig = self.build_signal(
                row,
                as_of,
                entry=close + offset,
                stop=close - offset,
                target=None,
                score=-offset / close,  # tighter relative offset first
                features={"offset": offset, "max_hold_days": p["max_hold_days"]},
                notes=f"volatility breakout: buy stop {close + offset:.2f} (close + {float(p['k']):g} x range), "
                "next open approximated by the close",
            )
            if sig:
                out.append(sig.model_copy(update={"entry_type": EntryType.STOP}))
        self.log_scan(as_of, len(rows), len(out))
        return out
