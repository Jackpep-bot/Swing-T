"""Power gap / buyable gap-up, consolidation entry (long): docs/methods.md section 7b #3 (`earnings_gap`).

Rules (docs/methods/13-power-earnings-gap.md): a gap of 10%+ (PEG / EP) or at least 0.75x the prior bar's ATR(40)
(Morales/Kacher BGU) on volume >= 2x the prior 50-day average with a strong close (close in the top 30% of the
range); then a 2-30 bar consolidation that holds above the gap-day low; buy the first close above the
consolidation high on rvol >= 1.5. Stop = gap-day low, capped at 1.5 ADR below the entry; the working exit is
the first close below the 20-day SMA (`should_exit`), plus a time stop. Partial sales after 3-5 days need a
scale-out hook the engine does not have.

LABEL: historical point-in-time earnings dates are not ingested (methods.md 8 #3), so every signal is a
*volume gap*, not a verified earnings gap; `features["earnings_verified"]` is 0 and the notes say so.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import as_of_view, gap_consolidation

from ._base import (
    P_MIN_MARKET_TREND,
    P_MIN_RR,
    P_MIN_TREND,
    SYMBOL,
    TREND_FLAT,
    TREND_UP,
    PanelStrategy,
    finite,
)

NAME = "power_gap"
GAP_ATR_COL = "gap_atr40"
VOL_RATIO_COL = "vol_ratio_50d_prev"
ADR_COL = "adr_pct_20"
ARRAYS = ("high", "low", "close", "gap_pct", GAP_ATR_COL, VOL_RATIO_COL, "close_pos")
EARNINGS_VERIFIED = 0.0  # no point-in-time earnings calendar in the panel (methods.md 8 #3)


@register("strategy", NAME)
class PowerGap(PanelStrategy):
    name = NAME
    description = "Volume gap >= 10% or 0.75x ATR40 on 2x vol; buy the break of a 2-30 bar hold above the gap low."
    default_params: dict[str, Any] = {
        "min_gap_pct": 0.10,  # doc 13: PEG / EP gap of 10% or more
        "min_gap_atr40": 0.75,  # doc 13: BGU gap >= 0.75 x ATR(40) of the prior bar
        "min_volume_ratio": 2.0,  # methods.md 7b #3: volume >= 2x the prior 50-day average
        "min_close_pos": 0.7,  # methods.md 7b #3: strong close, close_pos >= 0.7
        "consol_min_bars": 2,  # doc 13: consolidation 2-30 bars after the gap
        "consol_max_bars": 30,
        "breakout_rvol_min": 1.5,  # doc 13 automatability: trigger close > consolidation high on rvol >= 1.5
        "max_stop_adr": 1.5,  # methods.md 7b #3: stop gap-day low capped at 1.5 ADR
        "trail_ma": "sma_20",  # doc 13 / methods.md 7b #3: trail the 20-day
        "target_r": 10.0,  # reference target only (doc 05: winners run "10-20x+ your initial risk"); trail exits
        "max_hold_days": 60,  # doc 13 proposed max_hold_days=60
        P_MIN_TREND: TREND_FLAT,  # doc 13 BGU: "not while a stock is in a downtrend"
        P_MIN_MARKET_TREND: TREND_UP,  # doc 13 proposed min_market_trend_state=1
        P_MIN_RR: 2.0,
    }
    features_required = ["rvol_day", "gap_pct", "close_pos", "trend_state", GAP_ATR_COL, VOL_RATIO_COL, ADR_COL]

    def required_features(self) -> list[str]:
        return [*self.features_required, str(self.params["trail_ma"])]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        ma = row.get(str(self.params["trail_ma"]))
        return finite(ma) and float(row["close"]) < float(ma)

    def gap_days(self, w: dict[str, np.ndarray]) -> np.ndarray:
        """Boolean array: bars that qualify as a power gap (size, volume and close-strength rules)."""
        p = self.params
        with np.errstate(invalid="ignore"):
            big = (w["gap_pct"] >= float(p["min_gap_pct"])) | (w[GAP_ATR_COL] >= float(p["min_gap_atr40"]))
            return big & (w[VOL_RATIO_COL] >= float(p["min_volume_ratio"])) & (
                w["close_pos"] >= float(p["min_close_pos"])
            )

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        view = as_of_view(panel, as_of, ["open", *ARRAYS, *self.required_features()])
        cur = view.current
        keep = (cur["rvol_day"] >= float(self.params["breakout_rvol_min"])).fillna(False)
        c_min, c_max = int(self.params["consol_min_bars"]), int(self.params["consol_max_bars"])
        out: list[Signal] = []
        for _, row in cur.loc[keep].iterrows():
            if not self.trend_ok(row):
                continue
            w = view.window(str(row[SYMBOL]), ARRAYS)
            t = len(w["close"]) - 1
            gc = gap_consolidation(self.gap_days(w), w["high"], w["low"], t - 1, c_min, c_max)
            if gc is None:
                continue
            close = float(w["close"][t])
            if close <= gc.pivot:
                continue
            closes, highs = w["close"][gc.gap_idx + 1 : t], w["high"][gc.gap_idx + 1 : t]
            r0 = max(1, c_min)
            if (closes[r0:] > np.maximum.accumulate(highs)[r0 - 1 : -1]).any():
                continue  # an earlier close already broke this consolidation: one entry per gap
            adr = row[ADR_COL]
            stop = gc.gap_low
            if finite(adr):
                stop = max(stop, close * (1.0 - float(self.params["max_stop_adr"]) * float(adr)))
            g = gc.gap_idx
            vol_ratio = float(w[VOL_RATIO_COL][g])
            sig = self.build_signal(
                row,
                as_of,
                entry=close,
                stop=stop,
                target=close + float(self.params["target_r"]) * (close - stop),
                score=vol_ratio,
                features={
                    "earnings_verified": EARNINGS_VERIFIED,
                    "gap_pct": w["gap_pct"][g],
                    "gap_atr40": w[GAP_ATR_COL][g],
                    "gap_volume_ratio": vol_ratio,
                    "gap_low": gc.gap_low,
                    "gap_age": t - g,
                    "consol_len": gc.length,
                    "pivot": gc.pivot,
                    "rvol_day": row["rvol_day"],
                    ADR_COL: adr,
                    "max_hold_days": self.params["max_hold_days"],
                },
                notes=f"volume gap (earnings date not verified) {w['gap_pct'][g] * 100:+.1f}% on {vol_ratio:.1f}x vol "
                f"{t - g} bars ago; close {close:.2f} > {gc.length}-bar consolidation high {gc.pivot:.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(cur), len(out))
        return out
