"""Industry leaders lead, small caps lag (Hou 2007):
docs/proposals/swing-methods-2026-10/batch6/industry_leader_lag_smallmid.md.

On the last NYSE session of a week, among the rows passed in (the replay's screened universe) that have a two-digit
SIC (`sic2`, data.b6.join_b6): leaders = the 500 largest by `mcap_pit`; followers = SMALLMID (`_b5.smallmid`:
ranks 501-3,000, close >= $3, `med_dv_63` >= $1M), so the two never overlap. An industry counts with at least 3
leaders and 10 followers. L = the equal-weight mean of its leaders' 5-session returns (`roc_5`). Signal industries:
L in the top 20% of the counting industries and L >= +3%. Bought at the next open: followers of a signal industry
whose own 5-session return is at least 3 points below L, without an earnings reaction session in the last 5
sessions and not inside `event_avoid_filters`; the 30 widest gaps (L minus own return). Catastrophe stop 15% below
the signal close, no target, no trail, no regime gate. Equal weight and the 30-name cap come from the book.

Readings fixed here: "this week" is the last 5 sessions (a holiday week still reads 5); the sale is decided at the
5th close held and filled at the next open (`max_hold_days` 5: the engine has no close fill; the card sells Friday's
close). Known gap registered with the card: `sic2` is EDGAR's current code.
Replay-only: silent without `mcap_pit`, `sic2` or `days_since_earnings`.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.data.calendar import next_trading_day

from . import _b5 as b5
from . import _catalog1 as c1
from ._b6 import SINCE_EARNINGS, avoid
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy

NAME = "industry_leader_lag_smallmid"
SIC2 = "sic2"  # data.b6.join_b6
RET = "roc_5"  # features.extra: 5-session return in percent
NEEDS = (b5.MCAP, SIC2, SINCE_EARNINGS)


def is_week_end(day: date) -> bool:
    """True on the last NYSE session of an ISO week (published calendar)."""
    return next_trading_day(day).isocalendar()[:2] != day.isocalendar()[:2]


@register("strategy", NAME)
class IndustryLeaderLagSmallmid(PanelStrategy):
    name = NAME
    description = "Week end: buy small/mid caps that lagged a strong week of their SIC2 industry's large caps."
    default_params: dict[str, Any] = {
        "leader_top": 500,  # card: top-500 leaders
        "min_leaders": 3,  # card: industries need >= 3 leaders
        "min_followers": 10,  # card: and >= 10 followers
        "top_industry_fraction": 0.20,  # card: L in the top 20% of industries that week
        "min_leader_return_pct": 3.0,  # card: L >= +3%
        "min_gap_pct": 3.0,  # card: follower 5-session return <= L - 3 points
        "max_names": 30,  # card: up to 30 names, ranked by L - own return
        "earnings_sessions": 5,  # card: skip followers with their own 8-K 2.02 in the week
        "stop_pct": 15.0,  # card: catastrophe stop 15%
        "max_hold_days": 5,  # card: entry Monday open, exit Friday close (5 sessions)
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: no regime gate
        P_MIN_RR: 0.0,  # card: no target
    }
    extra_features = [RET, b5.MED_DV]
    prior_columns: list[str] = []
    engine_trail = False  # one-week hold; a trail would cut the catch-up

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or any(c not in panel.columns for c in NEEDS) or not is_week_end(as_of) \
                or not self.market_ok(regime):
            return []
        p = self.params
        rows = c1.rows(self, panel, as_of)
        if rows.empty:
            return []
        known = rows[SIC2].notna() & rows[RET].notna()
        leader = known & (b5.mcap_rank(rows) <= int(p["leader_top"]))
        follower = known & b5.smallmid(rows, first=int(p["leader_top"]) + 1)
        lead = rows.loc[leader].groupby(SIC2)[RET].agg(["mean", "count"])
        n_follow = rows.loc[follower].groupby(SIC2).size()
        lead = lead.loc[(lead["count"] >= int(p["min_leaders"]))
                        & (n_follow.reindex(lead.index).fillna(0) >= int(p["min_followers"]))]
        if lead.empty:
            return []
        strong = lead.loc[(lead["mean"].rank(pct=True) > 1.0 - float(p["top_industry_fraction"]))
                          & (lead["mean"] >= float(p["min_leader_return_pct"])), "mean"]
        industry_ret = rows[SIC2].map(strong)
        gap = industry_ret - rows[RET]
        ok = (follower & (gap >= float(p["min_gap_pct"])) & ~(rows[SINCE_EARNINGS] < float(p["earnings_sessions"]))
              & ~avoid(rows))
        out: list[Signal] = []
        for idx in gap.where(ok).dropna().sort_values(ascending=False, kind="mergesort").index[: int(p["max_names"])]:
            row, close = rows.loc[idx], float(rows.at[idx, "close"])
            sig = self.build_signal(row, as_of, entry=close, stop=close * (1.0 - float(p["stop_pct"]) / 100.0),
                                    target=None, score=float(gap[idx]),
                                    features={"leader_return_pct": industry_ret[idx], "own_return_pct": row[RET],
                                              SIC2: row[SIC2], b5.MCAP: row[b5.MCAP]},
                                    notes=f"SIC {int(row[SIC2]):02d} leaders {float(industry_ret[idx]):+.1f}% this week, "
                                          f"own {float(row[RET]):+.1f}%")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
