"""First green day (Tim Sykes), long: docs/proposals/swing-methods-2026-10/batch5/sykes_first_green_day.md.

Universe: close $1-$20, `med_dv_63` >= $1M, `mcap_pit` <= $2B. Signal on close t: a runner (the highest close of
t-25..t-3 is at least 2.0 x the lowest close of the 20 sessions before that peak) that sold off (3+ consecutive down
closes ending at t-1 and close t-1 <= 0.70 x the peak close), then the first green day: close > open, close > close
t-1, `close_pos` >= 0.75 and volume >= 1.5 x `avg_vol_20d` (the panel's 20-session average, today included). Stop:
the signal-day low. Score (engine choice, the card ranks nothing): volume / `avg_vol_20d`.

Which fill ran (card's registered deviation): the engine has no market-on-close entry (EntryType is open / stop /
limit), so the entry is the NEXT OPEN and the overnight gap Sykes holds for is not captured; this is a test of day-2
follow-through. Exit: `max_hold_days` = 1, the close of the entry session in `run_backtest`; the replay's position
manager decides at that close and fills at the following open (the card's next-open fallback). A gap-down open
through the stop is not entered (engine rule; Sykes exits at once on a gap down).

Needs `mcap_pit` (EDGAR share join) and is silent without it. `event_avoid_filters` (reverse splits) is graded as its
own card and is not applied here. Longest look-back is med_dv_63, inside the replay window.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _b5
from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy

NAME = "sykes_first_green_day"
AVG_VOL = "avg_vol_20d"  # card: 20-session average volume


@register("strategy", NAME)
class SykesFirstGreenDay(PanelStrategy):
    name = NAME
    description = "Small-cap runner (2x in a month) down 30%+ over 3+ red days prints a strong green day; hold a day."
    default_params: dict[str, Any] = {
        "min_price": 1.0,  # card: close $1 ...
        "max_price": 20.0,  # ... to $20
        "min_median_dollar_vol": 1_000_000.0,  # card: med_dv_63 >= $1M
        "max_mcap": 2_000_000_000.0,  # card: mcap_pit <= $2B
        "peak_first": 25,  # card (F): peak = max close over t-25 ...
        "peak_last": 3,  # ... to t-3
        "base_sessions": 20,  # card (F): min close over the 20 sessions before that peak
        "runner_mult": 2.0,  # card (F): peak >= 2.0 x that low (a double)
        "min_down_closes": 3,  # card (F): at least 3 consecutive down closes ending at t-1
        "selloff_frac": 0.70,  # card (F): close(t-1) <= 0.70 x the peak close
        "min_close_pos": 0.75,  # card (F): close_pos >= 0.75
        "min_volume_ratio": 1.5,  # card (F): volume >= 1.5 x 20-session average volume
        "max_hold_days": 1,  # card: exit at the close of the session after the signal (replay: the following open)
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: no market gate
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["close_pos", AVG_VOL]
    extra_features = [_b5.MED_DV]
    prior_columns: list[str] = []

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime) or _b5.MCAP not in panel.columns:
            return []
        p = self.params
        view = c1.view(self, panel, as_of, [_b5.MCAP])
        cur = view.current
        if cur.empty:
            return []
        close = cur["close"]
        keep = (
            (close >= float(p["min_price"])) & (close <= float(p["max_price"]))
            & (cur[_b5.MED_DV] >= float(p["min_median_dollar_vol"])) & (cur[_b5.MCAP] <= float(p["max_mcap"]))
            & (close > cur["open"]) & (cur["close_pos"] >= float(p["min_close_pos"]))
            & (cur["volume"] >= float(p["min_volume_ratio"]) * cur[AVG_VOL])
        )
        first, last, base_n, k = int(p["peak_first"]), int(p["peak_last"]), int(p["base_sessions"]), int(p["min_down_closes"])
        out: list[Signal] = []
        for _, row in cur.loc[keep].iterrows():
            cl = view.window(str(row[SYMBOL]), ["close"])["close"]
            if len(cl) < first + 1 + base_n or not np.isfinite(cl[-(first + 1 + base_n):]).all():
                continue
            peak_at = len(cl) - (first + 1) + int(np.argmax(cl[-(first + 1):-last]))
            peak, base = float(cl[peak_at]), float(cl[peak_at - base_n:peak_at].min())
            if peak < float(p["runner_mult"]) * base:
                continue  # not a runner
            if not (np.diff(cl[-(k + 2):-1]) < 0).all() or cl[-2] > float(p["selloff_frac"]) * peak:
                continue  # no 3-day selloff of 30% off the peak
            c = float(row["close"])
            if not c > cl[-2]:
                continue
            ratio = float(row["volume"]) / float(row[AVG_VOL])
            sig = self.build_signal(
                row, as_of, entry=c, stop=float(row["low"]), target=None, score=ratio,
                features={"peak_close": peak, "base_close": base, "selloff": 1.0 - float(cl[-2]) / peak,
                          "volume_ratio": ratio, "max_hold_days": p["max_hold_days"]},
                notes=f"first green day after {1.0 - float(cl[-2]) / peak:.0%} off a {peak / base:.1f}x run; "
                f"volume {ratio:.1f}x",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(cur), len(out))
        return out
