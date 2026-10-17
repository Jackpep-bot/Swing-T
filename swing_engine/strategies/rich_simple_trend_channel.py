"""James & John Rich Simple Trend Channel (long), docs/strategies/rich_simple_trend_channel.md (thinkorswim, B11).

Entry at the close when the close crosses above SMA(high, 8) (prior close at or below the prior channel top) with the
stock trend check "Min" (close > sma_50); filled next open. Stop = SMA(low, 8) when it is below the close, never wider
than entry - 2.5 x atr_14. `should_exit` on a close below SMA(low, 8) or after 30 sessions. No target.

Approximations: the S&P 500 close-above-SMA50 market filter is the engine's regime gate (min_market_trend_state = 0
rejects a market downtrend; panels carrying `market_trend_state` are gated per row too). The no-earnings-in-the-next-2-
sessions entry rule and the exit the session before earnings need a forward earnings calendar the store does not
keep (edgar_panel_features has only past announcements), so they are off; replays must be flagged as such.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import (
    P_MIN_MARKET_TREND,
    P_MIN_RR,
    P_MIN_TREND,
    REGIME_MARKET_TREND,
    TREND_DOWN,
    TREND_FLAT,
    PanelStrategy,
    finite,
)

NAME = "rich_simple_trend_channel"
TOP, BOTTOM = "sma_8_of_high", "sma_8_of_low"


@register("strategy", NAME)
class RichSimpleTrendChannel(PanelStrategy):
    name = NAME
    description = "Close crosses above SMA(high,8) with close > SMA50 in a non-down market; exit on close < SMA(low,8)."
    default_params: dict[str, Any] = {
        "trend_ma": "sma_50",  # card: trend check Min = close > sma_50
        "stop_atr_mult": 2.5,  # card: stop = max(sma(low,8), entry - 2.5 x atr_14)
        "max_hold_days": 30,  # card: max_hold_days 30
        P_MIN_TREND: TREND_DOWN,  # the trend check is the trend_ma test
        P_MIN_MARKET_TREND: TREND_FLAT,  # card approximation of SPX close > SMA50
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["atr_14", "trend_state", "sma_50"]
    extra_features = [TOP, BOTTOM, f"prev_{TOP}"]
    engine_trail = False  # exit on the channel bottom (card)

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        low = row.get(BOTTOM)
        return bars_held >= int(self.params["max_hold_days"]) or (finite(low) and float(row["close"]) < float(low))

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        rows = c1.rows(self, panel, as_of)
        if rows.empty:  # as_of before the first bar: rows_as_of returns the slice without prior_* columns
            return []
        keep = ((rows["close"] > rows[TOP]) & (rows["prior_close"] <= rows[f"prev_{TOP}"])
                & (rows["close"] > rows[str(p["trend_ma"])]))
        if REGIME_MARKET_TREND in rows.columns:
            keep &= ~(rows[REGIME_MARKET_TREND] < int(p[P_MIN_MARKET_TREND]))
        out: list[Signal] = []
        for _, row in rows.loc[keep.fillna(False)].iterrows():
            close, atr, low = float(row["close"]), row["atr_14"], row[BOTTOM]
            if not (finite(atr) and finite(low)) or not self.trend_ok(row):
                continue
            stop = max(float(low), close - float(p["stop_atr_mult"]) * float(atr))
            if stop >= close:
                stop = close - float(p["stop_atr_mult"]) * float(atr)
            sig = self.build_signal(row, as_of, entry=close, stop=stop, target=None, score=close / float(row[TOP]) - 1.0,
                                    features={TOP: row[TOP], BOTTOM: low, "max_hold_days": p["max_hold_days"]},
                                    notes=f"close {close:.2f} crossed above SMA(high,8) {row[TOP]:.2f}")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
