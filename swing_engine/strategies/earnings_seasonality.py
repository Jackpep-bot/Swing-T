"""Earnings seasonality (Chang, Hartzmark, Solomon & Soltes, RFS 2017): docs/strategies/earnings_seasonality.md,
pre-registered in docs/preregistration/2026-10-09-three-picks.md.

Reads the OPTIONAL panel columns `earn_season` (EarnRank of the upcoming fiscal quarter from XBRL diluted EPS, low =
historically strong), `sessions_to_expected_earnings` (the 8-K 2.02 reaction session 364 days earlier, rolled to a
session) and `days_since_earnings` from `data.fundamentals.join_edgar`; no signals when they are absent. Each
session, rank -earn_season among eligible names (close >= $5, 63-day median dollar volume >= $20M) expected to
report within 1-21 sessions; buy the top quintile when the expected date is 6 sessions away (fill next open = 5
sessions before it) and the last report is >= 25 sessions old. Exit at the next open once days_since_earnings >= 2
for an announcement on or after the entry session (the card's close two sessions after; the engine fills next
open), else at `max_hold_days` 25. Stop 3 x ATR(14) (engine choice, as pead_sue). `engine_trail = False`.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import structlog

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, finite

log = structlog.get_logger(__name__)

NAME = "earnings_seasonality"
SEASON, TO_EXP, SINCE = "earn_season", "sessions_to_expected_earnings", "days_since_earnings"  # data.fundamentals
MED_DV = "med_dv_63"  # features.extra


@register("strategy", NAME)
class EarningsSeasonality(PanelStrategy):
    name = NAME
    description = "Top seasonality quintile 5 sessions before the expected report; exit 2 sessions after it."
    default_params: dict[str, Any] = {
        "min_price": 5.0,  # card engine version: price >= $5
        "min_median_dollar_vol": 20_000_000.0,  # card engine version: 63-day median dollar volume >= $20M
        "entry_sessions_before": 6,  # card: enter next open 5 sessions before the expected date
        "population_max_sessions": 21,  # sort among names expected to report within the coming month
        "top_fraction": 0.2,  # card: long the top quintile only
        "min_sessions_since_report": 25,  # the coming quarter is not already out (engine choice)
        "exit_sessions_after": 2,  # card: exit 2 sessions after the actual announcement
        "stop_atr_mult": 3.0,  # engine choice (no stop in the paper), as pead_sue
        "max_hold_days": 25,  # card: 25 sessions after entry if no announcement
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # no target
    }
    features_required = ["atr_14"]
    extra_features = [MED_DV]
    prior_columns: list[str] = []
    engine_trail = False  # hold to the event, as the paper does

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        """The announcement arrived on or after the entry session (days_since < bars_held) and is >= N sessions old."""
        since = row.get(SINCE)
        return finite(since) and float(self.params["exit_sessions_after"]) <= float(since) < bars_held

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if any(c not in panel.columns for c in (SEASON, TO_EXP, SINCE)):
            log.debug("strategy.skip", strategy=self.name, reason="panel has no earn_season / earnings columns")
            return []
        if panel.empty or not self.market_ok(regime):
            return []
        p = self.params
        rows = c1.rows(self, panel, as_of)
        if rows.empty:
            return []
        to = rows[TO_EXP]
        pop = rows.loc[(rows["close"] >= float(p["min_price"])) & (rows[MED_DV] >= float(p["min_median_dollar_vol"]))
                       & rows[SEASON].notna() & (to >= 1) & (to <= float(p["population_max_sessions"]))]
        if pop.empty:
            return []
        strength = (-pop[SEASON]).rank(pct=True)
        fire = (strength > 1.0 - float(p["top_fraction"])) & (pop[TO_EXP] == float(p["entry_sessions_before"])) & (
            pop[SINCE] >= float(p["min_sessions_since_report"]))
        out: list[Signal] = []
        for idx, row in pop.loc[fire].iterrows():
            close, atr = float(row["close"]), row["atr_14"]
            if not finite(atr):
                continue
            sig = self.build_signal(
                row, as_of, entry=close, stop=close - float(p["stop_atr_mult"]) * float(atr), target=None,
                score=float(strength[idx]), features={SEASON: row[SEASON], "season_pct": strength[idx], TO_EXP: row[TO_EXP]},
                notes=f"EarnRank {float(row[SEASON]):.1f} (top {float(p['top_fraction']):.0%}), report in {int(row[TO_EXP])} sessions",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
