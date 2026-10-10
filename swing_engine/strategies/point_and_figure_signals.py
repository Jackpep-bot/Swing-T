"""Point & Figure double / triple top buy (long): docs/strategies/point_and_figure_signals.md.

Columns from features.extra (`pf_*`: high/low method, 3-box reversal, traditional box table at each column start).
Signal on bar t: the current X column's top exceeds the previous X column's top for the first time in this column
(double top buy; `triple: True` also needs the two prior X tops equal). Entry next open; stop = the double-bottom
sell level (previous O column low - one box); target = vertical count (column low + boxes in the column x box x 3);
rule exit on a double-bottom sell (the current O column breaks the previous O low). Catapults, spread triple tops
and horizontal counts are not modelled.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from swing_engine.core.models import Signal
from swing_engine.core.registry import register

from ._base import P_MIN_MARKET_TREND, P_MIN_RR, P_MIN_TREND, TREND_DOWN, PanelStrategy, finite

NAME = "point_and_figure_signals"
DIR, TOP, BOT, BOX = "pf_dir", "pf_top", "pf_bot", "pf_box"
PX1, PX2, PO = "pf_prev_x_top", "pf_prev_x_top2", "pf_prev_o_bot"
X_COL, O_COL = 1.0, -1.0


@register("strategy", NAME)
class PointAndFigure(PanelStrategy):
    name = NAME
    description = "P&F double top buy (3-box reversal); stop at the double-bottom sell level, vertical-count target."
    default_params: dict[str, Any] = {
        "triple": False,  # card variant: triple top (two prior equal X tops)
        "reversal": 3,  # card: vertical count uses the 3-box reversal (features.extra PF_REVERSAL)
        "max_hold_days": 60,  # card
        P_MIN_TREND: TREND_DOWN,  # card: trend_state is an optional gate
        P_MIN_MARKET_TREND: TREND_DOWN,
        P_MIN_RR: 1.5,  # card
    }
    features_required = ["trend_state"]
    extra_features = [DIR, TOP, BOT, BOX, PX1, PX2, PO]
    prior_columns = [DIR, TOP, PX1]

    def should_exit(self, row: pd.Series, bars_held: int) -> bool:
        bot, po = row.get(BOT), row.get(PO)
        dbs = row.get(DIR) == O_COL and finite(bot) and finite(po) and bot < po
        return bool(bars_held >= int(self.params["max_hold_days"]) or dbs)

    def signals(self, panel: pd.DataFrame, as_of: date, regime: dict[str, Any] | None = None) -> list[Signal]:
        if not self.market_ok(regime):
            return []
        rows = self.rows_as_of(panel, as_of, required=self.required_features())
        if rows.empty:  # rows_as_of returns the bare empty frame, without the prior_* columns
            return []
        buy = (rows[DIR] == X_COL) & (rows[TOP] > rows[PX1])
        already = (rows[f"prior_{DIR}"] == X_COL) & (rows[f"prior_{TOP}"] > rows[f"prior_{PX1}"])
        if self.params["triple"]:
            buy &= np.isclose(rows[PX1], rows[PX2])
        out: list[Signal] = []
        for _, row in rows.loc[(buy & ~already).fillna(False)].iterrows():
            if not (finite(row[PO]) and self.trend_ok(row)):
                continue
            box, bot, top = float(row[BOX]), float(row[BOT]), float(row[TOP])
            boxes = round((top - bot) / box) + 1
            target = bot + boxes * box * int(self.params["reversal"])
            sig = self.build_signal(
                row, as_of, entry=float(row["close"]), stop=float(row[PO]) - box, target=target, score=boxes,
                features={TOP: top, PX1: row[PX1], PO: row[PO], BOX: box, "column_boxes": boxes},
                notes=f"P&F {'triple' if self.params['triple'] else 'double'} top buy over {float(row[PX1]):.2f}",
            )
            if sig:
                out.append(sig)
        self.log_scan(as_of, len(rows), len(out))
        return out
