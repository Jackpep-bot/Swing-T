"""RSITrend (Kevin Luo, S&C Jun 2015; thinkorswim) (long), docs/strategies/rsi_trend_zigzag_luo.md (catalog B19).

Buy when rsi_14 crosses above 30 only while a NON-repainting close ZigZag (`zz_trend_5`, features.extra.zigzag_np:
swings confirmed after a 5% reversal) shows an uptrend: the last two confirmed highs and lows both higher. Stop = the
lower of the last confirmed swing low and entry - 1.5 x atr_14; target = the last confirmed swing high when above the
entry (then min_reward_risk 1.5), else none. Exit when rsi_14 crosses below 70 or the ZigZag trend is no longer up;
30-session cap. RSI(14) 30/70 and 5% are the card's assumed defaults (tos page gives none).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, finite

NAME = "rsi_trend_zigzag_luo"
RSI, PREV_RSI = "rsi_14", "prev_rsi_14"


@register("strategy", NAME)
class RSITrendZigZag(PanelStrategy):
    name = NAME
    description = "rsi_14 crosses above 30 while the confirmed 5% ZigZag makes higher highs and higher lows."
    default_params: dict[str, Any] = {
        "zz_pct": 5,  # card: settings zz_pct 5 (ZigZag reversal 3-10%)
        "rsi_os": 30.0,  # card: oversold 30
        "rsi_ob": 70.0,  # card: exit on a cross below 70
        "stop_atr_mult": 1.5,  # card: stop min(swing low, entry - 1.5 x atr_14)
        "max_hold_days": 30,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 1.5,  # card: when the swing-high target exists
    }
    features_required = ["atr_14", RSI]
    extra_features = [PREV_RSI, "zz_trend_5", "zz_high_5", "zz_low_5"]

    def _zz(self) -> tuple[str, str, str]:
        n = int(self.params["zz_pct"])
        return f"zz_trend_{n}", f"zz_high_{n}", f"zz_low_{n}"

    def required_features(self) -> list[str]:
        return [*self.features_required, PREV_RSI, *self._zz()]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        trend = row.get(self._zz()[0])
        if finite(trend) and float(trend) != 1.0:
            return True
        rsi, prev = row.get(RSI), row.get(PREV_RSI)
        ob = float(self.params["rsi_ob"])
        return finite(rsi) and finite(prev) and float(prev) >= ob > float(rsi)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        rows = c1.rows(self, panel, as_of)
        trend_col, hi_col, lo_col = self._zz()
        os_ = float(self.params["rsi_os"])
        rows = rows.loc[(rows[trend_col] == 1.0) & (rows[PREV_RSI] <= os_) & (rows[RSI] > os_)]
        out: list[Signal] = []
        for _, row in rows.iterrows():
            atr, swing_low, swing_high = row["atr_14"], row[lo_col], row[hi_col]
            if not (finite(atr) and finite(swing_low)):
                continue
            close = float(row["close"])
            stop = min(float(swing_low), close - float(self.params["stop_atr_mult"]) * float(atr))
            target = float(swing_high) if finite(swing_high) and float(swing_high) > close else None
            sig = self.build_signal(row, as_of, entry=close, stop=stop, target=target, score=float(row[RSI]) - os_,
                                    features={RSI: row[RSI], "swing_low": swing_low, "swing_high": swing_high,
                                              "max_hold_days": self.params["max_hold_days"]},
                                    notes=f"RSI crosses {os_:g} in a ZigZag uptrend; swing low {float(swing_low):.2f}")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
