"""Inside-bar / outside-bar breakouts (long), docs/strategies/inside_outside_bar_breakout.md (catalog B40/C51, P8/P9).

`variant` (pre-register one per trial; the card says keep the families apart):
- `inside_breakout` (Williams/Crabel): the as-of bar is inside the prior bar; buy stop at the inside-bar high for the
  next session (EntryType.STOP), stop under the inside-bar low; optional NR filter via `nr_col` (e.g. "nr7").
- `inside_builtin` (thinkorswim/TradingView): inside bar that closed up -> buy the next open, stop the inside-bar low.
- `outside` (TradeStation Outside Bar + card): outside bar closing up with close_pos >= 0.75 -> buy stop above its high,
  stop its low. The card allows the trigger within 2 bars; the engine's stop order lives one session.
Trend direction only (`trend_state == 1`, card). Target entry + 2R, 5-session cap (card).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, TREND_UP, PanelStrategy, finite

NAME = "inside_outside_bar_breakout"
INSIDE_BREAKOUT, INSIDE_BUILTIN, OUTSIDE = "inside_breakout", "inside_builtin", "outside"


@register("strategy", NAME)
class InsideOutsideBarBreakout(PanelStrategy):
    name = NAME
    description = "Inside bar in an uptrend: buy stop over its high, stop under its low, 2R target (variants: built-in, outside)."
    default_params: dict[str, Any] = {
        "variant": INSIDE_BREAKOUT,  # card: classic breakout; "inside_builtin" / "outside" are comparison trials
        "nr_col": None,  # card: optional NR filter ("nr4" / "nr7" from features.extra); None = off
        "outside_close_pos_min": 0.75,  # card: bullish outside bar closes near its high (close_pos >= 0.75)
        "stop_atr_buffer": 0.0,  # card: stop = bar low - 0.0 x atr_14
        "target_r": 2.0,  # card: target = entry + 2R
        "max_hold_days": 5,  # card
        P_MIN_TREND: TREND_UP,  # card: trend_state == 1 for longs
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 2.0,  # card
    }
    features_required = ["atr_14", "trend_state"]

    def required_features(self) -> list[str]:
        nr = self.params.get("nr_col")
        return [*self.features_required, str(nr)] if nr else list(self.features_required)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        rows = c1.rows(self, panel, as_of)
        variant, nr = str(self.params["variant"]), self.params.get("nr_col")
        buf, tr = float(self.params["stop_atr_buffer"]), float(self.params["target_r"])
        out: list[Signal] = []
        for _, row in rows.iterrows():
            h, lo, o, c = (float(row[k]) for k in ("high", "low", "open", "close"))
            ph, pl, atr = row["prior_high"], row["prior_low"], row["atr_14"]
            if not (finite(ph) and finite(pl) and finite(atr)) or not self.trend_ok(row):
                continue
            if nr and row.get(str(nr)) != 1:
                continue
            inside, outside = h < ph and lo > pl, h > ph and lo < pl
            if variant == OUTSIDE:
                ok = outside and c > o and h > lo and (c - lo) / (h - lo) >= float(self.params["outside_close_pos_min"])
            else:
                ok = inside and (variant == INSIDE_BREAKOUT or c > o)
            if not ok:
                continue
            entry = c if variant == INSIDE_BUILTIN else h
            stop = lo - buf * float(atr)
            sig = self.build_signal(row, as_of, entry=entry, stop=stop, target=entry + tr * (entry - stop),
                                    score=-(h - lo) / float(atr) if float(atr) > 0 else 0.0,
                                    features={"bar_high": h, "bar_low": lo, "mother_high": ph, "mother_low": pl,
                                              "max_hold_days": self.params["max_hold_days"]},
                                    notes=f"{variant}: bar {lo:.2f}-{h:.2f} vs prior {float(pl):.2f}-{float(ph):.2f}")
            if sig:
                out.append(sig if variant == INSIDE_BUILTIN else c1.stop_entry(sig))
        self.log_scan(as_of, len(rows), len(out))
        return out
