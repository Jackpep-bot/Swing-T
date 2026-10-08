"""Ken Calhoun four-day breakout (long): docs/strategies/calhoun_four_day_breakout.md (thinkorswim FourDayBreakoutLE).

Signal at the close when the last `pattern_len` candles are all bullish (close > open, i.e. min ret_intraday > 0),
the close is above the trend average (card: sma_50; replay sma_20 too) and trend_state >= 0. Entry is a buy stop
(`EntryType.STOP`, valid one session) at the pattern high + 0.15 x atr_14 (the card's ATR version of the $0.50
breakout amount). Stop = pattern low - 0.1 x atr_14; target 2R; 10-session time stop. The engine's breakeven/trail
overlay stays on (card: engine defaults manage the exit).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import EntryType, Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, TREND_FLAT, PanelStrategy, finite

NAME = "calhoun_four_day_breakout"


def _extras(n: int) -> list[str]:
    return [f"min_{n}_of_ret_intraday", f"high_{n}", f"low_{n}"]


@register("strategy", NAME)
class CalhounFourDayBreakout(PanelStrategy):
    name = NAME
    description = "Four bullish candles above sma_50; buy stop over the pattern high, stop under the pattern low."
    default_params: dict[str, Any] = {
        "pattern_len": 4,  # card: pattern length default 4 candles
        "trend_ma": "sma_50",  # card: close > sma_50 (replay sma_20 as well; TOS default length unverified)
        "entry_offset_atr": 0.15,  # card: buy stop at pattern_high_4 + 0.15 x atr_14
        "stop_offset_atr": 0.1,  # card: stop = pattern_low_4 - 0.1 x atr_14
        "target_r": 2.0,  # card: target = entry + 2R
        "max_hold_days": 10,  # card
        P_MIN_TREND: TREND_FLAT,  # card: trend_state >= 0
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card says 2.0, but the target IS 2R: a 2.0 floor drops ~8% of signals on float rounding
    }
    features_required = ["atr_14", "trend_state"]
    extra_features = _extras(4)

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        self.extra_features = _extras(int(self.params["pattern_len"]))

    def required_features(self) -> list[str]:
        return [*super().required_features(), str(self.params["trend_ma"])]

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        bull, hi_col, lo_col = self.extra_features
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        out: list[Signal] = []
        for _, row in rows.iterrows():
            ma, atr, bull_min, hi, lo = row[str(p["trend_ma"])], row["atr_14"], row[bull], row[hi_col], row[lo_col]
            if not (self.trend_ok(row) and all(finite(x) for x in (ma, atr, bull_min, hi, lo))):
                continue
            if float(bull_min) <= 0 or float(row["close"]) <= float(ma):
                continue
            entry = float(hi) + float(p["entry_offset_atr"]) * float(atr)
            stop = float(lo) - float(p["stop_offset_atr"]) * float(atr)
            sig = self.build_signal(
                row, as_of, entry=entry, stop=stop, target=entry + float(p["target_r"]) * (entry - stop),
                score=-(entry - stop) / entry,  # tighter patterns first
                features={"pattern_high": hi, "pattern_low": lo, "atr_14": atr, "max_hold_days": p["max_hold_days"]},
                notes=f"{p['pattern_len']} bullish candles; buy stop {entry:.2f} over pattern high {float(hi):.2f}",
            )
            if sig:
                out.append(sig.model_copy(update={"entry_type": EntryType.STOP}))
        self.log_scan(as_of, len(rows), len(out))
        return out
