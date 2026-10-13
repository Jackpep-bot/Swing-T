"""Pocket pivot (Morales & Kacher), long: docs/proposals/swing-methods-2026-10/batch5/pocket_pivot_morales_kacher.md.

Signal on close t in the SMALLMID universe (`_b5.smallmid`): an up close whose volume beats the largest down-day
volume of t-10..t-1 (no down day there: no signal), `close_pos` >= 0.5, low <= 1.01 x sma_10 and close <= 1.05 x
sma_10, close > sma_50 > sma_200, within 25% of the 52-week high, no V (close t-1 / close t-11 - 1 <= 15%), no wedge
(fewer than 7 up closes in t-10..t-1: the card's "last 10 sessions" is read as the same ten sessions before t), close
not below the close 105 sessions ago, and no expected earnings within 3 sessions (a row with no expected date is not
skipped). Entry next open. Initial stop min(signal-day low, 0.92 x signal close): the lower of the two, as the card
writes it, on the signal close because the next open is not known at the signal.

Exit, the card's mechanical seven-week rule, as a resting stop the engine only tightens (`trail_stop`): on a close
below sma_10 after 35 straight closes above it the stop goes to that session's low; otherwise, on a close below
sma_50, to that low x 0.975. "35 straight closes above sma_10" is read off `prev_min_35_of_bb_pctb_10` > 0.5 (%B of
the 10-day band is 0.5 exactly at sma_10). Max hold 63 sessions. `engine_trail = False`: the breakeven / N-day-low
overlay is not in the card. Score (engine choice, the card ranks nothing): volume / largest down-day volume.

Needs `mcap_pit` and `sessions_to_expected_earnings` (EDGAR joins) and is silent without them. Longest look-back is
sma_200, inside the replay's 300-session signal window.
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
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "pocket_pivot_morales_kacher"
TO_EXP = "sessions_to_expected_earnings"  # data.fundamentals
FAST_MA, SLOW_MA, LONG_MA = "sma_10", "sma_50", "sma_200"  # card: 10-day line, 50-day, 200-day
PCTB_AT_MA = 0.5  # features.extra bb_pctb_10 = 0.5 + (close - sma_10) / (4 sd): above 0.5 <=> close above sma_10


@register("strategy", NAME)
class PocketPivotMoralesKacher(PanelStrategy):
    name = NAME
    description = "Up day on volume above every down-day volume of the prior 10 sessions, off the 10-day line."
    default_params: dict[str, Any] = {
        "lookback": 10,  # card: prior 10 sessions (down-volume rule, V and wedge tests)
        "min_close_pos": 0.5,  # card: close in the upper half of the range
        "max_low_over_ma": 0.01,  # card (F): low <= 1.01 x sma_10
        "max_close_over_ma": 0.05,  # card (F): close <= 1.05 x sma_10 (not extended)
        "max_dist_52w_high": 0.25,  # card (F): dist_52w_high >= -0.25
        "max_prior_return": 0.15,  # card (F): skip a V, 10-session return before t above +15%
        "wedge_up_closes": 7,  # card (F): skip when 7+ of the 10 sessions closed up
        "downtrend_sessions": 105,  # card (F): skip if the close 105 sessions ago is above today's (5 months)
        "earnings_skip_sessions": 3,  # card: skip if sessions_to_expected_earnings <= 3
        "stop_pct": 0.08,  # card: initial stop min(signal-day low, entry x 0.92)
        "respect_sessions": 35,  # card (F): 7 weeks of closes above sma_10 switch the exit to the 10-day line
        "slow_ma_slack": 0.025,  # card (F): 50-day form uses the trigger low x 0.975
        "max_hold_days": 63,  # card: max hold 63 sessions
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: no market gate
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = [FAST_MA, SLOW_MA, LONG_MA, "close_pos", "dist_52w_high"]
    extra_features = [_b5.MED_DV, "prev_min_35_of_bb_pctb_10"]
    prior_columns: list[str] = []
    engine_trail = False  # the card's own 10-day / 50-day violation stop runs alone

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        self.respect_col = f"prev_min_{int(self.params['respect_sessions'])}_of_bb_pctb_10"
        self.extra_features = [_b5.MED_DV, self.respect_col]  # param-dependent name

    def trail_stop(self, row: pd.Series) -> float | None:
        close, low = row.get("close"), row.get("low")
        if not (finite(close) and finite(low)) or float(low) <= 0:
            return None
        respected = row.get(self.respect_col)
        if finite(respected) and float(respected) > PCTB_AT_MA:  # seven weeks above the 10-day: first violation
            fast = row.get(FAST_MA)
            return float(low) if finite(fast) and float(close) < float(fast) else None
        slow = row.get(SLOW_MA)
        if finite(slow) and float(close) < float(slow):
            return float(low) * (1.0 - float(self.params["slow_ma_slack"]))
        return None

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime) or any(c not in panel.columns for c in (_b5.MCAP, TO_EXP)):
            return []
        p = self.params
        view = c1.view(self, panel, as_of, [_b5.MCAP, TO_EXP])
        cur = view.current
        if cur.empty:
            return []
        n, back = int(p["lookback"]), int(p["downtrend_sessions"])
        close, fast = cur["close"], cur[FAST_MA]
        keep = (
            _b5.smallmid(cur)
            & (cur["close_pos"] >= float(p["min_close_pos"]))
            & (cur["low"] <= (1.0 + float(p["max_low_over_ma"])) * fast)
            & (close <= (1.0 + float(p["max_close_over_ma"])) * fast)
            & (close > cur[SLOW_MA]) & (cur[SLOW_MA] > cur[LONG_MA])
            & (cur["dist_52w_high"] >= -float(p["max_dist_52w_high"]))
            & ~(cur[TO_EXP] <= float(p["earnings_skip_sessions"]))
        )
        out: list[Signal] = []
        for _, row in cur.loc[keep].iterrows():
            w = view.window(str(row[SYMBOL]), ["close", "volume"])
            cl, vol = w["close"], w["volume"]
            if len(cl) < max(n + 2, back + 1) or not (np.isfinite(cl[-(n + 2):]).all() and finite(cl[-1 - back])):
                continue
            chg = np.diff(cl[-(n + 2):])  # close changes of t-n .. t
            prior, down = chg[:-1], chg[:-1] < 0
            if chg[-1] <= 0 or not down.any():
                continue
            max_down = float(vol[-(n + 1):-1][down].max())
            if not float(vol[-1]) > max_down:
                continue
            if cl[-2] / cl[-(n + 2)] - 1.0 > float(p["max_prior_return"]) or (prior > 0).sum() >= int(p["wedge_up_closes"]):
                continue  # V-shaped snap-back or wedging drift-up
            if cl[-1 - back] > cl[-1]:
                continue  # five-month downtrend
            c = float(row["close"])
            ratio = float(vol[-1]) / max_down if max_down > 0 else 0.0
            sig = self.build_signal(
                row, as_of, entry=c, stop=min(float(row["low"]), c * (1.0 - float(p["stop_pct"]))), target=None,
                score=ratio,
                features={"max_down_volume": max_down, "volume_ratio": ratio, FAST_MA: row[FAST_MA],
                          SLOW_MA: row[SLOW_MA], "max_hold_days": p["max_hold_days"]},
                notes=f"pocket pivot: volume {ratio:.2f}x the largest down-day volume of the prior {n} sessions",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(cur), len(out))
        return out
