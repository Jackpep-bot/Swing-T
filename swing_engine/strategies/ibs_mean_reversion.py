"""Internal Bar Strength mean reversion (long), docs/strategies/ibs_mean_reversion.md (Pagonidis 2013, catalog E38).

IBS = close_pos = (close - low) / (high - low). Long when IBS < 0.2 at the close (optional close > sma_200 via
`trend_ma`); exit on a close with IBS > 0.8 or after 3 sessions; catastrophic stop entry - 2 x atr_14 (card). Universe:
index and sector ETFs (`symbols`; None scans everything).

Approximation: the rule buys AT the close (MOC). The engine has no close-fill entry, so this enters at the next open,
which measures the open-to-open variant the card says is about zero; treat replays as a lower bound.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "ibs_mean_reversion"
IBS = "close_pos"
ETFS = ("SPY", "QQQ", "IWM", "DIA", "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY")


@register("strategy", NAME)
class IbsMeanReversion(PanelStrategy):
    name = NAME
    description = "Index/sector ETF closes in the bottom 20% of its range; exit on IBS > 0.8 or 3 days."
    default_params: dict[str, Any] = {
        "ibs_entry": 0.2,  # card: IBS < 0.2
        "ibs_exit": 0.8,  # card: exit at a close with IBS > 0.8
        "trend_ma": None,  # card: optional close > sma_200 ("sma_200" to enable)
        "symbols": list(ETFS),  # card: index and sector ETFs (SPY, QQQ, IWM, DIA, sector SPDRs); None = all
        "stop_atr_mult": 2.0,  # card: catastrophic stop entry - 2*atr_14
        "max_hold_days": 3,  # card: max_hold_days 3
        P_MIN_TREND: TREND_DOWN,
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: min_reward_risk 0
    }
    features_required = ["atr_14", "trend_state", IBS]
    engine_trail = False  # 1-3 day hold with its own exit (card)

    def required_features(self) -> list[str]:
        ma = self.params.get("trend_ma")
        return [*self.features_required, str(ma)] if ma else list(self.features_required)

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        ibs = row.get(IBS)
        return bars_held >= int(self.params["max_hold_days"]) or (finite(ibs) and ibs > float(self.params["ibs_exit"]))

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        rows = c1.rows(self, panel, as_of)
        keep = rows[IBS] < float(p["ibs_entry"])
        if p["symbols"] is not None:
            keep &= rows[SYMBOL].isin(set(p["symbols"]))
        if p.get("trend_ma"):
            keep &= rows["close"] > rows[str(p["trend_ma"])]
        out: list[Signal] = []
        for _, row in rows.loc[keep.fillna(False)].iterrows():
            close, atr = float(row["close"]), row["atr_14"]
            if not finite(atr) or not self.trend_ok(row):
                continue
            sig = self.build_signal(row, as_of, entry=close, stop=close - float(p["stop_atr_mult"]) * float(atr),
                                    target=None, score=-float(row[IBS]),
                                    features={"ibs": row[IBS], "max_hold_days": p["max_hold_days"]},
                                    notes=f"IBS {row[IBS]:.2f} < {p['ibs_entry']}")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
