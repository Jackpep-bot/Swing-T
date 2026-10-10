"""Bollinger Method II, %b + MFI trend following (long), docs/strategies/bollinger_pctb_mfi_trend.md (catalog P46/C37).

Base variant: at the close, %b(20, 2) > 0.80 and MFI(10) > 80 (Bollinger's 10-day MFI) with trend_state >= 0; entry
next open. Stop = the Parabolic SAR for the next bar when SAR is long, else the 10-bar low (card: SAR initialised at
the signal bar's 10-bar low), never wider than entry - 2 x atr_14 (card sizing floor). The SAR is the trailing stop
(`trail_stop`); `should_exit` on the opposite signal (%b < 0.20 and MFI < 20) or 30 sessions. No target. The card's
ADX < 15 pre-filter and MACD pullback entry are separate trials, not coded here.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, TREND_FLAT, PanelStrategy, finite

NAME = "bollinger_pctb_mfi_trend"
PCTB, MFI, SAR, SAR_DIR, LOW10 = "bb_pctb_20", "mfi_10", "psar", "psar_dir", "low_10"
SAR_LONG = 1.0


@register("strategy", NAME)
class BollingerPctbMfiTrend(PanelStrategy):
    name = NAME
    description = "%b(20,2) > 0.8 and MFI(10) > 80 in a non-down trend; Parabolic SAR stop/trail, exit on the opposite."
    default_params: dict[str, Any] = {
        "pctb_buy": 0.80,  # card: %b > 0.80
        "mfi_buy": 80.0,  # card: MFI(10) > 80
        "pctb_sell": 0.20,  # card: sell when %b < 0.20 and MFI < 20
        "mfi_sell": 20.0,
        "max_stop_atr": 2.0,  # card: stop floored at entry - 2 x atr_14
        "max_hold_days": 30,  # card: max_hold_days 30
        P_MIN_TREND: TREND_FLAT,  # card: trend_state >= 0
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no fixed target
    }
    features_required = ["atr_14", "trend_state"]
    extra_features = [PCTB, MFI, SAR, SAR_DIR, LOW10]
    engine_trail = False  # the SAR is the trail (card)

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        b, m = row.get(PCTB), row.get(MFI)
        return finite(b) and finite(m) and b < float(self.params["pctb_sell"]) and m < float(self.params["mfi_sell"])

    def trail_stop(self, row: pd.Series) -> float | None:
        sar = row.get(SAR)
        return float(sar) if finite(sar) and row.get(SAR_DIR) == SAR_LONG else None

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        rows = c1.rows(self, panel, as_of)
        p = self.params
        keep = ((rows[PCTB] > float(p["pctb_buy"])) & (rows[MFI] > float(p["mfi_buy"]))).fillna(False)
        out: list[Signal] = []
        for _, row in rows.loc[keep].iterrows():
            close, atr = float(row["close"]), row["atr_14"]
            if not finite(atr) or not self.trend_ok(row):
                continue
            level = row[SAR] if row[SAR_DIR] == SAR_LONG else row[LOW10]
            stop = max(float(level), close - float(p["max_stop_atr"]) * float(atr)) if finite(level) else float("nan")
            sig = self.build_signal(row, as_of, entry=close, stop=stop, target=None, score=float(row[MFI]),
                                    features={PCTB: row[PCTB], MFI: row[MFI], SAR: row[SAR],
                                              "max_hold_days": p["max_hold_days"]},
                                    notes=f"%b {row[PCTB]:.2f} > {p['pctb_buy']}, MFI {row[MFI]:.0f} > {p['mfi_buy']}")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out

