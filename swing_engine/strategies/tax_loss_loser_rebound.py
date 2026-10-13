"""Tax-loss loser rebound (Ritter 1988; Lynch, Puckett & Yan 2014; Kozlowski & Lytle 2023): docs/proposals/
swing-methods-2026-10/batch5/tax_loss_loser_rebound.md.

Signal day = the 10th-to-last NYSE session of December (9 sessions follow it; `data.calendar.trading_days`, which
also drops unscheduled closures: none fell in the last ten December sessions since 2001). On it, among the SMALLMID
universe (`_b5.smallmid`: `mcap_pit` ranks 501-3,000, close >= $3, `med_dv_63` >= $1M): year-to-date return = close /
the close of the prior year's last session - 1 (price only, split-adjusted; a name with no bar that day has none);
eligible when YTD <= -40% and not inside `event_avoid_filters`; buy the 30 most negative at the next open. Sold at
the close of the 10th January session = the 19th session held (9 December sessions + 10 January; `max_hold_days`;
replay and live fill the next open, the card's fallback). Catastrophe stop entry x 0.70, no target, no trail, no
regime gate.

`event_avoid_filters` as applied here (columns from data.b5_events.join_b5_events and join_edgar): a reverse split
in the last 252 sessions; an 8-K Item 1.03 / 3.01 in the last 126; an 8-K Item 5.02 in the last 63 with no earnings
reaction session in those 63. Its rule 4 (175-190 calendar days after the first bar) cannot apply: a name with a
prior-year-end close is older than that.

Card inconsistency, coded as the rule text: the front matter says a 15-session hold, the rules (10th-to-last
December session to the 10th January session) make it 19.
Replay-only: silent without `mcap_pit`, the event columns or `days_since_earnings`.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.data.calendar import trading_days

from . import _catalog1 as c1
from ._b5 import MCAP, MED_DV, RANK_FIRST, RANK_LAST, smallmid
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, TS, PanelStrategy

NAME = "tax_loss_loser_rebound"
SPLIT, DISTRESS, LEFT = "days_since_reverse_split", "days_since_8k_distress", "days_since_8k_502"  # data.b5_events
SINCE_EARNINGS = "days_since_earnings"  # data.fundamentals.join_edgar
DECEMBER = 12
YTD = "ytd_return"


@register("strategy", NAME)
class TaxLossLoserRebound(PanelStrategy):
    name = NAME
    description = "10th-to-last December session: buy the 30 worst YTD small/mid caps; sell after 10 January sessions."
    default_params: dict[str, Any] = {
        "sessions_left_in_december": 9,  # card: signal day + 9 sessions = the last session of December
        "mcap_rank_first": RANK_FIRST,  # README shared definitions: SMALLMID = mcap ranks 501 ...
        "mcap_rank_last": RANK_LAST,  # ... to 3,000
        "max_ytd_return": -0.40,  # card: YTD <= -40%
        "max_names": 30,  # card: the 30 most negative YTD
        "avoid_reverse_split_sessions": 252,  # event_avoid_filters rule 1
        "avoid_distress_8k_sessions": 126,  # event_avoid_filters rule 2 (Item 1.03 / 3.01)
        "avoid_502_sessions": 63,  # event_avoid_filters rule 3 (Item 5.02 with no earnings in the window)
        "stop_pct": 0.30,  # card: catastrophe stop at entry x 0.70
        "max_hold_days": 19,  # card: exit at the close of the 10th January session (9 December + 10 January held)
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: no regime gate
        P_MIN_RR: 0.0,  # card: no target
    }
    extra_features = [MED_DV]
    prior_columns: list[str] = []
    engine_trail = False  # card: no trail

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        needed = (MCAP, SPLIT, DISTRESS, LEFT, SINCE_EARNINGS)
        if panel.empty or any(c not in panel.columns for c in needed) or not self.market_ok(regime):
            return []
        p = self.params
        left = trading_days(as_of + timedelta(days=1), date(as_of.year, DECEMBER, 31))
        if as_of.month != DECEMBER or len(left) != int(p["sessions_left_in_december"]):
            return []
        rows = c1.rows(self, panel, as_of)
        if rows.empty or pd.Timestamp(rows[TS].iloc[0]).date() != as_of:
            return []
        year_end = trading_days(date(as_of.year - 1, DECEMBER, 1), date(as_of.year - 1, DECEMBER, 31))[-1]
        day = pd.to_datetime(panel[TS]).dt.tz_localize(None).dt.normalize()
        base = panel.loc[(day == pd.Timestamp(year_end)).to_numpy()].set_index(SYMBOL)["close"]
        rows = rows.assign(**{YTD: rows["close"] / rows[SYMBOL].map(base) - 1.0})
        w = float(p["avoid_502_sessions"])
        avoid = ((rows[SPLIT] <= float(p["avoid_reverse_split_sessions"]))
                 | (rows[DISTRESS] <= float(p["avoid_distress_8k_sessions"]))
                 | ((rows[LEFT] <= w) & ~(rows[SINCE_EARNINGS] <= w)))
        ok = (smallmid(rows, int(p["mcap_rank_first"]), int(p["mcap_rank_last"]))
              & (rows[YTD] <= float(p["max_ytd_return"])) & ~avoid)
        picks = rows.loc[ok].sort_values([YTD, SYMBOL]).head(int(p["max_names"]))
        out: list[Signal] = []
        for i, (_, row) in enumerate(picks.iterrows()):
            close = float(row["close"])
            sig = self.build_signal(row, as_of, entry=close, stop=close * (1.0 - float(p["stop_pct"])), target=None,
                                    score=1.0 - i / max(len(picks), 1), features={YTD: row[YTD], MCAP: row[MCAP]},
                                    notes=f"year-to-date {float(row[YTD]):+.0%} with {len(left)} December sessions left")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
