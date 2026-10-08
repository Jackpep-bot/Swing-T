"""Post-earnings-announcement drift on time-series SUE (long top decile): docs/strategies/pead_sue.md (catalog E21).

Reads the OPTIONAL panel columns `sue` and `days_since_earnings` from `data.fundamentals.edgar_panel_features`
(XBRL diluted EPS, usable the session after the 10-Q/10-K `filed` date, so conservative vs the 8-K release) and returns
no signals when they are absent. Monthly, on the symbol's first session of a calendar month: rank
`sue` across the symbols that have one on that session and buy the top decile with days_since_earnings <= 30 and
close >= $5. The size split the card asks for is logged per signal (`dollar_vol_20d`). No stop in the source; engine
stop entry - 3 x atr_14 (card); exit at `max_hold_days` 60 (Bernard-Thomas drift window); no target.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import structlog

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, TS, PanelStrategy, _local_day, finite

log = structlog.get_logger(__name__)

NAME = "pead_sue"
SUE, DAYS = "sue", "days_since_earnings"  # data/fundamentals.py FEATURE_COLUMNS


@register("strategy", NAME)
class PeadSue(PanelStrategy):
    name = NAME
    description = "Monthly top-decile time-series SUE within 30 days of the report; 3 ATR stop, 60-day hold."
    default_params: dict[str, Any] = {
        "top_fraction": 0.1,  # card: long the top decile
        "max_days_since_report": 30,  # card: days_since_report <= 30 (column counts sessions)
        "min_price": 5.0,  # card: price >= $5
        "stop_atr_mult": 3.0,  # card: engine choice, the source has none
        "max_hold_days": 60,  # card: Bernard-Thomas 60-trading-day drift window
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card
    }
    features_required = ["atr_14", "dollar_vol_20d"]
    prior_columns = ["ts"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if SUE not in panel.columns or DAYS not in panel.columns:
            log.debug("strategy.skip", strategy=self.name, reason="panel has no sue / days_since_earnings columns")
            return []
        if not self.market_ok(regime):
            return []
        p = self.params
        rows = self.rows_as_of(panel, as_of, required=[*self.required_features(), SUE, DAYS])
        new_month = _local_day(rows[TS]).dt.to_period("M") != _local_day(rows[f"prior_{TS}"]).dt.to_period("M")
        rows = rows.loc[new_month & rows["prior_ts"].notna() & rows[SUE].notna()]  # card: monthly, first session
        if rows.empty:
            return []
        rank = rows[SUE].rank(pct=True)
        keep = (rank > 1.0 - float(p["top_fraction"])) & (rows[DAYS] <= float(p["max_days_since_report"])) & (
            rows["close"] >= float(p["min_price"]))
        out: list[Signal] = []
        for idx, row in rows.loc[keep].iterrows():
            close, atr = float(row["close"]), row["atr_14"]
            if not finite(atr):
                continue
            sig = self.build_signal(
                row, as_of, entry=close, stop=close - float(p["stop_atr_mult"]) * float(atr), target=None,
                score=float(row[SUE]),
                features={SUE: row[SUE], "sue_rank": rank[idx], DAYS: row[DAYS], "dollar_vol_20d": row["dollar_vol_20d"]},
                notes=f"SUE {float(row[SUE]):.2f} (top {float(p['top_fraction']):.0%}), {int(row[DAYS])}d since report",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
