"""Marketed follow-on offering rebound (price pressure around seasoned equity offerings, sample 2000-2014; Corwin
2003): docs/proposals/swing-methods-2026-10/batch7/seo_marketed_offer_rebound.md.

Signal on a symbol's reaction session to a 424B4 or 424B5 prospectus with no 424B of any kind in the 90 days before
(`offer_event`, data.b7.join_b7). Pressure: the close of the session before the signal is at least 4% under the
close 6 sessions before the signal, and that 5-session return minus the market's (`market_close`, SPY) is at most
-3%. Close >= $5 and `med_dv_63` >= $2M on the signal day; not inside `event_avoid_filters` (`_b6.avoid`; none of
its rules is about offerings). Buy the next open; catastrophe stop 12% below the signal close; no target, no trail,
no regime gate. Time stop `max_hold_days` 7: decided at the 7th close and filled at the next open (the engine has no
close fill; the card sells that close). Biggest relative drop first when slots are short; eight positions at equal
risk come from the book. The card's descriptive split without the pressure filter is not run.
Replay-only: silent without `offer_event`.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _b5 as b5
from . import _catalog1 as c1
from ._b6 import avoid
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy

NAME = "seo_marketed_offer_rebound"
EVENT, MARKET = "offer_event", "market_close"  # data.b7.join_b7; features.extra
LOOKBACK = 7  # closes read: signal day, the session before it, and 6 sessions before the signal


@register("strategy", NAME)
class SeoMarketedOfferRebound(PanelStrategy):
    name = NAME
    description = "Buy after a marketed share offering that followed a 4%+ drop; hold 7 sessions."
    default_params: dict[str, Any] = {
        "min_close": 5.0,  # card: close >= $5
        "min_dollar_volume": 2e6,  # card: med_dv_63 >= $2M
        "max_drop": -0.04,  # card: close before the signal <= 0.96 x the close 6 sessions earlier
        "max_relative_drop": -0.03,  # card: and its return minus SPY's over those 5 sessions <= -3%
        "stop_pct": 12.0,  # card: catastrophe stop 12% below entry
        "max_hold_days": 7,  # card: exit at the close of the 7th session after entry
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: no regime gate
        P_MIN_RR: 0.0,  # card: no target
    }
    extra_features = [b5.MED_DV, MARKET]
    prior_columns: list[str] = []
    engine_trail = False  # a 7-session hold

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or EVENT not in panel.columns or not self.market_ok(regime):
            return []
        p = self.params
        rows = c1.rows(self, panel, as_of)
        if rows.empty:
            return []
        ok = ((rows[EVENT] == 1.0) & (rows["close"] >= float(p["min_close"]))
              & (rows[b5.MED_DV] >= float(p["min_dollar_volume"])) & ~avoid(rows))
        out: list[Signal] = []
        if ok.any():
            view = c1.view(self, panel, as_of, [MARKET])
        for _, row in rows.loc[ok.fillna(False)].iterrows():
            w = view.window(str(row[SYMBOL]), ["close", MARKET])
            c, m = w["close"][-LOOKBACK:], w[MARKET][-LOOKBACK:]
            if len(c) < LOOKBACK or not (np.isfinite(c).all() and np.isfinite(m).all()):
                continue
            ret, rel = c[-2] / c[0] - 1.0, c[-2] / c[0] - m[-2] / m[0]
            if ret > float(p["max_drop"]) or rel > float(p["max_relative_drop"]):
                continue
            close = float(row["close"])
            sig = self.build_signal(row, as_of, entry=close, stop=close * (1.0 - float(p["stop_pct"]) / 100.0),
                                    target=None, score=-rel, features={"pre_offer_return": ret, "pre_offer_vs_spy": rel},
                                    notes=f"offering after {ret:+.1%} ({rel:+.1%} against SPY) over 5 sessions")
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
