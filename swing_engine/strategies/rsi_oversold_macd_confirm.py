"""RSI(14) oversold recovery confirmed by a MACD signal cross (long): docs/strategies/rsi_oversold_macd_confirm.md.

On the close of t: MACD(12,26) crosses above its 9-EMA signal; RSI(14) crossed from below 30 back to 30+ within the
last `pair_window` bars; RSI(14) was below 30 within the last 10 bars; RSI(14) <= 70 (skip overbought crosses).
The source gives no exits; engine choices from the card: next-open entry, stop = lowest low of 10 bars - 0.5 x atr_14,
reference target sma_50 when above the entry, exit on a MACD cross down or RSI(14) > 70, 15-session time stop.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "rsi_oversold_macd_confirm"
PREV_MACD, PREV_SIG = "prev_macd", "prev_macd_signal"


@register("strategy", NAME)
class RsiOversoldMacdConfirm(PanelStrategy):
    name = NAME
    description = "RSI(14) back above 30 within 5 bars of a MACD signal-line up-cross; exit on the cross down."
    default_params: dict[str, Any] = {
        "rsi_oversold": 30.0,  # card: RSI(14) below 30 then back above 30
        "rsi_overbought": 70.0,  # card: skip when RSI(14) > 70; exit when RSI(14) > 70
        "pair_window": 5,  # card: RSI recovery within the last 5 bars of the MACD cross
        "oversold_lookback": 10,  # card: rsi14_min_10 < 30
        "stop_lookback": 10,  # card: stop = min(low over 10 bars) - 0.5 x atr_14
        "stop_atr_offset": 0.5,
        "target_ma": "sma_50",  # card: reference target sma_50 when above the entry
        "max_hold_days": 15,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: rule exit
    }
    features_required = ["rsi_14", "macd", "macd_signal", "atr_14", "sma_50"]
    extra_features = [PREV_MACD, PREV_SIG]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        m, s, r = row.get("macd"), row.get("macd_signal"), row.get("rsi_14")
        return (finite(m) and finite(s) and m < s) or (finite(r) and r > float(self.params["rsi_overbought"]))

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        lo_lvl, hi_lvl, pair = float(p["rsi_oversold"]), float(p["rsi_overbought"]), int(p["pair_window"])
        view = as_of_view(panel, as_of, ["open", "high", "low", "close", *self.required_features()])
        cur = view.current
        xup = (cur["macd"] > cur["macd_signal"]) & (cur[PREV_MACD] <= cur[PREV_SIG]) & (cur["rsi_14"] <= hi_lvl)
        out: list[Signal] = []
        for _, row in cur.loc[xup.fillna(False)].iterrows():
            w = view.window(str(row[SYMBOL]), ("rsi_14", "low"))
            rsi, t = w["rsi_14"], len(w["rsi_14"]) - 1
            n = max(pair + 1, int(p["oversold_lookback"]), int(p["stop_lookback"]))
            if t < n or not finite(row["atr_14"]):
                continue
            recent = rsi[t - pair - 1 : t + 1]  # cross bar j in t-pair..t (bars since <= pair)
            if not ((recent[:-1] < lo_lvl) & (recent[1:] >= lo_lvl)).any():
                continue
            if not (rsi[t - int(p["oversold_lookback"]) + 1 : t + 1] < lo_lvl).any():
                continue
            close = float(row["close"])
            stop = float(w["low"][t - int(p["stop_lookback"]) + 1 : t + 1].min()) - float(p["stop_atr_offset"]) * float(row["atr_14"])
            ma = row[str(p["target_ma"])]
            target = float(ma) if finite(ma) and float(ma) > close else None
            sig = self.build_signal(
                row, as_of, entry=close, stop=stop, target=target, score=lo_lvl - float(rsi[t - int(p["oversold_lookback"]) + 1 : t + 1].min()),
                features={"rsi_14": rsi[t], "macd": row["macd"], "macd_signal": row["macd_signal"],
                          "max_hold_days": p["max_hold_days"]},
                notes=f"RSI(14) {rsi[t]:.0f} back over {lo_lvl:.0f}; MACD crossed its signal",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(cur), len(out))
        return out
