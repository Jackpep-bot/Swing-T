"""Faber sector rotation (long): docs/strategies/faber_sector_rotation.md (ChartSchool / Faber white paper).

On the last session of each month (`tom_day == -1`, features.extra calendar) rank the sector ETFs in `symbols` that
are in the panel by 3-month return (`ret_63d`) and buy the top 3; invest only while the market proxy's month-end close
is above the mean of its last 10 month-end closes (`market_symbol` rows in the panel; when absent the filter is
skipped and only `min_market_trend_state` applies). Approximations: the engine sizes by risk, not equal weight, so
each pick gets an ATR stop (entry - 3 x atr_14; the source has none); positions exit by the time stop (`max_hold_days`
~ one month) and a still-top-3 sector is bought again at the next rebalance instead of being rolled. Needs the ETFs
in the universe (`universe.include_etfs`); with a stock-only panel it emits nothing.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, TS, PanelStrategy, _local_day, finite

NAME = "faber_sector_rotation"
SECTOR_SPDRS = ("XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY")


@register("strategy", NAME)
class FaberSectorRotation(PanelStrategy):
    name = NAME
    description = "Month-end: top 3 sector ETFs by 3-month return while SPY > its 10-month SMA; ~1 month hold."
    default_params: dict[str, Any] = {
        "symbols": SECTOR_SPDRS,  # card: the 11 Select Sector SPDRs as the 10-sector proxy
        "top_n": 3,  # card: hold the top 3
        "rebalance_tom_day": -1,  # card: rank on month-end closes
        "market_symbol": "SPY",  # card: S&P 500 trend filter
        "filter_months": 10,  # card: 10-month SMA of month-end closes (12-month variant)
        "stop_atr_mult": 3.0,  # engine choice: the risk sizer needs a stop (the source has none)
        "max_hold_days": 21,  # card: one rebalance period (~21 sessions)
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card
    }
    features_required = ["ret_63d", "atr_14"]
    extra_features = ["tom_day"]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def filter_on(self, panel: pd.DataFrame, as_of: date) -> bool:
        p = self.params
        m = panel.loc[panel[SYMBOL] == p["market_symbol"], [TS, "close"]]
        if m.empty:
            return True
        day = _local_day(m[TS])
        m = m.loc[day <= pd.Timestamp(as_of)].assign(_m=day.dt.to_period("M")).sort_values(TS)
        month_end = m.groupby("_m")["close"].last().tail(int(p["filter_months"]))
        return len(month_end) == int(p["filter_months"]) and month_end.iloc[-1] > month_end.mean()

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        rows = rows.loc[rows[SYMBOL].isin(list(p["symbols"])) & (rows["tom_day"] == float(p["rebalance_tom_day"]))]
        rows = rows.loc[rows["ret_63d"].notna()]
        if rows.empty or not self.filter_on(panel, as_of):
            return []
        out: list[Signal] = []
        for rank, (_, row) in enumerate(rows.nlargest(int(p["top_n"]), "ret_63d").iterrows(), start=1):
            close, atr = float(row["close"]), row["atr_14"]
            if not finite(atr):
                continue
            sig = self.build_signal(
                row, as_of, entry=close, stop=close - float(p["stop_atr_mult"]) * float(atr), target=None,
                score=float(row["ret_63d"]), features={"ret_63d": row["ret_63d"], "sector_rank": rank},
                notes=f"sector rank {rank} by 3-month return {float(row['ret_63d']):.1%}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
