"""Katsanos BB divergence (long): docs/strategies/intermarket_divergence_katsanos.md, catalog B47 (thinkorswim
BBDivergenceStrat).

Divergence = 100 x (%b of the secondary - %b of the stock), Bollinger(20, 2) on closes (card's assumed form:
positive when the stock lags). Buy when the 3-day max divergence > 20 but the divergence is falling, the stock close
and the secondary's 3-day average are both up over 2 days, and the 20-day price correlation > -0.4; the card's
engine addition requires a 120-day correlation of daily returns >= 0.5 for the pair to be eligible. Entry next open,
stop 2 x atr_14 (engine choice; none in the original). Exits: MACD crosses below its signal while stochastic(14) >
85, a 15-day closing low while the 20-day price correlation (`corr_market_20`) < -0.4 (thinkorswim's rule), or 15
sessions.

Approximation: the engine has no symbol -> sector ETF map, so the secondary is the market proxy (`market_close`,
SPY). The divergence exit (3-day min < -20 with ROC < -3) needs the secondary's %b in the held row and is not
built; the RegressionDivergence variant (three symbols) is not built.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register
from swing_engine.features.extra import MARKET_SYMBOL
from swing_engine.features.patterns2 import as_of_view

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy, finite

NAME = "intermarket_divergence_katsanos"
MKT = "market_close"
STOCH = "stoch_k_14"
LOW_15 = "min_15_of_close"
PCT = 100.0


def pct_b(x: np.ndarray, n: int, k: float) -> float:
    """Bollinger %b of the last value of ``x`` over its last ``n`` values (population stdev, as features use)."""
    w = x[-n:]
    mid, sd = w.mean(), w.std()
    return (x[-1] - (mid - k * sd)) / (2 * k * sd) if sd > 0 else np.nan


@register("strategy", NAME)
class IntermarketDivergenceKatsanos(PanelStrategy):
    name = NAME
    description = "Stock lags SPY inside Bollinger(20): divergence > 20 and turning down, both rising, correlated pair."
    default_params: dict[str, Any] = {
        "bb_len": 20,  # card: BB length 20
        "bb_k": 2.0,
        "div_level": 20.0,  # card: 3-day max divergence > 20
        "div_lookback": 3,
        "trend_bars": 2,  # card: primary close and secondary average up over the last 2 days
        "sec_avg_bars": 3,  # card: sma(close_s, 3)
        "corr_len": 20,  # card: corr_20 > -0.4
        "corr_min": -0.4,
        "pair_corr_len": 120,  # card (engine addition): 120-day return correlation >= 0.5
        "pair_corr_min": 0.5,
        "stoch_exit": 85.0,  # card: MACD cross down while stochastic > 85
        "stop_atr_mult": 2.0,  # card: stop entry - 2 x atr_14 (engine choice)
        "max_hold_days": 15,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,  # router: healthy_uptrend / choppy at reduced size
        P_MIN_RR: 0.0,  # card: no target
    }
    features_required = ["atr_14", "macd", "macd_signal"]
    extra_features = [MKT, STOCH, LOW_15, "prev_macd", "prev_macd_signal", "corr_market_20"]

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        self.corr_col = f"corr_market_{int(self.params['corr_len'])}"
        self.extra_features = [MKT, STOCH, LOW_15, "prev_macd", "prev_macd_signal", self.corr_col]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        low, corr = row.get(LOW_15), row.get(self.corr_col)
        if (finite(low) and finite(corr) and float(row["close"]) <= float(low)
                and float(corr) < float(self.params["corr_min"])):
            return True  # thinkorswim: 15-day closing low while the pair has decoupled
        vals = [row.get(c) for c in ("macd", "macd_signal", "prev_macd", "prev_macd_signal", STOCH)]
        if not all(finite(v) for v in vals):
            return False
        m, s, pm, ps, k = (float(v) for v in vals)
        return pm >= ps and m < s and k > float(self.params["stoch_exit"])

    def _divergence(self, pc: np.ndarray, sc: np.ndarray, t: int) -> np.ndarray:
        n, k, look = int(self.params["bb_len"]), float(self.params["bb_k"]), int(self.params["div_lookback"])
        return np.array([PCT * (pct_b(sc[: j + 1], n, k) - pct_b(pc[: j + 1], n, k)) for j in range(t - look, t + 1)])

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        cols = ["close", MKT]
        view = as_of_view(panel, as_of, ["open", "high", "low", *cols, *self.required_features()])
        need = max(int(p["pair_corr_len"]) + 1, int(p["bb_len"]) + int(p["div_lookback"]))
        out: list[Signal] = []
        for _, row in view.current.iterrows():
            if str(row[SYMBOL]) == MARKET_SYMBOL:
                continue
            w = view.window(str(row[SYMBOL]), cols)
            pc, sc = w["close"], w[MKT]
            t = len(pc) - 1
            if t + 1 < need or not (np.isfinite(pc[-need:]).all() and np.isfinite(sc[-need:]).all()):
                continue
            div = self._divergence(pc, sc, t)
            if not (np.nanmax(div[1:]) > float(p["div_level"]) and div[-1] < div[-2]):
                continue
            tb, na = int(p["trend_bars"]), int(p["sec_avg_bars"])
            if not (pc[t] > pc[t - tb] and sc[t - na + 1 :].mean() > sc[t - tb - na + 1 : t - tb + 1].mean()):
                continue
            nc, npc = int(p["corr_len"]), int(p["pair_corr_len"])
            corr = float(np.corrcoef(pc[-nc:], sc[-nc:])[0, 1])
            rp, rs = np.diff(pc[-npc - 1 :]) / pc[-npc - 1 : -1], np.diff(sc[-npc - 1 :]) / sc[-npc - 1 : -1]
            pair = float(np.corrcoef(rp, rs)[0, 1])
            if not (corr > float(p["corr_min"]) and pair >= float(p["pair_corr_min"])):
                continue
            close = float(pc[t])
            sig = self.build_signal(
                row, as_of, entry=close, stop=close - float(p["stop_atr_mult"]) * float(row["atr_14"]), target=None,
                score=float(np.nanmax(div[1:])),
                features={"bb_div": div[-1], "bb_div_max3": np.nanmax(div[1:]), "corr_20": corr, "pair_corr_120": pair,
                          "max_hold_days": p["max_hold_days"]},
                notes=f"lags {MARKET_SYMBOL}: BB divergence {div[-1]:.0f} (3-day max {np.nanmax(div[1:]):.0f}) turning "
                f"down; corr20 {corr:.2f}, pair corr {pair:.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(view.current), len(out))
        return out
