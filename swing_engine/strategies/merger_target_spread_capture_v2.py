"""Merger target spread capture, RE-TEST with a cleaned target flag (Mitchell & Pulvino 2001; Alpha Architect 2018):
docs/proposals/swing-methods-2026-10/batch8/merger_target_spread_capture_v2.md. Second trial of the family after
batch 7's `merger_target_spread_capture`.

Deal candidates come from data.b8.join_b8 (`deal_v2_days`: sessions since the candidate filing's session s, on s and
the 20 sessions after it; `deal_v2_anchor`: sessions from the anchor a to s): a tender offer naming the company as
subject with another filer, or the company's own DEFM14A after its own 8-K Item 1.01 in the 120 sessions before;
one candidate per symbol per 365 days. On a candidate's session, and each of the next 20 until the first pass:
- premium: close >= 1.10 x the close 25 sessions before the anchor;
- pinned: the sample standard deviation of the last 10 daily returns <= 1.0%.
The first session that passes is the signal; `mcap_pit` >= $300M and `med_dv_63` >= $5M that day. Buy the next
open. Exits, first to hit: the deal closes and the symbol stops trading (the replay's delisting exit at the last
close); the break stop at 85% of the signal close (filled during the session, or at the open on a gap; the card reads
the close); 180 sessions. No target, no trail, no regime gate. Fifteen positions at equal risk on the 15% stop come
from the book.

Readings fixed here: session counts inside the window are the symbol's own bars (a halted name counts fewer).
Replay-only: silent without the two join columns or `mcap_pit`.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _b5 as b5
from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy

NAME = "merger_target_spread_capture_v2"
DAYS, ANCHOR = "deal_v2_days", "deal_v2_anchor"  # data.b8.join_b8
NEEDS = (DAYS, ANCHOR, b5.MCAP)


@register("strategy", NAME)
class MergerTargetSpreadCaptureV2(PanelStrategy):
    name = NAME
    description = "Buy a takeover target trading pinned at a premium after its deal filing; hold to the deal close."
    default_params: dict[str, Any] = {
        "min_mcap": 300e6,  # card: mcap_pit >= $300M
        "min_dollar_volume": 5e6,  # card: med_dv_63 >= $5M
        "min_premium": 1.10,  # card: close >= 1.10 x close(a - 25)
        "premium_lookback": 25,  # card: 25 sessions before the anchor
        "pin_sessions": 10,  # card: stdev of daily returns over sessions t-9..t
        "max_pin_std": 0.01,  # card: <= 1.0%
        "break_stop_pct": 15.0,  # card: close <= 0.85 x entry is a deal break
        "max_hold_days": 180,  # card: 180-session limit
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: no regime gate
        P_MIN_RR: 0.0,  # card: no target
    }
    extra_features = [b5.MED_DV]
    prior_columns: list[str] = []
    engine_trail = False  # the payout is the deal close

    def _passes(self, c: np.ndarray, i: int, ref: int) -> bool:
        p, n = self.params, int(self.params["pin_sessions"])
        if i - n < 0 or ref < 0:
            return False
        r = c[i - n + 1:i + 1] / c[i - n:i] - 1.0
        return bool(np.isfinite(r).all() and np.isfinite(c[ref]) and c[i] >= float(p["min_premium"]) * c[ref]
                    and np.std(r, ddof=1) <= float(p["max_pin_std"]))

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or any(c not in panel.columns for c in NEEDS) or not self.market_ok(regime):
            return []
        p = self.params
        rows = c1.rows(self, panel, as_of)
        if rows.empty:
            return []
        ok = (rows[DAYS].notna() & (rows[b5.MCAP] >= float(p["min_mcap"]))
              & (rows[b5.MED_DV] >= float(p["min_dollar_volume"])))
        out: list[Signal] = []
        if ok.any():
            view = c1.view(self, panel, as_of, [])
        for _, row in rows.loc[ok.fillna(False)].iterrows():
            c = view.window(str(row[SYMBOL]), ["close"])["close"]
            t, d = len(c) - 1, int(row[DAYS])
            s = t - d
            ref = s - int(row[ANCHOR]) - int(p["premium_lookback"])
            if s < 0 or not self._passes(c, t, ref) or any(self._passes(c, s + k, ref) for k in range(d)):
                continue
            close = float(row["close"])
            sig = self.build_signal(row, as_of, entry=close, stop=close * (1.0 - float(p["break_stop_pct"]) / 100.0),
                                    target=None, score=float(row[b5.MCAP]) / 1e9,
                                    features={"premium": close / float(c[ref]), DAYS: row[DAYS], ANCHOR: row[ANCHOR]},
                                    notes=f"deal filing {d} sessions ago, {close / float(c[ref]) - 1.0:+.0%} over the "
                                          "pre-announcement close, price pinned")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
