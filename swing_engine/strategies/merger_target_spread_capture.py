"""Merger target spread capture, long leg only (Mitchell & Pulvino 2001):
docs/proposals/swing-methods-2026-10/batch7/merger_target_spread_capture.md.

Signal on a symbol's reaction session to a DEFM14A, or to a third-party tender offer (SC TO-T) naming it, when no such
filing came in the 365 days before (`deal_event`, data.b7.join_b7). Eligible: `mcap_pit` >= $300M and `med_dv_63` >=
$5M on the signal day, and not up more than 30% over the last 20 sessions (`roc_20`: a bidding war or a non-deal
spike). Buy the next open. Exits, first to hit: the deal closes and the symbol stops trading (the replay's delisting
exit at the last close, with the store's delisting reason deciding any haircut); the break stop at 85% of the signal
close; 180 sessions (`max_hold_days`). No target, no trail, no regime gate. `event_avoid_filters` does not apply (a
merger 8-K is the event itself). Fifteen positions at equal risk on the 15% stop come from the book.

Readings fixed here: the card's break rule reads the close (close <= 0.85 x entry); the engine's stop fills during
the session at 85% of the signal close, or at the open when the price gaps through it. Known limit (data.b7): a
DEFM14A filed by an acquirer whose own holders vote on a stock deal also fires.
Replay-only: silent without `deal_event` or `mcap_pit`.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _b5 as b5
from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy

NAME = "merger_target_spread_capture"
EVENT, RUNUP = "deal_event", "roc_20"  # data.b7.join_b7; features.extra (percent)
NEEDS = (EVENT, b5.MCAP)


@register("strategy", NAME)
class MergerTargetSpreadCapture(PanelStrategy):
    name = NAME
    description = "Buy a takeover target after its definitive proxy or a tender offer is filed; hold to the deal close."
    default_params: dict[str, Any] = {
        "min_mcap": 300e6,  # card: mcap_pit >= $300M
        "min_dollar_volume": 5e6,  # card: med_dv_63 >= $5M
        "max_runup_pct": 30.0,  # card: skip if up more than 30% over the 20 sessions before the signal
        "break_stop_pct": 15.0,  # card: close <= 0.85 x entry is a deal break
        "max_hold_days": 180,  # card: 180-session limit
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: no regime gate
        P_MIN_RR: 0.0,  # card: no target
    }
    extra_features = [b5.MED_DV, RUNUP]
    prior_columns: list[str] = []
    engine_trail = False  # the payout is the deal close; a breakeven or N-day-low trail would sell the spread early

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or any(c not in panel.columns for c in NEEDS) or not self.market_ok(regime):
            return []
        p = self.params
        rows = c1.rows(self, panel, as_of)
        if rows.empty:
            return []
        ok = ((rows[EVENT] == 1.0) & (rows[b5.MCAP] >= float(p["min_mcap"]))
              & (rows[b5.MED_DV] >= float(p["min_dollar_volume"])) & (rows[RUNUP] <= float(p["max_runup_pct"])))
        out: list[Signal] = []
        for _, row in rows.loc[ok.fillna(False)].iterrows():
            close = float(row["close"])
            sig = self.build_signal(row, as_of, entry=close, stop=close * (1.0 - float(p["break_stop_pct"]) / 100.0),
                                    target=None, score=float(row[b5.MCAP]) / 1e9,
                                    features={RUNUP: row[RUNUP], b5.MCAP: row[b5.MCAP]},
                                    notes=f"deal filing; up {float(row[RUNUP]):+.1f}% over 20 sessions")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
