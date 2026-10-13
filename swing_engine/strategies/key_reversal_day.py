"""Key reversal day (long), variant A (broker built-in): docs/strategies/key_reversal_day.md.

thinkorswim KeyRevLE / TradeStation Key Reversal LE: the low undercuts the lows of the `length` prior bars (default 1)
and the close is above the prior close (`strict`: above the prior high, the classic form). The engine's
`key_reversal` flag (features/patterns.py) adds a 1.5x volume rule; here it is a param (`vol_mult`, None = off) so
both can be compared. Signal at the close, buy next open, stop low - 0.01; no target; 4-day time stop and the
optional KeyRevLX exit (new 1-bar high and close below the prior close). Variant B (buy stop over the reversal high)
is the same module with `entry_stop: True` (stop entry at high + 0.01).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import EntryType, Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, PanelStrategy, RollingSpec, finite

NAME = "key_reversal_day"
PREV_HIGH = "prev_high"


@register("strategy", NAME)
class KeyReversalDay(PanelStrategy):
    name = NAME
    description = "Low below the prior N lows, close above the prior close; buy next open, stop under the low."
    default_params: dict[str, Any] = {
        "length": 1,  # card: TradeStation default N = 1
        "strict": False,  # card: classic strict form needs close > prior high
        "vol_mult": None,  # card: brokers have no volume rule; 1.5 reproduces features/patterns.py key_reversal
        "tick": 0.01,  # card: stop low_t - 0.01 (variant B entry high_t + 0.01)
        "entry_stop": False,  # card variant B: buy stop over the reversal high (needs the stop-entry fill)
        "keyrev_exit": True,  # card: optional KeyRevLX exit
        "max_hold_days": 4,  # card
        P_MIN_TREND: TREND_DOWN,
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["avg_vol_50d", "trend_state", "prev_close"]
    extra_features = [PREV_HIGH]  # KeyRevLX exit reads the prior high from the held row
    prior_columns = ["high", "close", "avg_vol_50d"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        ph, pc = row.get(PREV_HIGH), row.get("prev_close")
        return bool(self.params["keyrev_exit"]) and finite(ph) and finite(pc) and (
            float(row["high"]) > float(ph) and float(row["close"]) < float(pc))

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        spec = RollingSpec("low", "min", int(p["length"]), prior=True)
        rows = self.rows_as_of(panel, as_of, rolling=[spec], required=self.features_required)
        ref = rows["prior_high"] if p["strict"] else rows["prior_close"]
        keep = (rows["low"] < rows[spec.out]) & (rows["close"] > ref)
        if p["vol_mult"] is not None:
            keep &= rows["volume"] >= float(p["vol_mult"]) * rows["prior_avg_vol_50d"]
        tick = float(p["tick"])
        out: list[Signal] = []
        for _, row in rows.loc[keep.fillna(False)].iterrows():
            if not self.trend_ok(row):
                continue
            close, high, low = float(row["close"]), float(row["high"]), float(row["low"])
            entry = high + tick if p["entry_stop"] else close
            sig = self.build_signal(
                row, as_of, entry=entry, stop=low - tick, target=None, score=(close - low) / (high - low or 1.0),
                features={"low_ref": row[spec.out], "rvol_50": row["volume"] / row["prior_avg_vol_50d"]},
                notes=f"key reversal: low {low:.2f} < {int(p['length'])}-bar low, close {close:.2f} > prior",
            )
            if sig:
                out.append(sig.model_copy(update={"entry_type": EntryType.STOP}) if p["entry_stop"] else sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
