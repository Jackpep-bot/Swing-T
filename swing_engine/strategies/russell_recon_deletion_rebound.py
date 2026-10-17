"""Russell 2000 deletion rebound (Cai & Houge; Dimensional 2014-2023): docs/proposals/swing-methods-2026-10/batch5/
russell_recon_deletion_rebound.md.

Membership proxy and reconstitution calendar: `russell_recon_addition_frontrun` (total `mcap_pit` rank on rank
days, read from the panel rows of the rank day itself, so only bars and filings known that day enter). At the close
of a reconstitution day: buy (next open) names with 1,200 <= rank_prev <= 2,900 AND rank_R >= 3,200, where rank_R is
the rank on this event's rank day and rank_prev the rank on the rank day before it; `med_dv_63` >= $500k and an
as-traded close >= $1 on the signal day; no reverse split (`days_since_reverse_split`) and no 8-K Item 1.03 / 3.01
(`days_since_8k_distress`) in the last 126 sessions (both from data.b5_events.join_b5_events). At most 40, the
largest fall in rank first. Sold at the close of the 20th session held (`max_hold_days`; replay and live fill the
next open). Catastrophe stop entry x 0.75, no target, no trail, no regime gate.

Deviations and limits:
* Ranks are taken among the rows the caller passes (the replay's screened universe as of the signal day), so both
  ranks are among names still liquid enough for that screen on reconstitution day. A name with no rank on the rank
  day (no share count, or under $1) is not a candidate.
* History: the previous rank day is 288-293 sessions before the June reconstitution day (2017-2026), just inside the
  replay's 300-session signal slice (research.replay.SIGNAL_LOOKBACK_SESSIONS); `warmup_calendar_days` is raised so
  a window starting shortly before a reconstitution day still loads it. No signals when the panel has no bars on
  either rank day.
* Replay-only: silent without `mcap_pit` and the two event columns.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._b5 import MCAP, MED_DV
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, TS, PanelStrategy
from .russell_recon_addition_frontrun import (
    CALENDAR_PARAMS,
    as_traded_close,
    local_day,
    mcap_ranks,
    recon_events,
)

NAME = "russell_recon_deletion_rebound"
SPLIT, DISTRESS = "days_since_reverse_split", "days_since_8k_distress"  # data.b5_events.join_b5_events


@register("strategy", NAME)
class RussellReconDeletionRebound(PanelStrategy):
    name = NAME
    description = "Recon day: buy names that fell out of the proxy Russell 2000 by market-cap rank; hold 20 sessions."
    default_params: dict[str, Any] = {
        **CALENDAR_PARAMS,
        "prev_rank_min": 1200,  # card: 1,200 <= rank_prev ...
        "prev_rank_max": 2900,  # ... <= 2,900 (was well inside the proxy Russell 2000)
        "rank_min": 3200,  # card: rank_R >= 3,200 (well below it)
        "avoid_sessions": 126,  # card: no reverse split / 8-K Item 1.03 / 3.01 in the last 126 sessions
        "min_median_dollar_volume": 500_000.0,  # card: med_dv_63 >= $500k at entry
        "min_close": 1.0,  # card: close >= $1 at entry
        "max_names": 40,  # card: max 40, ranked by the largest fall in rank
        "stop_pct": 0.25,  # card: catastrophe stop entry x 0.75
        "max_hold_days": 20,  # card: exit at the close of the 20th session held
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: no regime gate
        P_MIN_RR: 0.0,  # card: no target
    }
    extra_features = [MED_DV]
    prior_columns: list[str] = []
    engine_trail = False  # card: no trail
    warmup_calendar_days = 450  # the previous rank day is up to 293 sessions (~425 calendar days) before the signal

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or any(c not in panel.columns for c in (MCAP, SPLIT, DISTRESS)) or not self.market_ok(regime):
            return []
        p = self.params
        events = recon_events(p, as_of.year)
        k = next((i for i, (_, recon_day) in enumerate(events) if recon_day == as_of), None)
        if not k:  # not a reconstitution day (or no earlier rank day to compare with)
            return []
        rows = c1.rows(self, panel, as_of)
        if rows.empty or pd.Timestamp(rows[TS].iloc[0]).date() != as_of:
            return []
        day = local_day(panel)
        now = mcap_ranks(panel, day, events[k][0], float(p["rank_min_close"]))
        prev = mcap_ranks(panel, day, events[k - 1][0], float(p["rank_min_close"]))
        if now.empty or prev.empty:
            return []
        rows = rows.assign(rank_r=rows[SYMBOL].map(now), rank_prev=rows[SYMBOL].map(prev))
        rows["rank_fall"] = rows["rank_r"] - rows["rank_prev"]
        recent = (rows[SPLIT] <= float(p["avoid_sessions"])) | (rows[DISTRESS] <= float(p["avoid_sessions"]))
        ok = (rows["rank_prev"].between(float(p["prev_rank_min"]), float(p["prev_rank_max"]))
              & (rows["rank_r"] >= float(p["rank_min"])) & ~recent
              & (rows[MED_DV] >= float(p["min_median_dollar_volume"])) & (as_traded_close(rows) >= float(p["min_close"])))
        picks = rows.loc[ok].sort_values(["rank_fall", SYMBOL], ascending=[False, True]).head(int(p["max_names"]))
        out: list[Signal] = []
        for i, (_, row) in enumerate(picks.iterrows()):
            close = float(row["close"])
            sig = self.build_signal(
                row, as_of, entry=close, stop=close * (1.0 - float(p["stop_pct"])), target=None,
                score=1.0 - i / max(len(picks), 1),
                features={"rank_r": row["rank_r"], "rank_prev": row["rank_prev"], "rank_fall": row["rank_fall"]},
                notes=f"market-cap rank {row['rank_prev']:.0f} -> {row['rank_r']:.0f} between rank days "
                      f"{events[k - 1][0]} and {events[k][0]}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
