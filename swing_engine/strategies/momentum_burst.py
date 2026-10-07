"""Stockbee momentum burst (long).

Source (docs/research-raw/methods-sweeps, Pradeep Bonde): a >= 4% close-to-close move on higher volume
(`burst_4pct` = c/c1 >= 1.04 & v > v1 & v >= 100000) after a quiet day ("narrow range day or negative
day"), not already up three days in a row; "momentum dies down in 3 to 5 days" so the exit is a time stop
plus a stop below the entry bar's low. Disabled by default in settings.yaml (weak standalone evidence).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, TREND_FLAT, PanelStrategy, finite

NAME = "momentum_burst"


@register("strategy", NAME)
class MomentumBurst(PanelStrategy):
    name = NAME
    description = "burst_4pct after a <= 2% prior move and not up 3 days; stop below entry bar low; 3-5 day exit."
    default_params: dict[str, Any] = {
        "max_prev_move": 0.02,  # |prior day return| <= 2%
        "max_up_days": 2,  # up_days_3 (up closes in the last 3 bars incl. today) must be <= this
        "min_volume": 100_000,  # Stockbee scan floor
        "hold_days_min": 3,  # informational: expected burst duration
        "max_hold_days": 5,  # time exit; research.backtest reads this key (STRATEGY_HOLD_PARAM) and should_exit uses it
        "stop_atr_buffer": 0.0,  # stop = entry bar low - stop_atr_buffer * atr_14
        "target_r": 2.0,  # reference target so reward_risk is defined; time exit is primary
        P_MIN_TREND: TREND_DOWN,  # no trend filter by default (Stockbee does not require one)
        P_MIN_MARKET_TREND: TREND_FLAT,
        P_MIN_RR: 1.0,
    }
    features_required = ["burst_4pct", "up_days_3", "ret_1d", "atr_14", "avg_vol_20d", "trend_state"]
    prior_columns = [*PanelStrategy.prior_columns, "ret_1d"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        rows = self.rows_as_of(panel, as_of)
        max_prev = float(self.params["max_prev_move"])
        max_up = int(self.params["max_up_days"])
        min_vol = float(self.params["min_volume"])
        buffer = float(self.params["stop_atr_buffer"])
        target_r = float(self.params["target_r"])
        out: list[Signal] = []
        for _, row in rows.iterrows():
            flag, up3, ret, prior_ret, atr = (
                row["burst_4pct"], row["up_days_3"], row["ret_1d"], row["prior_ret_1d"], row["atr_14"],
            )
            if not (finite(flag) and float(flag) >= 1.0):
                continue
            if not all(finite(x) for x in (up3, ret, prior_ret, atr)) or not self.trend_ok(row):
                continue
            if abs(float(prior_ret)) > max_prev or int(up3) > max_up:
                continue
            if float(row["volume"]) < min_vol or float(atr) <= 0:
                continue
            close, low = float(row["close"]), float(row["low"])
            stop = low - buffer * float(atr)
            target = close + target_r * (close - stop)
            vol_ratio = self.volume_ratio(row, "avg_vol_20d")
            score = (vol_ratio if finite(vol_ratio) else 1.0) * (1.0 + float(ret))
            sig = self.build_signal(
                row,
                as_of,
                entry=close,
                stop=stop,
                target=target,
                score=score,
                features={
                    "ret_1d": ret,
                    "prior_ret_1d": prior_ret,
                    "up_days_3": up3,
                    "volume_ratio": vol_ratio,
                    "atr_14": atr,
                    "max_hold_days": self.params["max_hold_days"],
                },
                notes=f"4% burst {float(ret) * 100:+.1f}% from quiet day; time exit {self.params['max_hold_days']}d",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
