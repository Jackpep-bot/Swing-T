"""Earnings announcement premium (long), docs/strategies/earnings_announcement_premium.md (catalog E23,
Frazzini-Lamont 2007; Barber et al. 2013).

Rule: own stocks in the window before an EXPECTED (predicted, never actual) earnings report. APPROXIMATION: the
card's year-earlier rule (same fiscal quarter's report + 364 days) needs dated announcement history in the panel;
the only joinable column today is `days_since_earnings` (sessions since the latest 8-K Item 2.02 session,
`data.fundamentals.earnings_calendar_features`), so the predicted date is the catalog's quarter-earlier proxy:
latest report + `quarter_sessions`. The signal fires on the session `pre_sessions` before that date (card window
[-10, +5] sessions) and holds `max_hold_days` (15) through the predicted report. The past-announcement-volume
tercile filter is not built (needs per-report rvol history). Stop = entry - 2 x atr_14 (engine choice; the paper has
none); no target. `days_since_earnings` is OPTIONAL: without it the strategy returns no signals (like
insider_cluster). Holding through reports conflicts with `execution.earnings_exit_days` (card "What the router
should know"): shadow only.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import structlog

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, PanelStrategy, finite

log = structlog.get_logger(__name__)

NAME = "earnings_announcement_premium"
DAYS_COL = "days_since_earnings"  # data.fundamentals.FEATURE_COLUMNS (optional panel join)


@register("strategy", NAME)
class EarningsAnnouncementPremium(PanelStrategy):
    name = NAME
    description = "Expected-announcer window: days_since_earnings == 63 - 10; hold 15 sessions, 2 ATR stop."
    default_params: dict[str, Any] = {
        "quarter_sessions": 63,  # catalog E23: quarter-earlier proxy for the expected report (~63 sessions)
        "pre_sessions": 10,  # card: window starts 10 sessions before the predicted date
        "max_hold_days": 15,  # card window [-10, +5] sessions around the predicted date
        "stop_atr_mult": 2.0,  # engine safety stop (paper: none)
        P_MIN_TREND: TREND_DOWN,  # no trend filter in the paper
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # time exit, no target
    }
    features_required = ["atr_14", "trend_state", "ret_63d"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if DAYS_COL not in panel.columns:
            log.debug("strategy.skip", strategy=self.name, reason=f"panel has no {DAYS_COL!r} column")
            return []
        if not self.market_ok(regime):
            return []
        p = self.params
        due = int(p["quarter_sessions"]) - int(p["pre_sessions"])
        rows = self.rows_as_of(panel, as_of, required=[*self.features_required, DAYS_COL])
        out: list[Signal] = []
        for _, row in rows.iterrows():
            days, atr = row[DAYS_COL], row["atr_14"]
            if not (finite(days) and finite(atr)) or int(days) != due or not self.trend_ok(row):
                continue
            close = float(row["close"])
            sig = self.build_signal(
                row,
                as_of,
                entry=close,
                stop=close - float(p["stop_atr_mult"]) * float(atr),
                target=None,
                score=float(row["ret_63d"]) if finite(row["ret_63d"]) else 0.0,
                features={DAYS_COL: days, "atr_14": atr, "max_hold_days": p["max_hold_days"]},
                notes=f"expected report in ~{int(p['pre_sessions'])} sessions ({int(days)} since the last 8-K 2.02; "
                "quarter-earlier proxy)",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
