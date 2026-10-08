"""Short-term momentum in high-turnover stocks (long), docs/strategies/high_turnover_short_term_momentum.md (E09,
Medhat-Schmeling RFS 2022).

Month-end double sort (last NYSE session, `rebalance_day` -1): long the names in the top `turnover_rank_min` of 21-session
share turnover AND the top `ret_rank_min` of the prior-month return (`ret_21d`), ranked across the symbols scanned on
that session; hold 21 sessions (card replay). Turnover = mean of the panel's `turnover` column (daily volume / point-in-
time shares outstanding from `data.fundamentals.edgar_panel_features`) when the panel carries it.

Approximation: the nightly/replay panels do not join EDGAR shares outstanding today, so without a `turnover` column the
module ranks RELATIVE turnover, mean volume 21 / mean volume 252 (`turnover_source` feature = 0). The card warns that
relative and absolute turnover are different signals; replays must be split by `turnover_source`. The academic sort is
long-short and value-weighted; this is the long leg only, equal risk, with an engine ATR stop (none in the paper).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from . import _catalog1 as c1
from ._base import P_MIN_MARKET_TREND, P_MIN_RR, SYMBOL, TREND_DOWN, PanelStrategy, finite
from ._catalog3 import month_offsets, session_day

NAME = "high_turnover_short_term_momentum"
TURNOVER = "turnover"  # data/fundamentals.py FEATURE_COLUMNS (volume / shares_outstanding)
VOL_SHORT, VOL_LONG = "sma_21_of_volume", "sma_252_of_volume"


@register("strategy", NAME)
class HighTurnoverShortTermMomentum(PanelStrategy):
    name = NAME
    description = "Month end: top-decile 21-day turnover AND top-decile 21-day return; hold 21 sessions."
    default_params: dict[str, Any] = {
        "rebalance_day": -1,  # card: monthly sort at the month end
        "turnover_window": 21,  # card: turnover over the prior month (21 sessions)
        "turnover_rank_min": 0.90,  # card: highest-turnover decile
        "ret_rank_min": 0.90,  # card: prior-month winners (top decile, `stmom_long`)
        "stop_atr_mult": 2.0,  # engine choice: the paper has no stop
        "max_hold_days": 21,  # card: max_hold_days 21
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: min reward:risk n/a
    }
    features_required = ["atr_14", "ret_21d"]
    extra_features = [VOL_SHORT, VOL_LONG]

    def _turnover(self, panel: pd.DataFrame, rows: pd.DataFrame, as_of: date) -> tuple[pd.Series, float]:
        if TURNOVER not in panel.columns:
            return rows[VOL_SHORT] / rows[VOL_LONG].where(rows[VOL_LONG] > 0), 0.0
        n = int(self.params["turnover_window"])
        view = c1.view(self, panel, as_of, [TURNOVER])
        vals = []
        for sym in rows[SYMBOL]:
            w = view.window(str(sym), [TURNOVER])[TURNOVER][-n:]
            vals.append(float(w.mean()) if len(w) == n and np.isfinite(w).all() else np.nan)
        return pd.Series(vals, index=rows.index), 1.0

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if panel.empty or not self.market_ok(regime):
            return []
        rows = c1.rows(self, panel, as_of)
        day = session_day(rows)
        if day is None or int(self.params["rebalance_day"]) not in month_offsets(day):
            return []
        turnover, source = self._turnover(panel, rows, as_of)
        t_rank, r_rank = turnover.rank(pct=True), rows["ret_21d"].rank(pct=True)
        keep = (t_rank >= float(self.params["turnover_rank_min"])) & (r_rank >= float(self.params["ret_rank_min"]))
        mult = float(self.params["stop_atr_mult"])
        out: list[Signal] = []
        for i, row in rows.loc[keep].iterrows():
            atr, close = row["atr_14"], float(row["close"])
            if not finite(atr):
                continue
            sig = self.build_signal(
                row, as_of, entry=close, stop=close - mult * float(atr), target=None,
                score=float(t_rank[i] + r_rank[i]),
                features={"turnover_rank": t_rank[i], "ret_21d_rank": r_rank[i], "ret_21d": row["ret_21d"],
                          "turnover_source": source, "max_hold_days": self.params["max_hold_days"]},
                notes=f"STMOM month end: turnover rank {t_rank[i]:.2f} ({'EDGAR' if source else 'relative proxy'}), "
                f"21d return rank {r_rank[i]:.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
