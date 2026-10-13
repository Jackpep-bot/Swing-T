"""Earnings-announcement abnormal return (Abr) continuation, docs/strategies/earnings_announcement_return_abr.md
(Chan-Jegadeesh-Lakonishok 1996; HXZ replication, catalog E22).

Abr = sum over d = -2..+1 of (ret_1d - market ret_1d) around the latest announcement session (day 0), known from the
close of day +1. On the last session of each month (`month_end`, features/extra.py) the symbols with an Abr from a
report no older than `max_report_age` sessions are sorted; the top decile is bought at the next open and held
`max_hold_days` (21, "hold 1 month"). Catastrophic stop `stop_atr_mult` x atr_14 (engine choice; the factor has no stop). Long only (the
paper's short leg is skipped).

Data: day 0 comes from the OPTIONAL panel column `days_since_earnings` (data/fundamentals.py edgar_panel_features,
8-K Item 2.02 sessions); without it the strategy returns no signals, like insider_cluster. Approximations: the market
return is SPY's ret_1d when SPY rows are in the panel, else the same-session equal-weight mean of the panel (the paper
uses the value-weighted market); deciles are over the scanned universe, not NYSE breakpoints.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "earnings_announcement_return_abr"
DSE_COL = "days_since_earnings"


@register("strategy", NAME)
class EarningsAnnouncementReturnAbr(PanelStrategy):
    name = NAME
    description = "Month-end top decile of the 4-day abnormal return around the latest earnings report; hold 21 days."
    default_params: dict[str, Any] = {
        "window_start": -2,  # card: d = -2 .. +1 around day 0
        "window_end": 1,
        "max_report_age": 126,  # card: NaN if the last report is more than 126 sessions old
        "top_fraction": 0.10,  # card: long the top decile
        "market_symbol": "SPY",  # card: SPY as the market proxy
        "stop_atr_mult": 3.0,  # engine choice (catastrophic stop; same as revenue_surprise card)
        "max_hold_days": 21,  # card: max_hold_days 21 (Abr1)
        P_MIN_TREND: TREND_DOWN,
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: min reward:risk n/a
    }
    features_required = ["atr_14", "ret_1d", "trend_state"]
    extra_features = ["month_end"]
    engine_trail = False  # monthly factor hold

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        return bars_held >= int(self.params["max_hold_days"])

    def abr(self, frame: pd.DataFrame, positions: dict[str, np.ndarray], current: pd.DataFrame) -> pd.Series:
        """Abr per current row (NaN when day 0 is unknown, too old, or the window is not complete yet)."""
        p = self.params
        spy = frame.loc[frame[SYMBOL] == p["market_symbol"]].set_index("ts")["ret_1d"]
        mkt = frame["ts"].map(spy) if len(spy) else frame.groupby("ts")["ret_1d"].transform("mean")
        abn = (frame["ret_1d"] - mkt).to_numpy(dtype=float)
        lo, hi = int(p["window_start"]), int(p["window_end"])
        out = pd.Series(np.nan, index=current.index)
        for idx, row in current.iterrows():
            dse = row[DSE_COL]
            if not finite(dse) or not hi <= dse <= int(p["max_report_age"]):
                continue
            pos = positions[str(row[SYMBOL])]
            d0 = len(pos) - 1 - int(dse)
            if d0 + lo >= 0:
                out[idx] = abn[pos[d0 + lo : d0 + hi + 1]].sum()
        return out

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or DSE_COL not in panel.columns or not self.market_ok(regime):
            return []
        v = c1.view(self, panel, as_of, [DSE_COL])
        cur = v.current.loc[v.current[SYMBOL] != self.params["market_symbol"]]
        if cur.empty or not (cur["month_end"] == 1).any():
            return []
        abr = self.abr(v.frame, v.positions, cur)
        mult = float(self.params["stop_atr_mult"])
        out: list[Signal] = []
        for idx in cur.index[c1.top_fraction(abr, float(self.params["top_fraction"]))]:
            row = cur.loc[idx]
            close, atr = float(row["close"]), row["atr_14"]
            if not finite(atr) or not self.trend_ok(row):
                continue
            sig = self.build_signal(row, as_of, entry=close, stop=close - mult * float(atr), target=None,
                                    score=abr[idx], features={"abr": abr[idx], DSE_COL: row[DSE_COL],
                                                              "max_hold_days": self.params["max_hold_days"]},
                                    notes=f"Abr {abr[idx] * 100:+.1f}% around the report {int(row[DSE_COL])} sessions ago")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(cur), len(out))
        return out
