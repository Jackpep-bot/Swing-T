"""Green line breakout (Eric Wish), long: docs/proposals/swing-methods-2026-10/batch5/green_line_breakout_wish.md.

Green line on day t = the highest price of all completed calendar months, valid only when the month that set it is
followed by at least three completed months that did not beat it (the current month never counts). Signal: close t
above the line and close t-1 at or below it, SMALLMID universe (`_b5.smallmid`), at least 504 sessions of history
(`hist_bars`), market gate SPY close > its 50-day average (`market_close` > `sma_50_of_market_close`, the GMI
stand-in). Entry next open, catastrophe stop 0.85 x signal close. Exits at the close (`should_exit`; the replay fills
them at the next open): close below the line x 0.99, or, once the best price since entry is 20% above the fill, a
close below sma_150. Max hold 126 sessions. `engine_trail = False`: the card's line exit runs alone.

History (deviation, registered): the card needs every monthly high since the first bar, but `signals()` sees only the
replay's 300 most recent sessions (research.replay.SIGNAL_LOOKBACK_SESSIONS) and a longer `warmup_calendar_days`
would not change that. So the line is built in two parts: monthly highs from the daily highs of the last 250
sessions, and, for everything older, `ath_close` on the bar before them: the highest CLOSE since the symbol's first
store bar (features.extra, folded with the store's pre-panel history on the replay and nightly paths). A peak older
than about a year is therefore drawn at its highest close, a little under Wish's intraday high; an all-time-high
column of highs in features.extra (name it in `ath_col`) would remove this. "All-time" is since the store's first bar
(card). The 250-bar split is fixed so replay, nightly and tests draw the same line from different panel lengths.

Needs `mcap_pit` (EDGAR share join) and SPY rows for `market_close`; silent without either. "+20% from entry" is
read as the highest high since entry (PositionContext.best_price); both exits wait for position facts (line and fill).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import PositionContext, Signal
from swing_engine.core.registry import register

from . import _b5
from . import _catalog1 as c1
from ._base import (
    P_MIN_MARKET_TREND,
    P_MIN_RR,
    SYMBOL,
    TREND_DOWN,
    TS,
    PanelStrategy,
    _local_day,
    entry_feature,
    entry_price,
    finite,
)

NAME = "green_line_breakout_wish"
HIST = "hist_bars"  # features.extra: bars of the symbol in the store through this row
MARKET, MARKET_MA = "market_close", "sma_50_of_market_close"  # card (F): SPY close > SPY sma_50
LINE = "green_line"  # Signal.features key the exit reads back
MONTHS_PER_YEAR = 12


def green_line(high: np.ndarray, month: np.ndarray, older_high: float, dormant_months: int) -> float | None:
    """The line from daily ``high`` with calendar ``month`` indices (last bar = signal day) and ``older_high``, the
    highest price before these bars; None when a month among the last ``dormant_months`` completed ones beat it."""
    cur = month[-1]
    old = month < cur - dormant_months
    recent = (month >= cur - dormant_months) & (month < cur)
    line = max(older_high, float(high[old].max())) if old.any() else older_high
    return None if recent.any() and float(high[recent].max()) > line else line


@register("strategy", NAME)
class GreenLineBreakoutWish(PanelStrategy):
    name = NAME
    description = "First close above an all-time high that stood for 3+ completed months; exit on a close back below."
    default_params: dict[str, Any] = {
        "dormant_months": 3,  # card (F): three complete monthly bars after the month that set the high
        "min_history_bars": 504,  # card: require >= 504 sessions of history
        "high_lookback_sessions": 250,  # engine: daily highs used for monthly highs; older history from ath_col
        "ath_col": "ath_close",  # engine: highest close since the first store bar (no all-time high-of-highs column)
        "line_slack": 0.01,  # card (F): exit on a close below the green line x 0.99
        "stop_pct": 0.15,  # card: catastrophe stop entry x 0.85
        "trail_arm_pct": 0.20,  # card (F): after +20% from entry ...
        "trail_ma": "sma_150",  # ... exit on a close below the 150-day SMA (30-week average)
        "max_hold_days": 126,  # card: max hold 126 sessions
        P_MIN_MARKET_TREND: TREND_DOWN,  # card: the gate is SPY > sma_50 (extras above), not the regime state
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["prev_close"]
    extra_features = [_b5.MED_DV, HIST, MARKET, MARKET_MA, "ath_close", "sma_150"]
    prior_columns: list[str] = []
    engine_trail = False  # the card's close-below-the-line exit and 150-day trail run alone

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(params)
        self.ath_col, self.trail_ma = str(self.params["ath_col"]), str(self.params["trail_ma"])
        self.extra_features = [_b5.MED_DV, HIST, MARKET, MARKET_MA, self.ath_col, self.trail_ma]  # param-dependent

    def should_exit(self, row: pd.Series, bars_held: int, position: PositionContext | None = None) -> bool:
        close = row.get("close")
        if not finite(close) or position is None:
            return False
        line = entry_feature(position, LINE)
        if line is not None and float(close) < line * (1.0 - float(self.params["line_slack"])):
            return True
        entry, best, ma = entry_price(position), position.best_price, row.get(self.trail_ma)
        if entry is None or not (finite(best) and finite(ma)):
            return False
        return float(best) >= entry * (1.0 + float(self.params["trail_arm_pct"])) and float(close) < float(ma)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime) or _b5.MCAP not in panel.columns:
            return []
        p = self.params
        view = c1.view(self, panel, as_of, [_b5.MCAP])
        cur = view.current
        if cur.empty:
            return []
        keep = (_b5.smallmid(cur) & (cur[HIST] >= float(p["min_history_bars"])) & (cur[MARKET] > cur[MARKET_MA])
                & (cur["close"] > cur["prev_close"]))
        if not keep.any():
            return []
        day = _local_day(view.frame[TS])
        months = (day.dt.year * MONTHS_PER_YEAR + day.dt.month).to_numpy()
        n, dormant = int(p["high_lookback_sessions"]), int(p["dormant_months"])
        out: list[Signal] = []
        for _, row in cur.loc[keep].iterrows():
            sym = str(row[SYMBOL])
            w = view.window(sym, ["high", "close", self.ath_col])
            month = months[view.positions[sym]]
            if len(month) < n + 1 or month[-n - 1] >= month[-1] - dormant or not finite(w[self.ath_col][-n - 1]):
                continue  # too little panel history to draw the line
            line = green_line(w["high"][-n:], month[-n:], float(w[self.ath_col][-n - 1]), dormant)
            close = float(row["close"])
            if line is None or not (close > line and w["close"][-2] <= line):
                continue
            sig = self.build_signal(
                row, as_of, entry=close, stop=close * (1.0 - float(p["stop_pct"])), target=None,
                score=close / line - 1.0,  # engine choice (the card ranks nothing): distance through the line
                features={LINE: line, HIST: row[HIST], "max_hold_days": p["max_hold_days"]},
                notes=f"close {close:.2f} above the green line {line:.2f} (dormant {dormant}+ completed months)",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(cur), len(out))
        return out
