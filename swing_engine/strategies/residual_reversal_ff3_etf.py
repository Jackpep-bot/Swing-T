"""One-month residual reversal on ETF factor proxies (Blitz, Huij, Lansdorp & Verbeek 2013):
docs/proposals/swing-methods-2026-10/batch6/residual_reversal_ff3_etf.md.

Eligible on a session: the 500 largest names by `mcap_pit` among the rows passed in (the replay's screened
universe), close >= $5, no earnings reaction session (`days_since_earnings`) in the last 21 sessions. Score =
`etf3_resid_rev_756_21_22_500` (features.extra): r = a + b1 x etf_mkt + b2 x etf_smb + b3 x etf_hml fitted by least
squares on the 756 sessions that end 22 sessions before the signal day (at least 500 with every input present;
r = close-to-close return, factor columns from data.b6.join_b6), then the sum over the last 21 sessions of
(r - a - b'f) divided by the population standard deviation of the fit's residuals; NaN when the last 21 sessions
have a gap. It is computed on the whole panel (the replay hands `signals` only its last 300 sessions) and only on a
month's last two sessions. Book rules and the hold-zone deviation: `_b6.MonthEndLoserBook` (buy the 50 lowest
scores at month end, keep the lowest 100, catastrophe stop 20%).

Readings fixed here: the residual subtracts the fit's intercept as well as the factor terms; "excess return" is the
plain daily return (no risk-free leg: the factor proxies are ETF returns, and the intercept absorbs a constant).
The replay loads `warmup_calendar_days` of bars before its first session. The store's ETF history starts in 2016,
so the first score of the 2017-24 window appears about 522 sessions after that (early 2018).
Replay-only: silent without `mcap_pit`, `days_since_earnings` or the factor columns.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.registry import register

from . import _b5 as b5
from ._b6 import SINCE_EARNINGS, MonthEndLoserBook

NAME = "residual_reversal_ff3_etf"
FACTORS = ["etf_mkt", "etf_smb", "etf_hml"]  # data.b6.join_b6
NEEDS = (b5.MCAP, SINCE_EARNINGS, *FACTORS)
WARMUP_CALENDAR_DAYS = 1200  # 756 + 22 bars (~1,130 days), with a margin


@register("strategy", NAME)
class ResidualReversalFf3Etf(MonthEndLoserBook):
    name = NAME
    description = "Month end: buy the 50 large caps with the most negative one-month factor-neutral residual."
    default_params: dict[str, Any] = {
        "universe_top": 500,  # card: the 500 largest store stocks by mcap_pit
        "min_close": 5.0,  # card: close >= $5
        "fit_sessions": 756,  # card: betas over 756 sessions
        "fit_gap_sessions": 22,  # card: ending 22 sessions before the rebalance day
        "min_fit_sessions": 500,  # card: at least 500 sessions present
        "form_sessions": 21,  # card: sum of the last 21 sessions' residuals; also the earnings exclusion window
        **MonthEndLoserBook.BOOK_PARAMS,
    }
    warmup_calendar_days = WARMUP_CALENDAR_DAYS

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        p = self.params
        self.score_column = (f"etf3_resid_rev_{int(p['fit_sessions'])}_{int(p['form_sessions'])}_"
                             f"{int(p['fit_gap_sessions'])}_{int(p['min_fit_sessions'])}")
        self.extra_features = [self.score_column]

    def scores(self, panel: pd.DataFrame, as_of: date, rows: pd.DataFrame) -> pd.Series:
        if any(c not in panel.columns for c in NEEDS):
            return pd.Series(np.nan, index=rows.index)
        p = self.params
        ok = ((b5.mcap_rank(rows) <= int(p["universe_top"])) & (rows["close"] >= float(p["min_close"]))
              & ~(rows[SINCE_EARNINGS] < int(p["form_sessions"])))
        return rows[self.score_column].where(ok)
