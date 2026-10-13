"""Bensdorp "Long Mean Reversion High ADX Reversal", long:
docs/proposals/swing-methods-2026-10/batch5/bensdorp_adx_reversal.md.

Signal on close t: 50-day average volume >= 500k shares, average dollar volume >= $2.5M, ATR%(10) = atr_10 / close x
100 >= 4, adx_7 > 45, close >= sma_100 + atr_10, rsi_3 <= 50, and no expected earnings within 6 sessions (a row with
no expected date is not skipped). Entry: buy limit at 0.96 x the signal close, good for the next session only
(`EntryType.LIMIT`: fills at min(open, limit) when the low reaches it, else no trade). Stop: limit - 3 x atr_10.
Score: adx_7 (card: rank by ADX). Needs `sessions_to_expected_earnings` (EDGAR join) and is silent without it.

Deviations, registered:
- Dollar-volume window. The card gives no window; the 50-session mean of close x volume is used, the window of the
  share-volume filter beside it (`sma_50_of_dollar_vol`).
- Profit target. The card rests a limit at fill + 1.2 x atr_10 from the fill session's close onward. The engine
  cannot arm a target after the fill bar: a target on the Signal is live on the fill bar itself, where a limit bought
  under the open would "sell" at that same open. So the Signal has no target and `should_exit` closes the trade on the
  first close at or above fill + 1.2 x the signal-day atr_10, the fill session included (the replay fills that exit
  at the next open). Intraday touches of the target that fade by the close are not taken.
- Stop and limit are fixed at the signal: a gap-down open fills under the limit, and the stop stays at limit - 3 ATR.
- Time exit: `max_hold_days` = 7, the close of the 6th session after the fill in `run_backtest`; the replay's
  position manager decides at that close and fills at the next open.
- `event_avoid_filters` is graded as its own card and is not applied here.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import EntryType, PositionContext, Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, entry_feature, entry_price, finite

NAME = "bensdorp_adx_reversal"
ADX, RSI, ATR, TREND_MA = "adx_7", "rsi_3", "atr_10", "sma_100"  # features.extra; card: ADX(7), RSI(3), ATR(10), SMA(100)
AVG_VOL, DOLLAR_VOL = "avg_vol_50d", "sma_50_of_dollar_vol"  # card: 50-day average volume; dollar volume (window: see above)
TO_EXP = "sessions_to_expected_earnings"  # data.fundamentals
PCT = 100.0


@register("strategy", NAME)
class BensdorpAdxReversal(PanelStrategy):
    name = NAME
    description = "ADX7 > 45 above sma_100 + ATR with RSI3 <= 50; limit buy 4% lower; +1.2 ATR close or 6 days."
    default_params: dict[str, Any] = {
        "min_avg_volume": 500_000.0,  # card: 50-day average volume >= 500k
        "min_dollar_volume": 2_500_000.0,  # card: dollar volume >= $2.5M
        "min_atr_pct": 4.0,  # card: ATR%(10) >= 4
        "adx_min": 45.0,  # card: ADX(7) > 45 (book value; the published code default 20.5 is not registered)
        "trend_atr_mult": 1.0,  # card: close >= SMA(100) + ATR(10)
        "rsi_max": 50.0,  # card: RSI(3) <= 50
        "earnings_skip_sessions": 6,  # card: skip if sessions_to_expected_earnings <= 6
        "limit_pct": 0.04,  # card: limit 4% below the signal close
        "stop_atr_mult": 3.0,  # card: stop entry - 3 x ATR(10)
        "target_atr_mult": 1.2,  # card: target entry + 1.2 x ATR(10)
        "max_hold_days": 7,  # card: time exit at the close of the 6th session after the fill (fill session = 1)
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: no market gate
        P_MIN_RR: 0.0,  # the target is a rule exit, not a Signal target
    }
    features_required = [AVG_VOL]
    extra_features = [ADX, RSI, ATR, TREND_MA, DOLLAR_VOL]
    prior_columns: list[str] = []

    def should_exit(self, row: pd.Series, bars_held: int, position: PositionContext | None = None) -> bool:
        entry, atr, close = entry_price(position), entry_feature(position, ATR), row.get("close")
        if entry is None or atr is None or not finite(close):
            return False
        return float(close) >= entry + float(self.params["target_atr_mult"]) * atr

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime) or TO_EXP not in panel.columns:
            return []
        p = self.params
        rows = c1.rows(self, panel, as_of)
        if rows.empty:
            return []
        close, atr = rows["close"], rows[ATR]
        keep = (
            (rows[AVG_VOL] >= float(p["min_avg_volume"])) & (rows[DOLLAR_VOL] >= float(p["min_dollar_volume"]))
            & (atr / close * PCT >= float(p["min_atr_pct"])) & (rows[ADX] > float(p["adx_min"]))
            & (close >= rows[TREND_MA] + float(p["trend_atr_mult"]) * atr) & (rows[RSI] <= float(p["rsi_max"]))
            & ~(rows[TO_EXP] <= float(p["earnings_skip_sessions"]))
        )
        out: list[Signal] = []
        for _, row in rows.loc[keep].iterrows():
            limit = float(row["close"]) * (1.0 - float(p["limit_pct"]))
            stop = limit - float(p["stop_atr_mult"]) * float(row[ATR])
            if stop <= 0:
                continue
            sig = self.build_signal(
                row, as_of, entry=limit, stop=stop, target=None, score=float(row[ADX]),
                features={ADX: row[ADX], RSI: row[RSI], ATR: row[ATR], "signal_close": row["close"],
                          "max_hold_days": p["max_hold_days"]},
                notes=f"adx_7 {float(row[ADX]):.0f}, rsi_3 {float(row[RSI]):.0f} above {TREND_MA} + ATR; limit "
                f"{limit:.2f} for one session",
            )
            if sig:
                out.append(sig.model_copy(update={"entry_type": EntryType.LIMIT}))
        self.log_scan(as_of, len(rows), len(out))
        return out
