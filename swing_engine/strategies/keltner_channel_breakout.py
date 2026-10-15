"""Keltner channel breakout (long), TradeStation Keltner Channel LE: docs/strategies/keltner_channel_breakout.md,
catalog B76 / P10 / C41.

Bands: SMA20(close) +/- 1.5 x simple-mean ATR(20) (TradeStation; `kc_*_20` in features.extra). Setup: the close
crosses above the upper band; then a buy stop at that bar's high + 0.01 for one session (`entry_type = stop`). Card
mechanical context: the channel is turning up (centre above its value 5 bars ago) and trend_state is up. Stop: the
higher of the centre line and the breakout bar's low - 0.01. Exit: the long-only stand-in for the stop-and-reverse,
a close below the centre line, or 20 sessions. No target.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import EntryType, Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, TREND_UP, PanelStrategy, finite

NAME = "keltner_channel_breakout"
UPPER, MID = "kc_upper_20", "kc_mid_20"
SLOPE = "sma_20_slope_5"  # kc_mid_20 is sma_20: sma_20 / sma_20[t-5] - 1


@register("strategy", NAME)
class KeltnerChannelBreakout(PanelStrategy):
    name = NAME
    description = "Close crosses above SMA20 + 1.5 x ATR20; buy stop over the breakout high; exit close < SMA20."
    default_params: dict[str, Any] = {
        "tick": 0.01,  # card: buy stop at high + 1 tick; stop = low - 0.01
        "require_channel_up": True,  # card: channel turning up = kc_mid_t > kc_mid_{t-5}
        "max_hold_days": 20,  # card
        P_MIN_TREND: TREND_UP,  # card: require trend_state >= 1
        P_MIN_MARKET_TREND: TREND_DOWN,  # comparison baseline; the router gates the regime
        P_MIN_RR: 0.0,  # card: rule exit, no target
    }
    features_required = ["trend_state", "prev_close"]
    extra_features = [UPPER, MID, f"prev_{UPPER}", SLOPE]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        mid = row.get(MID)
        return finite(mid) and float(row["close"]) < float(mid)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        keep = (rows["close"] > rows[UPPER]) & (rows["prev_close"] <= rows[f"prev_{UPPER}"])
        if bool(p["require_channel_up"]):
            keep &= rows[SLOPE] > 0
        out: list[Signal] = []
        for _, row in rows.loc[keep.fillna(False)].iterrows():
            if not self.trend_ok(row):
                continue
            tick = float(p["tick"])
            entry = float(row["high"]) + tick
            stop = max(float(row[MID]), float(row["low"]) - tick)
            sig = self.build_signal(
                row, as_of, entry=entry, stop=stop, target=None, score=float(row["close"]) / float(row[UPPER]) - 1.0,
                features={UPPER: row[UPPER], MID: row[MID], SLOPE: row[SLOPE], "max_hold_days": p["max_hold_days"]},
                notes=f"close {float(row['close']):.2f} crossed over KC upper {float(row[UPPER]):.2f}; buy stop {entry:.2f}",
            )
            if sig:
                out.append(sig.model_copy(update={"entry_type": EntryType.STOP}))
        self.log_scan(as_of, len(rows), len(out))
        return out
