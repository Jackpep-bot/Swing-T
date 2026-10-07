"""Connors RSI-2 mean reversion (long).

Source (docs/research-raw/methods-sweeps, Connors & Alvarez 2008 as reproduced by LuxAlgo/backtrex): long
only when close > 200-day SMA; buy when RSI(2) closes below 10 (stricter variant < 5); exit when the close
is back above a short SMA or RSI(2) recovers above 70. This port adds a protective ATR stop and a time stop.
The reference target is the exit MA, so reward_risk is honest (mean reversion is a thin, high-win-rate edge).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, finite

NAME = "rsi2_meanrev"


@register("strategy", NAME)
class RSI2MeanRev(PanelStrategy):
    name = NAME
    description = "close > sma_200 and rsi_2 < 10; exit close > sma_10 or rsi_2 > 70 or 5-day time stop."
    default_params: dict[str, Any] = {
        "rsi_entry": 10.0,  # rsi_2 < rsi_entry
        "rsi_exit": 70.0,  # exit when rsi_2 > rsi_exit
        "trend_ma": "sma_200",  # close must be above this column
        "exit_ma": "sma_10",  # exit when close > this column; also the reference target
        "max_hold_days": 5,  # time stop; research.backtest reads this key (STRATEGY_HOLD_PARAM)
        "stop_atr_mult": 2.0,  # protective stop = entry - stop_atr_mult * atr_14
        P_MIN_MARKET_TREND: TREND_DOWN,  # Connors gates on the instrument's own 200-day, not the index
        P_MIN_RR: 0.0,  # low-R by design; risk.min_reward_risk decides portfolio admission
    }
    features_required = ["rsi_2", "atr_14"]

    def required_features(self) -> list[str]:
        return [*self.features_required, str(self.params["trend_ma"]), str(self.params["exit_ma"])]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        exit_ma = row.get(str(self.params["exit_ma"]))
        if finite(exit_ma) and float(row["close"]) > float(exit_ma):
            return True
        rsi = row.get("rsi_2")
        return finite(rsi) and float(rsi) > float(self.params["rsi_exit"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        trend_col, exit_col = str(self.params["trend_ma"]), str(self.params["exit_ma"])
        rsi_entry = float(self.params["rsi_entry"])
        stop_mult = float(self.params["stop_atr_mult"])
        out: list[Signal] = []
        for _, row in rows.iterrows():
            rsi, atr, trend_ma, exit_ma = row["rsi_2"], row["atr_14"], row[trend_col], row[exit_col]
            if not all(finite(x) for x in (rsi, atr, trend_ma)):
                continue
            close = float(row["close"])
            if close <= float(trend_ma) or float(rsi) >= rsi_entry or float(atr) <= 0:
                continue
            stop = close - stop_mult * float(atr)
            target = float(exit_ma) if finite(exit_ma) and float(exit_ma) > close else None
            sig = self.build_signal(
                row,
                as_of,
                entry=close,
                stop=stop,
                target=target,
                score=rsi_entry - float(rsi),  # deeper oversold ranks higher
                features={
                    "rsi_2": rsi,
                    "atr_14": atr,
                    trend_col: trend_ma,
                    exit_col: exit_ma,
                    "max_hold_days": self.params["max_hold_days"],
                    "rsi_exit": self.params["rsi_exit"],
                },
                notes=f"rsi_2 {float(rsi):.1f} < {rsi_entry:g} above {trend_col}; exit > {exit_col} / rsi > "
                f"{float(self.params['rsi_exit']):g} / {int(self.params['max_hold_days'])}d",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
