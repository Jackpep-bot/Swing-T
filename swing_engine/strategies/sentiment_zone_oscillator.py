"""Sentiment Zone Oscillator (long): docs/strategies/sentiment_zone_oscillator.md (thinkorswim SentimentZoneOscillator).

SZO = 100 x TEMA_14(sign(close - prev close)) / 14 (`szo_14`). Dynamic levels over 30 bars: OS = max - 95% x range.
Buy on any of: (a) SMA30(SZO) crosses above 0 with close > EMA60; (b) SZO < OS with SMA30(SZO) rising and close > EMA60;
(c) SZO crosses above OS with SMA30(SZO) > 0 and EMA60 rising. Sell on SMA30(SZO) crossing below 0, or SZO crossing below
the exit level (0.98 x 100 / length) while SMA30(SZO) falls. Entry next open; engine stop = 10-bar low - 0.1 x atr_14;
reference target 4R. Port defaults (14 / 30 / 95% / 60) are unverified against the article.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, RollingSpec, finite

NAME = "sentiment_zone_oscillator"
SZO, SZO_PREV = "szo_14", "prev_szo_14"
AVG, AVG_PREV = "sma_30_of_szo_14", "prev_sma_30_of_szo_14"
HI, LO, HI_PREV, LO_PREV = "max_30_of_szo_14", "min_30_of_szo_14", "prev_max_30_of_szo_14", "prev_min_30_of_szo_14"
EMA, EMA_PREV = "ema_60", "prev_ema_60"
SZO_LENGTH = 14  # column names above carry the card's length 14 / long length 30 / SMA 30 / EMA 60


@register("strategy", NAME)
class SentimentZoneOscillator(PanelStrategy):
    name = NAME
    description = "SZO zone entries over EMA60 (SMA30 zero cross, oversold zone, OS cross); SZO rule exits."
    default_params: dict[str, Any] = {
        "zone_pct": 0.95,  # card: pct 95% of the 30-bar SZO range
        "exit_level": 0.98 * 100.0 / SZO_LENGTH,  # card: exit_level = 0.98 x 100 / length
        "stop_lookback": 10,  # card: stop = low of last 10 bars - 0.1 x atr_14
        "stop_atr_offset": 0.1,
        "target_r": 4.0,  # card: reference target_r 4.0
        "max_hold_days": 40,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 1.0,  # card
    }
    features_required = ["atr_14"]
    extra_features = [SZO, SZO_PREV, AVG, AVG_PREV, HI, LO, HI_PREV, LO_PREV, EMA, EMA_PREV]

    def _os(self, hi: float, lo: float) -> float:
        return hi - float(self.params["zone_pct"]) * (hi - lo)

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        s, sp, a, ap = (row.get(c) for c in (SZO, SZO_PREV, AVG, AVG_PREV))
        if not all(finite(x) for x in (s, sp, a, ap)):
            return False
        lvl = float(self.params["exit_level"])
        return bool((a < 0 <= ap) or (s < lvl <= sp and a < ap))

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        stop_spec = RollingSpec("low", "min", int(p["stop_lookback"]))
        rows = self.rows_as_of(panel, as_of, rolling=[stop_spec], required=self.required_features())
        out: list[Signal] = []
        for _, row in rows.iterrows():
            vals = [row[c] for c in (SZO, SZO_PREV, AVG, AVG_PREV, HI, LO, HI_PREV, LO_PREV, EMA, EMA_PREV, "atr_14")]
            if not all(finite(x) for x in [*vals, row[stop_spec.out]]):
                continue
            s, sp, a, ap, hi, lo, hip, lop, e, ep, atr = (float(x) for x in vals)
            close = float(row["close"])
            os_now, os_prev = self._os(hi, lo), self._os(hip, lop)
            rule = ("a" if a > 0 >= ap and close > e else
                    "b" if s < os_now and a > ap and close > e else
                    "c" if s > os_now and sp <= os_prev and a > 0 and e > ep else None)
            if rule is None:
                continue
            stop = float(row[stop_spec.out]) - float(p["stop_atr_offset"]) * atr
            sig = self.build_signal(
                row, as_of, entry=close, stop=stop, target=close + float(p["target_r"]) * (close - stop), score=a,
                features={SZO: s, AVG: a, "szo_os": os_now, EMA: e, "max_hold_days": p["max_hold_days"]},
                notes=f"SZO buy rule ({rule}): SZO {s:.2f}, SMA30 {a:.2f}, OS {os_now:.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
