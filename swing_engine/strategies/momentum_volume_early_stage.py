"""Early-stage momentum: low-turnover winners (Lee & Swaminathan, JF 2000): docs/strategies/momentum_volume_early_stage.md,
pre-registered in docs/preregistration/2026-10-10-two-picks.md.

On the last NYSE session of each month (`month_end`), over the symbols scanned that session: formation return =
close[t-5] / close[t-131] - 1 (J = 6 months = 126 sessions, ending one week = 5 sessions before the signal, the
paper's one-week lag) and formation volume = mean daily `turnover` (volume / point-in-time EDGAR shares outstanding,
`data.fundamentals.join_edgar`) over the same 126 sessions, all 126 required. Two independent sorts: buy the
names in the top return decile (R10) AND the bottom turnover tercile (V1), the long leg of the paper's early-stage
strategy (its short leg, high-volume losers, is not traded). Next open, hold K = 6 months (`max_hold_days` 126), no
target. Stop 3 x ATR(63) (engine choice; the paper has none). `engine_trail = False`. No signals when the panel has
no `turnover` column (a panel built without `join_edgar` is silent; relative volume is never used as a proxy).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd
import structlog

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy, finite

log = structlog.get_logger(__name__)

NAME = "momentum_volume_early_stage"
TURNOVER = "turnover"  # data/fundamentals.py FEATURE_COLUMNS (volume / shares_outstanding)
MONTH_END, HIST, ATR = "month_end", "hist_bars", "atr_63"  # features.extra


@register("strategy", NAME)
class MomentumVolumeEarlyStage(PanelStrategy):
    name = NAME
    description = "Month end: top-decile 6-month return AND bottom-tercile 6-month turnover; hold 6 months."
    default_params: dict[str, Any] = {
        "formation_days": 126,  # paper: J = 6 months
        "skip_days": 5,  # paper: one-week lag between formation and holding
        "winner_fraction": 0.10,  # paper: R10, top return decile
        "low_volume_fraction": 1.0 / 3.0,  # paper: V1, bottom turnover tercile (independent sort)
        "min_history_bars": 504,  # paper: at least two years of data before formation
        "stop_atr_mult": 3.0,  # engine choice (no stop in the paper), as composite_cost_aware_rank
        "max_hold_days": 126,  # paper: K = 6 months
        P_MIN_MARKET_TREND: TREND_DOWN,  # paper: no market filter
        P_MIN_RR: 0.0,  # no target
    }
    extra_features = [MONTH_END, HIST, ATR]
    prior_columns: list[str] = []
    engine_trail = False  # hold the K months, as the paper does

    def _formation(self, panel: pd.DataFrame, rows: pd.DataFrame, as_of: date) -> tuple[pd.Series, pd.Series]:
        j, skip = int(self.params["formation_days"]), int(self.params["skip_days"])
        view = c1.view(self, panel, as_of, [TURNOVER])
        ret, turn = [], []
        for sym in rows[SYMBOL]:
            w = view.window(str(sym), ["close", TURNOVER])
            c, t = w["close"], w[TURNOVER]
            if len(c) < j + skip + 1:
                ret.append(np.nan)
                turn.append(np.nan)
                continue
            end = len(c) - 1 - skip  # last formation bar
            base = c[end - j]
            ret.append(c[end] / base - 1.0 if base > 0 else np.nan)
            tw = t[end - j + 1:end + 1]
            turn.append(float(tw.mean()) if np.isfinite(tw).all() else np.nan)
        return pd.Series(ret, index=rows.index), pd.Series(turn, index=rows.index)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if TURNOVER not in panel.columns:
            log.debug("strategy.skip", strategy=self.name, reason="panel has no turnover column")
            return []
        if panel.empty or not self.market_ok(regime):
            return []
        p = self.params
        rows = c1.rows(self, panel, as_of)
        if rows.empty or not (rows[MONTH_END] == 1.0).any():
            return []
        ret, turn = self._formation(panel, rows, as_of)
        ok = ret.notna() & turn.notna() & (rows[HIST] >= float(p["min_history_bars"]))
        r_rank, t_rank = ret[ok].rank(pct=True), turn[ok].rank(pct=True)
        fire = (r_rank > 1.0 - float(p["winner_fraction"])) & (t_rank <= float(p["low_volume_fraction"]))
        out: list[Signal] = []
        for idx in fire.index[fire]:
            row = rows.loc[idx]
            close, atr = float(row["close"]), row[ATR]
            if not finite(atr):
                continue
            sig = self.build_signal(
                row, as_of, entry=close, stop=close - float(p["stop_atr_mult"]) * float(atr), target=None,
                score=float(r_rank[idx] - t_rank[idx]),
                features={"formation_ret": ret[idx], "formation_turnover": turn[idx], "ret_rank": r_rank[idx],
                          "turnover_rank": t_rank[idx]},
                notes=f"6-month return rank {r_rank[idx]:.2f}, turnover rank {t_rank[idx]:.2f} (early stage)",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
