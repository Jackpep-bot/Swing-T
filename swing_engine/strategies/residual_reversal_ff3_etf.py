"""One-month residual reversal on ETF factor proxies (Blitz, Huij, Lansdorp & Verbeek 2013):
docs/proposals/swing-methods-2026-10/batch6/residual_reversal_ff3_etf.md.

Eligible on a session: the 500 largest names by `mcap_pit` among the rows passed in (the replay's screened
universe), close >= $5, no earnings reaction session (`days_since_earnings`) in the last 21 sessions. For each: fit
r = a + b1 x etf_mkt + b2 x etf_smb + b3 x etf_hml by least squares on the 756 sessions that end 22 sessions before
the signal day (at least 500 of them with every input present; r = close-to-close return, factor columns from
data.b6.join_b6). Score = sum over the last 21 sessions of (r - a - b'f), divided by the population standard
deviation of the fit's residuals. A name with a missing input in the last 21 sessions has no score. Book rules and
the hold-zone deviation: `_b6.MonthEndLoserBook` (buy the 50 lowest scores at month end, keep the lowest 100,
catastrophe stop 20%).

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
from . import _catalog1 as c1
from ._b6 import SINCE_EARNINGS, MonthEndLoserBook
from ._base import SYMBOL

NAME = "residual_reversal_ff3_etf"
FACTORS = ["etf_mkt", "etf_smb", "etf_hml"]  # data.b6.join_b6
NEEDS = (b5.MCAP, SINCE_EARNINGS, *FACTORS)
WARMUP_CALENDAR_DAYS = 1200  # 756 + 22 bars (~1,130 days), with a margin


def residual_score(close: np.ndarray, factors: np.ndarray, fit: int, gap: int, form: int, min_fit: int) -> float:
    """Score of one name from its closes and the (rows x 3) factor matrix, both ending at the signal day; NaN when
    the last ``form`` sessions have a gap or fewer than ``min_fit`` complete sessions fall in the fit window."""
    r = close[1:] / close[:-1] - 1.0
    x = np.column_stack([np.ones(len(r)), factors[1:]])
    if len(r) < form + gap:
        return float("nan")
    ok = np.isfinite(r) & np.isfinite(x).all(axis=1)
    if not ok[-form:].all():
        return float("nan")
    end = len(r) - gap  # the fit window is r[end - fit:end]: it ends `gap` sessions before the signal day
    lo = max(end - fit, 0)
    keep = ok[lo:end]
    if int(keep.sum()) < min_fit:
        return float("nan")
    xf, yf = x[lo:end][keep], r[lo:end][keep]
    beta, *_ = np.linalg.lstsq(xf, yf, rcond=None)
    sd = float(np.std(yf - xf @ beta))
    return float((r[-form:] - x[-form:] @ beta).sum() / sd) if sd > 0 else float("nan")


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

    def scores(self, panel: pd.DataFrame, as_of: date, rows: pd.DataFrame) -> pd.Series:
        out = pd.Series(np.nan, index=rows.index)
        if any(c not in panel.columns for c in NEEDS):
            return out
        p = self.params
        form = int(p["form_sessions"])
        ok = ((b5.mcap_rank(rows) <= int(p["universe_top"])) & (rows["close"] >= float(p["min_close"]))
              & ~(rows[SINCE_EARNINGS] < form))
        view = c1.view(self, panel, as_of, ["close", *FACTORS])
        for idx in rows.index[ok.fillna(False)]:
            w = view.window(str(rows.at[idx, SYMBOL]), ["close", *FACTORS])
            out[idx] = residual_score(w["close"], np.column_stack([w[c] for c in FACTORS]), int(p["fit_sessions"]),
                                      int(p["fit_gap_sessions"]), form, int(p["min_fit_sessions"]))
        return out
