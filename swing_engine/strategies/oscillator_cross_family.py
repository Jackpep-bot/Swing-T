"""Vendor oscillator-cross strategies (long; a negative control): docs/strategies/oscillator_cross_family.md.

`variant` (entry on the close of t, next-open fill unless noted; exit = the vendor's reverse condition, `should_exit`):
* `rsi_30_70`: RSI(14) crosses above 30; exit when it crosses below 70.
* `stoch_20_80`: slow %K(14,3) crosses above %D(3) with both < 20; exit on the cross down with both > 80.
* `macd_signal` / `macd_hist_zero` (identical rules): MACD crosses above its 9-EMA signal; exit on the reverse cross.
* `momentum_rising`: momentum > 0 and rising, buy stop (`EntryType.STOP`) at the bar high + $0.01 for the next session;
  exit when momentum is < 0 and falling. Momentum is roc_12 (100 x C/C[12] - 1): same sign as C - C[12], "rising"
  measured in percent rather than dollars (approximation).
* `dmi_osc`: +DI(10) - -DI(10) crosses above 0; exit on the cross below 0.
Not built: `pct_r` (stateful setup-cancel rule), `pmo` (lengths unverified), `spectrum_bars` (no exit, n unspecified).
Engine stop entry - 2 x atr_14; no target; 20-session time stop.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import EntryType, Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, finite

NAME = "oscillator_cross_family"
K, D = "stoch_k_14_3", "stoch_d_14_3_3"
PDI, MDI = "plus_di_10", "minus_di_10"

Rule = Callable[[Callable[[str], float], dict[str, Any]], bool]


def _up(a: float, ap: float, b: float, bp: float) -> bool:
    return ap <= bp and a > b


def _dmi(g: Callable[[str], float], prev: bool) -> float:
    return g(f"prev_{PDI}") - g(f"prev_{MDI}") if prev else g(PDI) - g(MDI)


# variant -> (extra columns, entry rule, exit rule); g(col) reads a float from the row
VARIANTS: dict[str, tuple[list[str], Rule, Rule]] = {
    "rsi_30_70": (
        ["prev_rsi_14"],
        lambda g, p: _up(g("rsi_14"), g("prev_rsi_14"), p["rsi_low"], p["rsi_low"]),
        lambda g, p: _up(p["rsi_high"], p["rsi_high"], g("rsi_14"), g("prev_rsi_14")),
    ),
    "stoch_20_80": (
        [K, D, f"prev_{K}", f"prev_{D}"],
        lambda g, p: _up(g(K), g(f"prev_{K}"), g(D), g(f"prev_{D}")) and max(g(K), g(D)) < p["stoch_low"],
        lambda g, p: _up(g(D), g(f"prev_{D}"), g(K), g(f"prev_{K}")) and min(g(K), g(D)) > p["stoch_high"],
    ),
    "macd_signal": (
        ["prev_macd", "prev_macd_signal"],
        lambda g, p: _up(g("macd"), g("prev_macd"), g("macd_signal"), g("prev_macd_signal")),
        lambda g, p: _up(g("macd_signal"), g("prev_macd_signal"), g("macd"), g("prev_macd")),
    ),
    "momentum_rising": (
        ["roc_12", "prev_roc_12"],
        lambda g, p: g("roc_12") > 0 and g("roc_12") > g("prev_roc_12"),
        lambda g, p: g("roc_12") < 0 and g("roc_12") < g("prev_roc_12"),
    ),
    "dmi_osc": (
        [PDI, MDI, f"prev_{PDI}", f"prev_{MDI}"],
        lambda g, p: _up(_dmi(g, False), _dmi(g, True), 0.0, 0.0),
        lambda g, p: _up(0.0, 0.0, _dmi(g, False), _dmi(g, True)),
    ),
}
VARIANTS["macd_hist_zero"] = VARIANTS["macd_signal"]  # card: MACD - signal crossing 0 is the same event
STOP_ENTRY = {"momentum_rising"}


def _getter(row: pd.Series) -> Callable[[str], float]:
    def g(col: str) -> float:
        v = row.get(col)
        if not finite(v):
            raise ValueError(col)
        return float(v)

    return g


@register("strategy", NAME)
class OscillatorCrossFamily(PanelStrategy):
    name = NAME
    description = "Textbook oscillator crosses (RSI 30/70, stochastic 20/80, MACD, momentum, DMI); reverse-cross exits."
    default_params: dict[str, Any] = {
        "variant": "rsi_30_70",  # card: default variant rsi_30_70
        "rsi_low": 30.0,  # card: RSI(14) crosses above 30 ...
        "rsi_high": 70.0,  # ... exit when it crosses below 70
        "stoch_low": 20.0,  # card: %K/%D cross with both < 20 ...
        "stoch_high": 80.0,  # ... exit cross with both > 80
        "stop_tick": 0.01,  # card: tick offsets -> $0.01 (momentum_rising buy stop)
        "stop_atr_mult": 2.0,  # card: stop entry - 2 x atr_14
        "max_hold_days": 20,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["rsi_14", "macd", "macd_signal", "atr_14"]
    #: class level: every variant's columns, so the nightly panel (built from classes) serves any `variant` setting
    extra_features = list(dict.fromkeys(c for cols, _, _ in VARIANTS.values() for c in cols))

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        if self.params["variant"] not in VARIANTS:
            raise ValueError(f"{NAME}: unknown variant {self.params['variant']!r}")
        self.extra_features = VARIANTS[str(self.params["variant"])][0]

    def _rule(self, row: pd.Series, which: int) -> bool:
        try:
            return bool(VARIANTS[str(self.params["variant"])][which](_getter(row), self.params))
        except ValueError:  # an input is NaN (warm-up)
            return False

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"]) or self._rule(row, 2)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        stop_entry = p["variant"] in STOP_ENTRY
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        out: list[Signal] = []
        for _, row in rows.iterrows():
            atr = row["atr_14"]
            if not finite(atr) or not self._rule(row, 1):
                continue
            entry = float(row["high"]) + float(p["stop_tick"]) if stop_entry else float(row["close"])
            sig = self.build_signal(
                row, as_of, entry=entry, stop=entry - float(p["stop_atr_mult"]) * float(atr), target=None, score=0.0,
                features={"atr_14": atr, "max_hold_days": p["max_hold_days"]},
                notes=f"oscillator cross {p['variant']}",
            )
            if sig:
                out.append(sig.model_copy(update={"entry_type": EntryType.STOP}) if stop_entry else sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
