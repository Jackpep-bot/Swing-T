"""Moving-average crossover family (long), docs/strategies/ma_crossover_family.md: the negative-control baseline.

`variant` picks a published vendor default (do not tune; the variant exists to be beaten). Each preset is
(fast, slow, entry band, exit fast, exit slow, exit band): entry when `fast` crosses above `band x slow` at the close
(first bar of the cross), exit (`should_exit`) when `exit fast < exit band x exit slow`. `three_line` instead enters
on the first bar with SMA4 > SMA9 > SMA18 and exits when that order breaks.

| variant | entry | exit |
|---|---|---|
| golden_cross (Calhoun) | SMA50 x SMA200 | close < SMA50 (set max_hold_days 120) |
| vwma_sma (Calhoun) | VWMA50 x SMA70 | VWMA50 < SMA70 |
| breen_band | close >= 1.03 x SMA50 | close <= 0.96 x SMA50 (MA length not published: SMA50 is an engine choice) |
| price_ma (TOS/TS) | close x SMA9 | close < SMA9 |
| two_line (TS MovAvg2Line, default) | SMA9 x SMA18 | SMA9 < SMA18 |
| three_line (TS MovAvg3Line) | SMA4 > SMA9 > SMA18 first bar | order breaks |
| mhl_ma (Apirine) | SMA20 x SMA20 of (HH10 + LL10) / 2 | reverse cross |
| webull_5_10_20 | SMA5 x SMA10 | Sell 1: SMA5 < SMA10 |

Entry next open. Stop entry - 2 x atr_14 (engine-required; the originals have none). No target. Long only.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, PanelStrategy, finite

NAME = "ma_crossover_family"
THREE_LINE = "three_line"
THREE_LINE_MAS = ("sma_4", "sma_9", "sma_18")
#: variant -> (fast, slow, entry band, exit fast, exit slow, exit band); docs/strategies/ma_crossover_family.md table
VARIANTS: dict[str, tuple[str, str, float, str, str, float]] = {
    "golden_cross": ("sma_50", "sma_200", 1.0, "close", "sma_50", 1.0),
    "vwma_sma": ("vwma_50", "sma_70", 1.0, "vwma_50", "sma_70", 1.0),
    "breen_band": ("close", "sma_50", 1.03, "close", "sma_50", 0.96),
    "price_ma": ("close", "sma_9", 1.0, "close", "sma_9", 1.0),
    "two_line": ("sma_9", "sma_18", 1.0, "sma_9", "sma_18", 1.0),
    THREE_LINE: ("sma_4", "sma_9", 1.0, "sma_9", "sma_18", 1.0),  # entry/exit special-cased below
    "mhl_ma": ("sma_20", "sma_20_of_hl_mid_10", 1.0, "sma_20", "sma_20_of_hl_mid_10", 1.0),
    "webull_5_10_20": ("sma_5", "sma_10", 1.0, "sma_5", "sma_10", 1.0),
}
_MAS = sorted({c for v in VARIANTS.values() for c in (v[0], v[1], v[3], v[4])} - {"close"})
_CONTRACT_MAS = {"sma_10", "sma_50", "sma_200"}


@register("strategy", NAME)
class MaCrossoverFamily(PanelStrategy):
    name = NAME
    description = "Vendor MA-crossover presets (default SMA9 x SMA18); exit on the reverse cross; 2 ATR stop."
    default_params: dict[str, Any] = {
        "variant": "two_line",  # card: default two_line
        "stop_atr_mult": 2.0,  # card: stop = entry - 2 x atr_14
        "max_hold_days": 60,  # card: 60 for fast variants (120 for golden_cross)
        P_MIN_TREND: TREND_DOWN,  # standalone crossovers, no filter (negative control)
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["atr_14", "trend_state"]
    extra_features = [*(c for c in _MAS if c not in _CONTRACT_MAS), *(f"prev_{c}" for c in _MAS)]
    engine_trail = False  # exit is the reverse cross (card)

    @property
    def preset(self) -> tuple[str, str, float, str, str, float]:
        return VARIANTS[str(self.params["variant"])]

    def _cols(self) -> list[str]:
        if self.params["variant"] == THREE_LINE:
            return list(THREE_LINE_MAS)
        fast, slow, _, xf, xs, _ = self.preset
        return list(dict.fromkeys(c for c in (fast, slow, xf, xs) if c != "close"))

    def required_features(self) -> list[str]:
        cols = self._cols()
        return [*self.features_required, *cols, *(f"prev_{c}" for c in cols)]

    @staticmethod
    def _above(row: pd.Series, fast: str, slow: str, band: float) -> bool:
        f, s = row.get(fast), row.get(slow)
        return finite(f) and finite(s) and float(f) >= band * float(s)

    def _ordered(self, row: pd.Series, prefix: str = "") -> bool:
        a, b, c = (row.get(prefix + m) for m in THREE_LINE_MAS)
        return all(finite(x) for x in (a, b, c)) and a > b > c

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        if self.params["variant"] == THREE_LINE:
            return not self._ordered(row)
        _, _, _, xf, xs, band = self.preset
        f, s = row.get(xf), row.get(xs)
        return finite(f) and finite(s) and not self._above(row, xf, xs, band)

    def entry_ok(self, row: pd.Series) -> bool:
        if self.params["variant"] == THREE_LINE:
            return self._ordered(row) and not self._ordered(row, "prev_")
        fast, slow, band, *_ = self.preset
        prev = row.get("prior_close") if fast == "close" else row.get(f"prev_{fast}")
        prev_slow = row.get(f"prev_{slow}")
        crossed = finite(prev) and finite(prev_slow) and float(prev) < band * float(prev_slow)
        return crossed and self._above(row, fast, slow, band)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        rows = c1.rows(self, panel, as_of)
        mult = float(self.params["stop_atr_mult"])
        out: list[Signal] = []
        for _, row in rows.iterrows():
            close, atr = float(row["close"]), row["atr_14"]
            if not finite(atr) or not self.trend_ok(row) or not self.entry_ok(row):
                continue
            sig = self.build_signal(row, as_of, entry=close, stop=close - mult * float(atr), target=None, score=0.0,
                                    features={"max_hold_days": self.params["max_hold_days"]},
                                    notes=f"MA crossover ({self.params['variant']})")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
