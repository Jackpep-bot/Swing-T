"""Insider cluster-buy follow-through (long).

docs/research-monitor.md: insider cluster = >= 3 distinct insiders with open-market buys (Form 4 codes P/A)
within 30 days, rejecting clusters with >= 80% identical date+price. The cluster scoring itself lives with
the EDGAR ingest; this strategy only consumes an OPTIONAL panel column `insider_cluster_score` and returns
no signals when the column is absent (settings.yaml ships it disabled until Form 4 ingest exists).
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

NAME = "insider_cluster"
DEFAULT_SCORE_COLUMN = "insider_cluster_score"


@register("strategy", NAME)
class InsiderCluster(PanelStrategy):
    name = NAME
    description = "Optional insider_cluster_score column >= min_score; ATR stop, R-multiple target."
    default_params: dict[str, Any] = {
        "score_column": DEFAULT_SCORE_COLUMN,
        "min_score": 1.0,  # scale is defined by the producer of the column; >= 1 means "a cluster exists"
        "stop_atr_mult": 2.0,
        "target_r": 2.0,
        P_MIN_TREND: TREND_DOWN,  # insiders often buy weakness; no trend filter by default
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 1.0,
    }
    features_required = ["atr_14", "trend_state"]

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        col = str(self.params["score_column"])
        if col not in panel.columns:
            log.debug("strategy.skip", strategy=self.name, reason=f"panel has no {col!r} column")
            return []
        if not self.market_ok(regime):
            return []
        rows = self.rows_as_of(panel, as_of)
        min_score = float(self.params["min_score"])
        stop_mult = float(self.params["stop_atr_mult"])
        target_r = float(self.params["target_r"])
        out: list[Signal] = []
        for _, row in rows.iterrows():
            score, atr = row[col], row["atr_14"]
            if not (finite(score) and finite(atr)) or float(score) < min_score or float(atr) <= 0:
                continue
            if not self.trend_ok(row):
                continue
            close = float(row["close"])
            stop = close - stop_mult * float(atr)
            target = close + target_r * (close - stop)
            sig = self.build_signal(
                row,
                as_of,
                entry=close,
                stop=stop,
                target=target,
                score=float(score),
                features={col: score, "atr_14": atr, "trend_state": row["trend_state"]},
                notes=f"insider cluster score {float(score):.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
