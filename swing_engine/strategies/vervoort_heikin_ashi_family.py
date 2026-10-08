"""Vervoort Heikin-Ashi family (long): docs/strategies/vervoort_heikin_ashi_family.md (thinkorswim SVE* strategies).

`variant` (both fully specified up to their lengths, which the thinkorswim pages do not state: engine defaults below):
* `ha_typ_cross` (SVEHaTypCross): A = EMA(hlc3, typical_length), B = EMA(Heikin-Ashi ohlc4, ha_length). Buy when A
  crosses above B on a bullish bar (close > open); exit when A crosses below B on a bearish bar.
* `svesc` (SVESC): A = SMA(hlc3, length), B = SMA(HA ohlc4, length). Buy when A crosses above B on a bullish bar;
  exit when close < SMA(close, exit_length) and close < open.
Not built (card: formulas unverified): HACOLT, SVEZLRBPercB, VolatilityBand. Entry next open; engine stop = lowest
HA low of 3 bars - 0.1 x atr_14; reference target 4R; 40-session time stop.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, finite

NAME = "vervoort_heikin_ashi_family"
HA_TYP, SVESC = "ha_typ_cross", "svesc"


def _columns(p: dict[str, Any]) -> dict[str, str]:
    """Named panel columns for the variant: a, b (and prev_ copies), exit average, stop low."""
    if p["variant"] == HA_TYP:
        a, b = f"ema_{int(p['typical_length'])}_of_hlc3", f"ema_{int(p['ha_length'])}_of_ha_ohlc4"
    elif p["variant"] == SVESC:
        a, b = f"sma_{int(p['length'])}_of_hlc3", f"sma_{int(p['length'])}_of_ha_ohlc4"
    else:
        raise ValueError(f"{NAME}: unknown variant {p['variant']!r}")
    return {"a": a, "b": b, "a_prev": f"prev_{a}", "b_prev": f"prev_{b}", "exit": f"sma_{int(p['exit_length'])}",
            "stop": f"min_{int(p['stop_lookback'])}_of_ha_low"}


@register("strategy", NAME)
class VervoortHeikinAshi(PanelStrategy):
    name = NAME
    description = "Typical price vs Heikin-Ashi average crosses on a bullish bar (SVEHaTypCross / SVESC)."
    default_params: dict[str, Any] = {
        "variant": HA_TYP,  # card: implement SVEHaTypCross and SVESC first
        "typical_length": 9,  # engine default; thinkorswim page states none (card: unverified)
        "ha_length": 9,  # engine default (unverified)
        "length": 9,  # SVESC average length, engine default (unverified)
        "exit_length": 5,  # SVESC exit SMA(close) length, engine default (unverified)
        "stop_lookback": 3,  # card: stop = min(haLow over last 3 bars) - 0.1 x atr_14
        "stop_atr_offset": 0.1,
        "target_r": 4.0,  # card: reference target_r 4.0
        "max_hold_days": 40,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 1.0,  # card
    }
    features_required = ["atr_14"]
    extra_features: list[str] = []  # set below the class: both variants' columns at the default lengths

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        self.cols = _columns(self.params)
        self.extra_features = list(self.cols.values())

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        c = self.cols
        close, open_ = float(row["close"]), float(row["open"])
        if self.params["variant"] == SVESC:
            x = row.get(c["exit"])
            return finite(x) and close < float(x) and close < open_
        a, b, ap, bp = (row.get(c[k]) for k in ("a", "b", "a_prev", "b_prev"))
        return all(finite(v) for v in (a, b, ap, bp)) and ap >= bp and a < b and close < open_

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p, c = self.params, self.cols
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        out: list[Signal] = []
        for _, row in rows.iterrows():
            vals = [row[c[k]] for k in ("a", "b", "a_prev", "b_prev", "stop")] + [row["atr_14"]]
            if not all(finite(v) for v in vals):
                continue
            a, b, ap, bp, ha_low, atr = (float(v) for v in vals)
            close = float(row["close"])
            if not (ap <= bp and a > b and close > float(row["open"])):
                continue
            stop = ha_low - float(p["stop_atr_offset"]) * atr
            sig = self.build_signal(
                row, as_of, entry=close, stop=stop, target=close + float(p["target_r"]) * (close - stop),
                score=(a - b) / atr,
                features={c["a"]: a, c["b"]: b, "atr_14": atr, "max_hold_days": p["max_hold_days"]},
                notes=f"{p['variant']}: {c['a']} {a:.2f} crossed over {c['b']} {b:.2f} on a bullish bar",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out


#: class level: both variants' columns at the default lengths, so the nightly panel (built from classes) serves either
VervoortHeikinAshi.extra_features = list(dict.fromkeys(
    c for v in (HA_TYP, SVESC) for c in _columns({**VervoortHeikinAshi.default_params, "variant": v}).values()))
