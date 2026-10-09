"""Residual momentum (long top decile), docs/strategies/residual_momentum.md (catalog E04, Blitz-Huij-Martens 2011).

Score (`factor_model` param):
* "ff3" / "auto" with French factors in the panel (`swing ingest-french`; data.market_series joins `ff_*`):
  `features.extra` `ff3_resid_mom_<n>_<form>` regresses daily excess returns on Mkt-RF, SMB, HML over 756 bars and
  scores the residuals of the last 231 bars, both windows ending at the end of month t-2 (BHM's t-12 .. t-2, and
  the French publication lag: month t-1's factors are not out yet at the month start).
* "capm" / "auto" without factors (the card's "daily proxy"): `resid_mom_<n>_<form>_<skip>` fits daily returns on
  the market proxy's (SPY) over the last 756 bars, then scores sum(residuals) / std(residuals) over bars
  t-252 .. t-21. Needs SPY in the panel (or the market frame).
"auto" picks ff3 on a session where any scanned row has a finite ff3 score, else capm (never mixed in one
ranking). Both need 756+ bars of history; NaN otherwise. On the first session of each month the names in the top
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


def ff3_score_column(params: dict[str, Any]) -> str:
    return f"ff3_resid_mom_{int(params['beta_bars'])}_{int(params['formation_bars'])}"


def _extras(params: dict[str, Any]) -> list[str]:
    cols = [score_column(params), ff3_score_column(params)]
    return [*cols, *(f"{c}_rank" for c in cols)]


@register("strategy", NAME)
class ResidualMomentum(PanelStrategy):
    name = NAME
    description = "Month-start top decile of market-residual momentum (t-12..t-2); ATR stop, 21-session hold."
    default_params: dict[str, Any] = {
        "beta_bars": 756,  # card daily proxy: regress on SPY over 756 bars (36 months, all required)
        "formation_bars": 231,  # card: months t-12 .. t-2 = bars t-252 .. t-21
        "skip_bars": 21,  # card: skip month t-1
        "rank_min": 0.90,  # card: long the top decile
        "factor_model": "auto",  # auto | ff3 | capm (module docstring)
        "stop_atr_mult": 2.0,  # engine safety stop (paper: none)
        "max_hold_days": 21,  # card: hold 1 month
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # time exit, no target
    }
    features_required = ["atr_14"]
    extra_features = _extras(default_params)
    prior_columns = [*PanelStrategy.prior_columns, "ts"]

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        self.extra_features = _extras(self.params)

    def required_features(self) -> list[str]:
        ff3 = ff3_score_column(self.params)
        return [c for c in super().required_features() if c not in (ff3, f"{ff3}_rank")]  # optional: no factors

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        capm, ff3 = score_column(self.params), ff3_score_column(self.params)
        model = str(self.params["factor_model"])
        use_ff3 = model == "ff3" or (model == "auto" and ff3 in rows and bool(rows[ff3].notna().any()))
        col = ff3 if use_ff3 else capm
        rank_col = f"{col}_rank"
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
                notes=f"residual momentum ({'ff3' if use_ff3 else 'capm'}) rank {float(rank):.2f} "
                      f"(score {float(row[col]):.2f}) at the month start",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
