"""Weinstein Stage 2 breakout, trader method (long), docs/strategies/weinstein_stage2_breakout.md (catalog C28).

Evaluated only on the last NYSE session of a week (Friday close, or Thursday before a Friday holiday; `data.calendar`),
on weekly bars resampled in the strategy from the symbol's daily history (weeks ending Friday, all complete because
the as-of session closes its week): weekly close above the top of the prior `base_weeks`-week base, base depth <=
`base_max_depth`, close above a 30-week SMA whose 4-week slope is >= 0, breakout-week volume >= 2x the prior 4-week
average, Mansfield RS > 0 (daily `mansfield_rs`, 252-session ~ 52 weeks, against SPY). Entry next open (no stop-entry
on the Friday close). Stop = base low, never wider than 15% (card). Exit on a daily close below the 150-day SMA
(daily equivalent of the 30-week MA, card) or 180 sessions; no target. Not modelled: overhead-resistance check, group
strength (no sector data), the trail under weekly correction lows.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.features.patterns2 import local_day

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, TS, PanelStrategy, finite
from ._catalog3 import WEEK, is_week_end, session_day

NAME = "weinstein_stage2_breakout"
ARRAYS = ("high", "low", "close", "volume")


@register("strategy", NAME)
class WeinsteinStage2Breakout(PanelStrategy):
    name = NAME
    description = "Weekly close over a Stage 1 base above a flat/rising 30-week MA on 2x volume with Mansfield RS > 0."
    default_params: dict[str, Any] = {
        "ma_weeks": 30,  # card: 30-week SMA (definition of the method, do not tune)
        "ma_slope_weeks": 4,  # card: wk_sma_30 / wk_sma_30.shift(4) - 1 >= 0
        "vol_mult_4w": 2.0,  # card: breakout-week volume >= 2x the prior 4-week average
        "base_weeks": 12,  # card: base length unpublished, try 8-26 (12 pre-registered here)
        "base_max_depth": 0.30,  # card: unverified, try 0.25-0.35
        "rs_col": "mansfield_rs",  # card: Mansfield RS above its zero line
        "rs_min": 0.0,
        "max_stop_pct": 0.15,  # card: stop capped at 15% (param, not from source)
        "exit_ma": "sma_150",  # card: daily alternative to the 30-week MA
        "max_hold_days": 180,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,  # router: healthy_uptrend only
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required: list[str] = []
    extra_features = ["mansfield_rs", "sma_150"]
    engine_trail = False  # weeks-to-months hold; the engine's 10-day-low trail would cut it (card)

    def required_features(self) -> list[str]:
        return [str(self.params["rs_col"]), str(self.params["exit_ma"])]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        ma = row.get(str(self.params["exit_ma"]))
        return finite(ma) and float(row["close"]) < float(ma)

    def _weekly(self, view: Any, sym: str) -> pd.DataFrame:
        pos = view.positions[sym]
        w = view.window(sym, ARRAYS)
        week = local_day(view.frame[TS].iloc[pos]).dt.to_period(WEEK).to_numpy()
        daily = pd.DataFrame(w).assign(week=week)
        return daily.groupby("week", sort=True).agg(high=("high", "max"), low=("low", "min"), close=("close", "last"),
                                                    volume=("volume", "sum"))

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        p = self.params
        rs_col, ma_col = str(p["rs_col"]), str(p["exit_ma"])
        view = c1.view(self, panel, as_of, [])
        cur = view.current
        if cur.empty or not is_week_end(session_day(cur)):
            return []
        cur = cur.loc[(cur[rs_col] > float(p["rs_min"])) & (cur["close"] > cur[ma_col])]
        n_ma, n_base = int(p["ma_weeks"]), int(p["base_weeks"])
        out: list[Signal] = []
        for _, row in cur.iterrows():
            wk = self._weekly(view, str(row[SYMBOL]))
            if len(wk) < max(n_ma + int(p["ma_slope_weeks"]), n_base + 1):
                continue
            sma = wk["close"].rolling(n_ma).mean()
            vol_avg = wk["volume"].shift(1).rolling(4).mean()
            top, low = wk["high"].shift(1).rolling(n_base).max().iloc[-1], wk["low"].shift(1).rolling(n_base).min().iloc[-1]
            close, ma_now, ma_then = wk["close"].iloc[-1], sma.iloc[-1], sma.iloc[-1 - int(p["ma_slope_weeks"])]
            ok = (close > top and (top - low) / top <= float(p["base_max_depth"]) and close > ma_now
                  and ma_now >= ma_then and wk["volume"].iloc[-1] >= float(p["vol_mult_4w"]) * vol_avg.iloc[-1])
            if not ok:
                continue
            stop = max(float(low), float(close) * (1.0 - float(p["max_stop_pct"])))
            sig = self.build_signal(
                row, as_of, entry=float(close), stop=stop, target=None, score=float(row[rs_col]),
                features={"wk_base_top": top, "wk_base_low": low, "wk_sma_30": ma_now,
                          "wk_vol_ratio_4": wk["volume"].iloc[-1] / vol_avg.iloc[-1], rs_col: row[rs_col],
                          "max_hold_days": p["max_hold_days"]},
                notes=f"Stage 2 breakout: weekly close {close:.2f} > {n_base}-week base {top:.2f}, 30-week MA rising",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(cur), len(out))
        return out
