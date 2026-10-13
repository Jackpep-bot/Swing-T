"""CEO/CFO open-market purchase, 5-session hold (Wang, Shin & Francis 2012; Hossain 2010): docs/proposals/
swing-methods-2026-10/batch5/ceo_cfo_buy_5day.md.

`ceo_cfo_buy_value` (data.b5_events.join_b5_events) is, on the first session after a Form 4 filing date, the dollar
value of code-P purchases on that filing date by officers titled CEO or CFO who are not Cohen-Malloy-Pomorski
routine traders, and 0 on every other session. At that session's close: buy (next open, the second session after
the filing, the paper's day +2) when the value is >= $25,000, the name is in the SMALLMID universe (`_b5.smallmid`)
and no earnings report is expected within 5 sessions (`sessions_to_expected_earnings` <= 5, join_edgar; a name with
no expected date is not skipped). Sold at the close of the 5th session held (`max_hold_days`; replay and live fill
the next open, the card's fallback). Catastrophe stop entry x 0.85, no target, no trail, no regime gate.

Engine choices: the score is the purchase value, so a full book takes the larger purchases first (the card gives no
order); the 15-position cap comes from the book. `ceo_buy_value` / `cfo_buy_value` ride in the signal features for
the card's CEO / CFO split of the results.
Replay-only until the nightly runs the share and b5 joins: silent without the columns.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._b5 import MCAP, MED_DV, RANK_FIRST, RANK_LAST, smallmid
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy

NAME = "ceo_cfo_buy_5day"
VALUE, CEO, CFO = "ceo_cfo_buy_value", "ceo_buy_value", "cfo_buy_value"  # data.b5_events.join_b5_events
TO_EXP = "sessions_to_expected_earnings"  # data.fundamentals.join_edgar
MILLION = 1e6


@register("strategy", NAME)
class CeoCfoBuy5Day(PanelStrategy):
    name = NAME
    description = "Small/mid cap whose CEO or CFO filed an open-market buy >= $25k: buy next open, hold 5 sessions."
    default_params: dict[str, Any] = {
        "min_buy_value": 25_000.0,  # card: qualifying purchases on one filing date sum to >= $25,000
        "earnings_skip_sessions": 5,  # card: skip when sessions_to_expected_earnings <= 5
        "mcap_rank_first": RANK_FIRST,  # README shared definitions: SMALLMID = mcap ranks 501 ...
        "mcap_rank_last": RANK_LAST,  # ... to 3,000
        "stop_pct": 0.15,  # card: catastrophe stop entry x 0.85
        "max_hold_days": 5,  # card: exit at the close of the 5th session held
        P_MIN_MARKET_TREND: TREND_DOWN,  # card engine version: no regime gate
        P_MIN_RR: 0.0,  # card: no target
    }
    extra_features = [MED_DV]
    prior_columns: list[str] = []
    engine_trail = False  # card: time exit plus a catastrophe stop

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or any(c not in panel.columns for c in (VALUE, TO_EXP, MCAP)) or not self.market_ok(regime):
            return []
        p = self.params
        rows = c1.rows(self, panel, as_of)
        fire = ((rows[VALUE] >= float(p["min_buy_value"]))
                & smallmid(rows, int(p["mcap_rank_first"]), int(p["mcap_rank_last"]))
                & ~(rows[TO_EXP] <= float(p["earnings_skip_sessions"])))
        out: list[Signal] = []
        for _, row in rows.loc[fire].iterrows():
            close, value = float(row["close"]), float(row[VALUE])
            sig = self.build_signal(row, as_of, entry=close, stop=close * (1.0 - float(p["stop_pct"])), target=None,
                                    score=value / MILLION,
                                    features={c: row[c] for c in (VALUE, CEO, CFO, TO_EXP) if c in rows.columns},
                                    notes=f"CEO/CFO open-market purchases of ${value:,.0f}, Form 4 public from this session")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
