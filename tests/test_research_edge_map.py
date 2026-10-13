"""research.edge_map: liquidity bands, the both-windows candidate rule and the chance count."""
from __future__ import annotations

import pandas as pd
import pytest

from swing_engine.research import edge_map as E
from swing_engine.research import leaderboard as lb
from tests.test_research_leaderboard import WINDOWS, frame


def test_cells_are_named_by_band_and_candidates_need_both_windows() -> None:
    def cell(strategy: str, start: str, edge: float, dv: float, seed: int) -> pd.DataFrame:
        return frame(strategy, start, edge, seed=seed).assign(dollar_volume=dv)

    shadow = pd.concat([cell("good", "2024-01-02", 0.6, 1e6, 0), cell("good", "2020-01-02", 0.6, 1e6, 1),
                        cell("good", "2024-01-02", 0.0, 5e8, 2), cell("good", "2020-01-02", 0.0, 5e8, 3),
                        cell("once", "2024-01-02", 0.6, 3e7, 4), cell("once", "2020-01-02", -0.6, 3e7, 5),
                        cell("good", "2024-01-02", 0.6, float("nan"), 6)])
    banded = E.bucketed(shadow)
    assert set(banded["strategy"]) == {"good@dv<5M", "good@dv>100M", "once@dv20-100M"}  # no dollar volume: left out
    board, _ = lb.leaderboard(banded, WINDOWS)
    rows, eligible = E.candidates(board, E.T_STRONG)
    assert set(rows["strategy"]) == {"good@dv<5M"} and eligible == 9  # 3 cells x 3 horizons had enough signals
    assert E.candidates(board, E.T_STRONG, min_signals=1000)[1] == 0
    text = E.render(board, E.pooled_by_band(banded), 123)
    assert "| good | dv<5M |" in text and "By luck alone about" in text and "once" not in text.split("## Strong")[1]


def test_chance_count_is_the_product_of_the_tail_probabilities() -> None:
    assert E.chance(1000, 1.0) == pytest.approx(1000 * 0.158655 ** 2, rel=1e-4)
    assert E.chance(1000, 2.0) == pytest.approx(0.5176, rel=1e-3)
