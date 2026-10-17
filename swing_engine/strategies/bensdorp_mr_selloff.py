"""Bensdorp "Long Mean Reversion Selloff" (system 3), long: docs/proposals/swing-methods-2026-10/batch5/bensdorp_mr_selloff.md.

Signal on close t: 50-day average volume >= 1M shares, close >= $1, ATR%(10) = atr_10 / close x 100 >= 5, close >=
sma_150 and a 3-session drop 1 - close / close[t-3] >= 12.5% (`roc_3`). Entry: buy limit at 0.93 x the signal close,
good for the next session only (`EntryType.LIMIT`: fills at min(open, limit) when the low reaches it, else no trade).
Stop: limit - 2.5 x atr_10. Score: the 3-session drop (card: rank by largest drop).

Deviations, registered:
- Profit target. The card rests a limit at fill x 1.04 from the fill session's close onward. The engine cannot arm a
  target after the fill bar: a target on the Signal is live on the fill bar itself, where a limit bought under the
  open would "sell" at that same open. So the Signal has no target and `should_exit` closes the trade on the first
  close at or above fill x 1.04, the fill session included (the replay fills that exit at the next open). Intraday
  touches of +4% that fade by the close are not taken.
- Stop and limit are fixed at the signal: a gap-down open fills under the limit, and the stop stays at limit - 2.5 ATR.
- Time exit: `max_hold_days` = 4, the close of the 3rd session after the fill in `run_backtest`; the replay's
  position manager decides at that close and fills at the next open.
- Exclusions: `event_avoid_filters` is graded as its own card and the panel has no 8-K item column, so neither the
  filter nor the Item 1.03 / 3.01 skip runs here.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import EntryType, PositionContext, Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, entry_price, finite

NAME = "bensdorp_mr_selloff"
ATR, TREND_MA, ROC = "atr_10", "sma_150", "roc_3"  # features.extra; card: ATR(10), SMA(150), 3-day drop
AVG_VOL = "avg_vol_50d"  # card: 50-day average volume
PCT = 100.0


@register("strategy", NAME)
class BensdorpMrSelloff(PanelStrategy):
    name = NAME
    description = "12.5% three-day drop above sma_150 in a volatile stock; limit buy 7% lower; +4% close or 3 days."
    default_params: dict[str, Any] = {
        "min_avg_volume": 1_000_000.0,  # card: 50-day average volume >= 1M shares
        "min_price": 1.0,  # card: close >= $1 (published)
        "min_atr_pct": 5.0,  # card: ATR%(10) >= 5
        "min_drop": 0.125,  # card: 3-day drop >= 12.5%
        "limit_pct": 0.07,  # card: limit 7% below the signal close
        "stop_atr_mult": 2.5,  # card: stop entry - 2.5 x ATR(10)
        "target_pct": 0.04,  # card: profit target +4%
        "max_hold_days": 4,  # card: time exit at the close of the 3rd session after the fill (fill session = 1)
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: no market gate
        P_MIN_RR: 0.0,  # the target is a rule exit, not a Signal target
    }
    features_required = [AVG_VOL]
    extra_features = [ATR, TREND_MA, ROC]
    prior_columns: list[str] = []

    def should_exit(self, row: pd.Series, bars_held: int, position: PositionContext | None = None) -> bool:
        entry, close = entry_price(position), row.get("close")
        return entry is not None and finite(close) and float(close) >= entry * (1.0 + float(self.params["target_pct"]))

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        p = self.params
        rows = c1.rows(self, panel, as_of)
        if rows.empty:
            return []
        close, atr, drop = rows["close"], rows[ATR], -rows[ROC] / PCT
        keep = (
            (rows[AVG_VOL] >= float(p["min_avg_volume"])) & (close >= float(p["min_price"]))
            & (atr / close * PCT >= float(p["min_atr_pct"])) & (close >= rows[TREND_MA])
            & (drop >= float(p["min_drop"]))
        )
        out: list[Signal] = []
        for _, row in rows.loc[keep].iterrows():
            limit, fall = float(row["close"]) * (1.0 - float(p["limit_pct"])), -float(row[ROC]) / PCT
            stop = limit - float(p["stop_atr_mult"]) * float(row[ATR])
            if stop <= 0:
                continue
            sig = self.build_signal(
                row, as_of, entry=limit, stop=stop, target=None, score=fall,
                features={ATR: row[ATR], "drop_3d": fall, "signal_close": row["close"],
                          "max_hold_days": p["max_hold_days"]},
                notes=f"{fall:.1%} three-day drop above {TREND_MA}; limit {limit:.2f} for one session",
            )
            if sig:
                out.append(sig.model_copy(update={"entry_type": EntryType.LIMIT}))
        self.log_scan(as_of, len(rows), len(out))
        return out
