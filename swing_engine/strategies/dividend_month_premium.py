"""Dividend month premium (Hartzmark & Solomon 2013; Chen-Zimmermann `DivSeason`): project file
research/strategies/dividend_month_premium.md, pre-registered in docs/preregistration/2026-10-13-dividend-month.md.

`div_season` (data.dividends.join_dividends) is 1 on a month's last NYSE session for a common stock predicted to go
ex-dividend next month (it went ex 3, 6, 9 or 12 months before that month; 6 or 12 for a semi-annual payer; 12 for an
annual one). On that session: among predicted payers with a close >= $5, a 63-day median dollar volume >= $20M and
a point-in-time market cap from EDGAR share counts (`mcap_pit`, data.fundamentals.join_share_issuance: the store's
`symbols.type` calls SPY a common stock, and funds do not file share counts), buy the `max_names` with the largest
median dollar volume at the next open, and hold for the month. A held name is
sold at the open after the next month's last session unless it is predicted again. Catastrophe stop 3 x ATR(63) (the
engine sizes on it). No target, no regime gate, `engine_trail = False`. Equal weight and the name cap's slots come
from the book (config/prereg_div.yaml). Replay-only: the CLI scan and nightly do not run the dividend join, so the
column is absent there and the strategy is silent. Grade on a total-return store (data.dividends.total_return_adjust).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, finite

NAME = "dividend_month_premium"
DIV = "div_season"  # data.dividends.join_dividends
MCAP = "mcap_pit"  # data.fundamentals.join_share_issuance: present for companies that file share counts
MONTH_END, MED_DV, ATR = "month_end", "med_dv_63", "atr_63"  # features.extra


@register("strategy", NAME)
class DividendMonthPremium(PanelStrategy):
    name = NAME
    description = "Month end: buy the 50 most liquid stocks predicted to go ex-dividend next month; hold one month."
    default_params: dict[str, Any] = {
        "max_names": 50,  # registered: the book's 50 slots, filled by median dollar volume
        "min_price": 5.0,  # card: price >= $5
        "min_median_dollar_volume": 20e6,  # card: 63-day median dollar volume >= $20M
        "stop_atr_mult": 3.0,  # catastrophe stop 3 x atr_63, as the other monthly books
        "max_hold_days": 10_000,  # the month end is the exit (finite so the 20-bar backtest default never applies)
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: no regime gate
        P_MIN_RR: 0.0,  # card: no target
    }
    extra_features = [MONTH_END, MED_DV, ATR]
    prior_columns: list[str] = []
    engine_trail = False  # month-end exit only

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        """On a month's last session: sell unless the name is predicted to go ex again next month."""
        flag = row.get(MONTH_END)
        if not finite(flag) or float(flag) != 1.0:
            return False
        again = row.get(DIV)
        return not finite(again) or float(again) != 1.0

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or DIV not in panel.columns or MCAP not in panel.columns or not self.market_ok(regime):
            return []
        rows = c1.rows(self, panel, as_of)
        if rows.empty or not (rows[MONTH_END] == 1.0).any():
            return []
        ok = ((rows[DIV] == 1.0) & rows[MCAP].notna() & (rows["close"] >= float(self.params["min_price"]))
              & (rows[MED_DV] >= float(self.params["min_median_dollar_volume"])))
        picks = rows.loc[ok].sort_values([MED_DV, "symbol"], ascending=[False, True]).head(int(self.params["max_names"]))
        mult = float(self.params["stop_atr_mult"])
        out: list[Signal] = []
        for rank, (_, row) in enumerate(picks.iterrows()):
            atr, close = row[ATR], float(row["close"])
            if not finite(atr):
                continue
            sig = self.build_signal(row, as_of, entry=close, stop=close - mult * float(atr), target=None,
                                    score=1.0 - rank / max(len(picks), 1), features={DIV: row[DIV], MED_DV: row[MED_DV]},
                                    notes=f"predicted ex-dividend next month; median dollar volume ${float(row[MED_DV]) / 1e6:,.0f}M")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
