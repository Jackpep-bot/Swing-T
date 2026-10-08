"""Residual momentum (long top decile), docs/strategies/residual_momentum.md (catalog E04, Blitz-Huij-Martens 2011).

APPROXIMATION (the card's "daily proxy"): there is no Fama-French factor ingest, so `features.extra`
`resid_mom_<n>_<form>_<skip>` fits daily returns on the market proxy's (SPY) over the last 756 bars (36 months),
then scores sum(residuals) / std(residuals) over bars t-252 .. t-21 (months t-12 .. t-2). Needs SPY in the panel (or
the market frame) and 756+ bars of history; NaN otherwise. On the first session of each month the names in the top
decile of the same-session cross-sectional rank are bought (long side only; the short leg is dropped). Hold one month
(`max_hold_days` 21) with an engine ATR stop; no target.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, finite

NAME = "residual_momentum"


def score_column(params: dict[str, Any]) -> str:
    return f"resid_mom_{int(params['beta_bars'])}_{int(params['formation_bars'])}_{int(params['skip_bars'])}"


@register("strategy", NAME)
class ResidualMomentum(PanelStrategy):
    name = NAME
    description = "Month-start top decile of market-residual momentum (t-12..t-2); ATR stop, 21-session hold."
    default_params: dict[str, Any] = {
        "beta_bars": 756,  # card daily proxy: regress on SPY over 756 bars (36 months, all required)
        "formation_bars": 231,  # card: months t-12 .. t-2 = bars t-252 .. t-21
        "skip_bars": 21,  # card: skip month t-1
        "rank_min": 0.90,  # card: long the top decile
        "stop_atr_mult": 2.0,  # engine safety stop (paper: none)
        "max_hold_days": 21,  # card: hold 1 month
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # time exit, no target
    }
    features_required = ["atr_14"]
    extra_features = [score_column(default_params), f"{score_column(default_params)}_rank"]
    prior_columns = [*PanelStrategy.prior_columns, "ts"]

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        col = score_column(self.params)
        self.extra_features = [col, f"{col}_rank"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        col, rank_col = self.extra_features
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        out: list[Signal] = []
        for _, row in rows.iterrows():
            ts, prior = pd.Timestamp(row["ts"]), row["prior_ts"]
            if pd.isna(prior) or pd.Timestamp(prior).month == ts.month:
                continue  # rebalance on the first session of the month only
            rank, atr = row[rank_col], row["atr_14"]
            if not (finite(rank) and finite(atr)) or float(rank) < float(self.params["rank_min"]):
                continue
            close = float(row["close"])
            sig = self.build_signal(
                row,
                as_of,
                entry=close,
                stop=close - float(self.params["stop_atr_mult"]) * float(atr),
                target=None,
                score=float(rank),
                features={col: row[col], rank_col: rank, "atr_14": atr, "max_hold_days": self.params["max_hold_days"]},
                notes=f"residual momentum rank {float(rank):.2f} (score {float(row[col]):.2f}) at the month start",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
