"""NR7 / NR4 / ID-NR4 range-contraction breakout (Crabel, long): docs/strategies/nr7_nr4_range_contraction.md.

Setup at the close of bar t: `pattern` (nr7 default; nr4 or id_nr4) from features.extra, trend_state >= 1,
avg_vol_20d >= 100k, close >= $5. Entry: buy stop high_t + tick for the next session (`EntryType.STOP`; untriggered
orders expire). Stop: low_t - tick. Variant A (Crabel, default): no target, 3-bar time exit; the "first profitable
close" exit is not modelled because `should_exit` does not see the entry price. Variant B (Bulkowski): set
`target_pct: 0.07`, `max_hold_days: 40`. The sell-stop short half of the OCO bracket is not modelled (long-only).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import EntryType, Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, TREND_UP, PanelStrategy, finite

NAME = "nr7_nr4_range_contraction"
PATTERNS = ("nr7", "nr4", "id_nr4")


@register("strategy", NAME)
class NR7RangeContraction(PanelStrategy):
    name = NAME
    description = "NR7 (or NR4 / ID-NR4) in an uptrend; buy stop over the NR high, stop under its low; 3-bar exit."
    default_params: dict[str, Any] = {
        "pattern": "nr7",  # card: NR7 default; nr4 / id_nr4 variants
        "min_avg_volume": 100_000,  # card: avg_vol_20d >= 100k
        "min_price": 5.0,  # card: close >= 5
        "tick": 0.01,  # card: buy stop high + 0.01, stop low - 0.01
        "target_pct": None,  # card variant B (Bulkowski): 0.07
        "max_hold_days": 3,  # card variant A (Crabel); variant B uses 40
        P_MIN_TREND: TREND_UP,  # card: trend_state >= 1
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: variant A needs min_reward_risk 0
    }
    features_required = ["avg_vol_20d", "trend_state"]
    extra_features = list(PATTERNS)

    def required_features(self) -> list[str]:
        return [*self.features_required, str(self.params["pattern"])]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        flag = str(p["pattern"])
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        keep = (rows[flag] == 1.0) & (rows["avg_vol_20d"] >= float(p["min_avg_volume"])) & (
            rows["close"] >= float(p["min_price"]))
        tick, tgt = float(p["tick"]), p["target_pct"]
        out: list[Signal] = []
        for _, row in rows.loc[keep.fillna(False)].iterrows():
            if not self.trend_ok(row):
                continue
            high, low = float(row["high"]), float(row["low"])
            entry = high + tick
            sig = self.build_signal(
                row, as_of, entry=entry, stop=low - tick,
                target=entry * (1.0 + float(tgt)) if tgt is not None and finite(tgt) else None,
                score=-(high - low) / float(row["close"]),  # tightest range first
                features={"range_pct": (high - low) / float(row["close"])},
                notes=f"{flag}: buy stop {entry:.2f}, stop {low - tick:.2f}",
            )
            if sig:
                out.append(sig.model_copy(update={"entry_type": EntryType.STOP}))
        self.log_scan(as_of, len(rows), len(out))
        return out
