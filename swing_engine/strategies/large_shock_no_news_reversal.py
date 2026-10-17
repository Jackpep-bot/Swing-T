"""Large no-news shock reversal (Savor 2012; Chan 2003):
docs/proposals/swing-methods-2026-10/batch6/large_shock_no_news_reversal.md.

Universe on a session: the 1,500 highest `med_dv_63` among the rows passed in, close >= $5. Shock: the day's return
<= -5% and its excess over the market (`rel_ret_1d`) <= -3 x the sample standard deviation of that excess over the
60 sessions before it (all 60 present). No news: `news_flag_1d` = 0 (no Alpaca article in the 24 hours to the
close; a session the news table does not cover gives no signal), no 8-K reaction session today or yesterday
(`days_since_8k` > 1), no actual earnings within 3 sessions (`days_since_earnings`) and no expected earnings within
3 sessions either side (`sessions_to_expected_earnings`). Not inside `event_avoid_filters` (`_b6.avoid`).

Buy the next open. Stop: signal close - 2 x the shock day's high-low range (no signal when that is not above zero).
No target, no trail, no regime gate. Time stop `max_hold_days` 10: decided at the 10th close and filled at the next
open (the engine has no close fill; the card sells that close). When more names fire than the book has slots, the
largest shock in standard deviations goes first. Eight positions at equal risk come from the book.

Replay-only: silent without the news, 8-K or earnings columns.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._b6 import SINCE_EARNINGS, avoid
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy

NAME = "large_shock_no_news_reversal"
MED_DV, EXCESS, RET = "med_dv_63", "rel_ret_1d", "roc_1"  # features.extra (roc_1 is in percent)
NEWS, SINCE_8K, TO_EARNINGS = "news_flag_1d", "days_since_8k", "sessions_to_expected_earnings"  # data joins
NEEDS = (NEWS, SINCE_8K, SINCE_EARNINGS, TO_EARNINGS)
PCT = 100.0


@register("strategy", NAME)
class LargeShockNoNewsReversal(PanelStrategy):
    name = NAME
    description = "Buy a liquid stock after a 3-sigma, -5% one-day drop with no news, 8-K or earnings; hold 10 sessions."
    default_params: dict[str, Any] = {
        "universe_top": 1500,  # card: the 1,500 most liquid store stocks (med_dv_63)
        "min_close": 5.0,  # card: close >= $5
        "max_return_pct": -5.0,  # card: stock return <= -5%
        "shock_sigmas": 3.0,  # card: excess return <= -3.0 x its standard deviation
        "sigma_sessions": 60,  # card: over the prior 60 sessions
        "no_8k_sessions": 1,  # card: no 8-K filed t-1..t
        "earnings_sessions": 3,  # card: not within 3 sessions of an expected or actual earnings date
        "stop_range_mult": 2.0,  # card: catastrophe stop 2 x the shock day's range below entry
        "max_hold_days": 10,  # card: exit 10 sessions after entry
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: no regime gate
        P_MIN_RR: 0.0,  # card: no target
    }
    extra_features = [MED_DV, EXCESS, RET]
    prior_columns: list[str] = []
    engine_trail = False  # the card holds 10 sessions; a breakeven or N-day-low trail would cut the rebound

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or any(c not in panel.columns for c in NEEDS) or not self.market_ok(regime):
            return []
        p = self.params
        rows = c1.rows(self, panel, as_of)
        if rows.empty:
            return []
        near = float(p["earnings_sessions"])
        ok = ((rows[MED_DV].rank(ascending=False, method="first") <= int(p["universe_top"]))
              & (rows["close"] >= float(p["min_close"])) & (rows[RET] <= float(p["max_return_pct"]))
              & (rows[NEWS] == 0.0) & ~(rows[SINCE_8K] <= float(p["no_8k_sessions"]))
              & ~(rows[SINCE_EARNINGS] <= near) & ~(rows[TO_EARNINGS].abs() <= near) & ~avoid(rows))
        n = int(p["sigma_sessions"])
        out: list[Signal] = []
        if ok.any():
            view = c1.view(self, panel, as_of, [EXCESS])
        for idx in rows.index[ok.fillna(False)]:
            row = rows.loc[idx]
            prior = view.window(str(row[SYMBOL]), [EXCESS])[EXCESS][-(n + 1):-1]
            if len(prior) < n or not np.isfinite(prior).all():
                continue
            sd = float(np.std(prior, ddof=1))
            z = float(row[EXCESS]) / sd if sd > 0 else float("nan")
            close = float(row["close"])
            stop = close - float(p["stop_range_mult"]) * (float(row["high"]) - float(row["low"]))
            if not z <= -float(p["shock_sigmas"]) or stop <= 0:
                continue
            sig = self.build_signal(row, as_of, entry=close, stop=stop, target=None, score=-z,
                                    features={"shock_sigmas": z, "shock_return_pct": row[RET], EXCESS: row[EXCESS]},
                                    notes=f"{float(row[RET]):+.1f}% on no news, {z:+.1f} sd against the market")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
