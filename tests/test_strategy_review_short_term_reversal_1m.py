"""short_term_reversal_1m review: trend_state >= 0 belongs to the screen, before the rev_21d ranking."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from swing_engine.core import registry
from swing_engine.features.extra import ensure_extra
from swing_engine.features.panel import build_panel
from tests.fixtures.strategies.panel import bars_from_closes

AS_OF = date(2025, 2, 21)  # a Friday


def test_downtrend_loser_does_not_take_a_rank_slot():
    strat = registry.get("strategy", "short_term_reversal_1m")(None)
    n, start = 300, pd.bdate_range(end=AS_OF, periods=300)[0].strftime("%Y-%m-%d")
    t = np.arange(n)
    frames = [bars_from_closes(f"S{i}", 50 * np.exp((0.0005 + 0.0002 * i) * t), start=start) for i in range(34)]
    loser = np.where(t < n - 21, 0.01 * t, 0.01 * (n - 21) - 0.008 * (t - (n - 21)))
    frames.append(bars_from_closes("LOSER", 50 * np.exp(loser), start=start))
    panel = ensure_extra(build_panel(pd.concat(frames, ignore_index=True), None), strat.extra_features)
    assert {s.symbol for s in strat.signals(panel, AS_OF)} >= {"LOSER"}

    on_day = (panel["symbol"] == "LOSER") & (panel["ts"].dt.date == AS_OF)
    panel.loc[on_day, "trend_state"] = -1
    syms = {s.symbol for s in strat.signals(panel, AS_OF)}
    assert "LOSER" not in syms
    assert syms == {"S24", "S25"}  # ranked within the trend-filtered screen, S25 moves into the top 10%
