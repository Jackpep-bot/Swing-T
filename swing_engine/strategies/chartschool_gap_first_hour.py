"""ChartSchool gap trading, daily approximation (label approx_daily): docs/strategies/chartschool_gap_first_hour.md.

The real rule needs first-hour (to ~10:30 ET) intraday bars: buy stop two ticks over the first-hour high. The engine
has daily bars only, so (card "Daily approximation") the first-hour break becomes a strong gap-day close: close > open
and close_pos >= 0.7, entry next open. This is NOT the ChartSchool rule. Long gap types traded (card's fixed set):
full gap up (open > prior high), partial gap up (prior close < open <= prior high), both at least `min_gap_pct`;
and the full-gap-down Oops reclaim (open < prior low, close > prior low). Filter: avg_vol_20d >= 500k. Initial stop =
gap-day low; exit = 8% trailing stop from the highest close (`trail_stop`; the 5-6% partial-gap trail is not
distinguished because the hook sees only the held row); 5-day time exit; no target. Short rules are not used.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, finite

NAME = "chartschool_gap_first_hour"
FULL_UP, PARTIAL_UP, OOPS = "full_gap_up", "partial_gap_up", "full_gap_down_reclaim"


@register("strategy", NAME)
class ChartSchoolGapDaily(PanelStrategy):
    name = NAME
    description = "Daily proxy of the ChartSchool first-hour gap rules: strong gap-up close or gap-down reclaim; 8% trail."
    default_params: dict[str, Any] = {
        "min_gap_pct": 0.02,  # card: source sets none; 0.02 engine choice
        "min_close_pos": 0.7,  # card daily approximation: close > open and close_pos >= 0.7
        "min_avg_volume": 500_000,  # card: average volume >= 500k
        "trail_pct": 0.08,  # card: 8% trailing stop for longs (5-6% for partial gaps not distinguished)
        "trade_oops": True,  # card: full-gap-down long = Oops reclaim of the prior low
        "max_hold_days": 5,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["avg_vol_20d", "close_pos"]
    engine_trail = False  # the percent trail replaces the breakeven / N-day-low overlay

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def trail_stop(self, row: pd.Series) -> float | None:
        # the engine ratchets (never loosens), so this tracks the highest close since entry x (1 - trail)
        return float(row["close"]) * (1.0 - float(self.params["trail_pct"]))

    def gap_type(self, row: pd.Series) -> str | None:
        o, c = float(row["open"]), float(row["close"])
        ph, pl, pc = float(row["prior_high"]), float(row["prior_low"]), float(row["prior_close"])
        strong = c > o and finite(row["close_pos"]) and float(row["close_pos"]) >= float(self.params["min_close_pos"])
        if o >= pc * (1.0 + float(self.params["min_gap_pct"])) and strong:
            return FULL_UP if o > ph else PARTIAL_UP
        if bool(self.params["trade_oops"]) and o < pl < c:
            return OOPS
        return None

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        rows = self.rows_as_of(panel, as_of)
        liquid = (rows["avg_vol_20d"] >= float(self.params["min_avg_volume"])).fillna(False)
        out: list[Signal] = []
        for _, row in rows.loc[liquid].iterrows():
            if not all(finite(row[c]) for c in ("prior_high", "prior_low", "prior_close")):
                continue
            kind = self.gap_type(row)
            if kind is None:
                continue
            close, low = float(row["close"]), float(row["low"])
            sig = self.build_signal(
                row, as_of, entry=close, stop=low, target=None, score=float(row["open"]) / float(row["prior_close"]) - 1,
                features={"gap_pct": float(row["open"]) / float(row["prior_close"]) - 1, "close_pos": row["close_pos"]},
                notes=f"approx_daily {kind}: gap-day low stop {low:.2f}, {self.params['trail_pct']:.0%} trail",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
