"""Stochastic Pop (long), Bernstein / Steckler / Hill: docs/strategies/stochastic_pop_and_drop.md, catalog P51.

Bias: 70-period stochastic %K > 50. Setup: ADX(14) < 20 (consolidation). Pop: fast %K(14) crosses up through 80,
coming from below 50 (the card's "surge", engine choice), on volume above the PRIOR 250-day average volume. Entry
at the next open. Stop: lowest low of the prior 20 bars x 0.995, never more than 3 x atr_14 below the entry. Exit:
%K(14) back below 50, or 10 sessions. No target. The "Drop" short side and the optional Parabolic SAR trail are not
built (%K < 50 is the card's primary exit).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_FLAT, PanelStrategy, RollingSpec, finite

NAME = "stochastic_pop_and_drop"
K_FAST, K_BIAS, VOL_AVG = "stoch_k_14", "stoch_k_70", "prev_sma_250_of_volume"


@register("strategy", NAME)
class StochasticPopAndDrop(PanelStrategy):
    name = NAME
    description = "%K70 > 50, ADX14 < 20; %K14 pops through 80 from < 50 on volume over its 250-day average."
    default_params: dict[str, Any] = {
        "bias_min": 50.0,  # card: 70-period stochastic > 50
        "adx_max": 20.0,  # card: ADX(14) < 20 (Steckler prefers 15)
        "pop_level": 80.0,  # card: 14-day stochastic surges above 80
        "prior_k_max": 50.0,  # card `min_prior_k` e.g. 50: the prior %K was below 50 (a surge, not drift)
        "support_lookback": 20,  # card: stop = min(low over prior 20 bars) x 0.995
        "stop_mult": 0.995,
        "max_stop_atr": 3.0,  # card: at most 3 x atr_14 below the entry
        "exit_level": 50.0,  # card: exit when %K(14) < 50
        "max_hold_days": 10,  # card
        P_MIN_MARKET_TREND: TREND_FLAT,  # card: uptrend regimes only, in shadow
        P_MIN_RR: 0.0,  # card: rule exit, no target
    }
    features_required = ["atr_14"]
    extra_features = [K_FAST, f"prev_{K_FAST}", K_BIAS, "adx_14", VOL_AVG]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        k = row.get(K_FAST)
        return finite(k) and float(k) < float(self.params["exit_level"])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        spec = RollingSpec("low", "min", int(p["support_lookback"]), prior=True)
        rows = self.rows_as_of(panel, as_of, rolling=[spec], required=self.required_features())
        keep = (
            (rows[K_BIAS] > float(p["bias_min"]))
            & (rows["adx_14"] < float(p["adx_max"]))
            & (rows[K_FAST] >= float(p["pop_level"]))
            & (rows[f"prev_{K_FAST}"] < float(p["prior_k_max"]))
            & (rows["volume"] > rows[VOL_AVG])
        )
        out: list[Signal] = []
        for _, row in rows.loc[keep.fillna(False)].iterrows():
            close, atr, support = float(row["close"]), row["atr_14"], row[spec.out]
            if not (finite(atr) and finite(support)):
                continue
            stop = max(float(support) * float(p["stop_mult"]), close - float(p["max_stop_atr"]) * float(atr))
            sig = self.build_signal(
                row, as_of, entry=close, stop=stop, target=None, score=float(row[K_FAST]) - float(row[f"prev_{K_FAST}"]),
                features={K_FAST: row[K_FAST], K_BIAS: row[K_BIAS], "adx_14": row["adx_14"],
                          "vol_ratio_250": float(row["volume"]) / float(row[VOL_AVG]), "max_hold_days": p["max_hold_days"]},
                notes=f"pop: %K14 {float(row[f'prev_{K_FAST}']):.0f} -> {float(row[K_FAST]):.0f}, ADX {float(row['adx_14']):.0f}, "
                f"%K70 {float(row[K_BIAS]):.0f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
