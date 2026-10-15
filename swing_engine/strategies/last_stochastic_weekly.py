"""George Lane "Last" stochastic, weekly (long), docs/strategies/last_stochastic_weekly.md (catalog P40, StockCharts
ChartSchool).

Weekly bars (completed W-FRI weeks, `features.extra` `wk_*`): the 39-week slow stochastic %K (3-week smoothing,
ChartSchool's preference; catalog "(39,1)" = `smooth` 1) crosses above 50 and the weekly close is above the prior
week's close. Acts on the session a week completes (`wk_fresh`), entering at the next open. No published stop: lowest
low of the last 10 sessions (~2 weeks) - 0.1 x atr_14, but no wider than 2.5 x atr_14 (card engine choice). Exit on
the weekly sell (%K crosses below 50 and the weekly close is below the prior week's) or 180 sessions. Weekly holds
would be cut by the engine's daily breakeven / N-day-low overlay, so it is off (`engine_trail = False`). The optional
OBV confirmation is not built.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, TREND_DOWN, PanelStrategy, finite

NAME = "last_stochastic_weekly"


def weekly_names(params: dict[str, Any]) -> list[str]:
    k = f"wk_stoch_{int(params['stoch_weeks'])}_{int(params['smooth'])}"
    return [k, f"prev_{k}", "wk_close", "wk_close_max_1", "wk_fresh", f"low_{int(params['stop_lookback'])}"]


@register("strategy", NAME)
class LastStochasticWeekly(PanelStrategy):
    name = NAME
    description = "Weekly slow %K(39,3) crosses above 50 with a higher weekly close; weekly sell signal exit."
    default_params: dict[str, Any] = {
        "stoch_weeks": 39,  # card: 39-week stochastic
        "smooth": 3,  # card: ChartSchool prefers 3-week smoothing (1 = catalog fast version)
        "level": 50.0,  # card: cross level 50 (one level for the universe)
        "stop_lookback": 10,  # card: lowest weekly low of the last 2 weeks (~10 sessions) ...
        "stop_atr_buffer": 0.1,  # ... minus 0.1 x atr_14
        "max_stop_atr": 2.5,  # card: capped at 2.5 x atr_14
        "max_hold_days": 180,  # card
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 0.0,  # card: no fixed target
    }
    engine_trail = False  # weekly system: the daily breakeven / N-day-low overlay would cut it
    features_required = ["atr_14"]
    extra_features = weekly_names(default_params)

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        self.extra_features = weekly_names(self.params)

    def _weekly(self, row: pd.Series) -> tuple[float, float, float, float] | None:
        """(%K, prior week %K, weekly close, prior weekly close) on the row a week completes, else None."""
        k, pk, wc, pwc, fresh = (row.get(c) for c in self.extra_features[:5])
        if not (finite(fresh) and float(fresh) == 1.0 and all(finite(x) for x in (k, pk, wc, pwc))):
            return None
        return float(k), float(pk), float(wc), float(pwc)

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        if bars_held >= int(self.params["max_hold_days"]):
            return True
        wk, level = self._weekly(row), float(self.params["level"])
        return wk is not None and wk[1] >= level > wk[0] and wk[2] < wk[3]

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        p = self.params
        level, low_col = float(p["level"]), self.extra_features[5]
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        out: list[Signal] = []
        for _, row in rows.iterrows():
            wk, atr, low_n = self._weekly(row), row["atr_14"], row[low_col]
            if wk is None or not (finite(atr) and finite(low_n)):
                continue
            k, pk, wc, pwc = wk
            if not (pk <= level < k and wc > pwc):
                continue
            close = float(row["close"])
            stop = max(float(low_n) - float(p["stop_atr_buffer"]) * float(atr), close - float(p["max_stop_atr"]) * float(atr))
            sig = self.build_signal(
                row,
                as_of,
                entry=close,
                stop=stop,
                target=None,
                score=k - level,
                features={"wk_stoch": k, "prev_wk_stoch": pk, "wk_close": wc, "atr_14": atr,
                          "max_hold_days": p["max_hold_days"]},
                notes=f"weekly %K {pk:.0f} -> {k:.0f} through {level:g}, weekly close {wc:.2f} > {pwc:.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
