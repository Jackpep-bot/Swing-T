"""Price Zone Oscillator (Khalil & Steckler, long): docs/strategies/price_zone_oscillator.md (thinkorswim PZO LE/LX).

PZO(14) = 100 x EMA(signed close) / EMA(close) (features.extra `pzo_14`); ADX(14) > 18 = trending, direction from
EMA(60). Long entries: uptrend (ADX > 18, close > EMA60): PZO crosses above -40, or crosses above +15 for the first
time since it was last below 0 ("after crossing zero upward"); non-trend (ADX <= 18): PZO crosses above -40 or +15.
ADX > 18 with close < EMA60 is a downtrend: no long. Exit (`should_exit`, row-based): PZO was above +60 and turns
down, or close < EMA60 with PZO < 0. The non-trend LX path rules ("after dropping through +40 ...", "fails to reach
+40 and falls below -5") need the path since entry and are folded into those two tests. Stop 2 x atr_14 (card).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "price_zone_oscillator"
PZO, PREV_PZO, EMA, ADX = "pzo_14", "prev_pzo_14", "ema_60", "adx_14"


@register("strategy", NAME)
class PriceZoneOscillator(PanelStrategy):
    name = NAME
    description = "PZO(14) crosses -40 or +15 up in an ADX/EMA60 uptrend or a range; exit on +60 turn-down."
    default_params: dict[str, Any] = {
        "adx_trend": 18.0,  # card: ADX(14) > 18 = trending
        "oversold": -40.0,  # card: long when PZO crosses -40 upward
        "buy_level": 15.0,  # card: ... or crosses +15 upward (after crossing zero, in an uptrend)
        "overbought": 60.0,  # card: exit when PZO is above +60 then turns down
        "zero_lookback": 60,  # bars searched back for the last PZO < 0 (engine choice)
        "stop_atr_mult": 2.0,  # card
        "max_hold_days": 30,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["atr_14"]
    extra_features = [PZO, PREV_PZO, EMA, ADX]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        pzo, prev, ema = row.get(PZO), row.get(PREV_PZO), row.get(EMA)
        if not (finite(pzo) and finite(prev) and finite(ema)):
            return False
        turn_down = prev > float(self.params["overbought"]) and pzo < prev
        return bool(turn_down or (float(row["close"]) < ema and pzo < 0))

    def _entry(self, pzo: np.ndarray, trending: bool) -> str | None:
        now, prev = pzo[-1], pzo[-2]
        lo, up = float(self.params["oversold"]), float(self.params["buy_level"])
        if prev <= lo < now:
            return "cross_oversold"
        if not prev <= up < now:
            return None
        if not trending:
            return "cross_buy_level"
        below = np.flatnonzero(pzo[:-1] < 0)
        return "cross_buy_level_after_zero" if below.size and (pzo[below[-1] + 1 : -1] <= up).all() else None

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        view = as_of_view(panel, as_of, ["high", "low", "close", *self.required_features()])
        n = int(p["zero_lookback"])
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            if not all(finite(row[c]) for c in (PZO, PREV_PZO, EMA, ADX, "atr_14")):
                continue
            trending = float(row[ADX]) > float(p["adx_trend"])
            if trending and float(row["close"]) <= float(row[EMA]):
                continue  # downtrend mode: shorts only (not used)
            pzo = view.window(str(row[SYMBOL]), [PZO])[PZO][-n:]
            why = self._entry(pzo[np.isfinite(pzo)], trending) if np.isfinite(pzo[-2:]).all() else None
            if why is None:
                continue
            close = float(row["close"])
            sig = self.build_signal(
                row, as_of, entry=close, stop=close - float(p["stop_atr_mult"]) * float(row["atr_14"]), target=None,
                score=float(row[ADX]), features={PZO: row[PZO], ADX: row[ADX], EMA: row[EMA]},
                notes=f"PZO {why} ({'trend' if trending else 'range'} mode), PZO {float(row[PZO]):.1f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
