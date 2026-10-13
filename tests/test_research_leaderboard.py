"""research.leaderboard: net edge, block t-stats, haircut and survivors."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from swing_engine.research import leaderboard as lb
from swing_engine.research.cards import Window

WINDOWS = (Window(date(2024, 1, 1), date(2025, 12, 31), "a"), Window(date(2020, 1, 1), date(2021, 12, 31), "b"))


def frame(strategy: str, start: str, edge: float, n: int = 400, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    days = pd.bdate_range(start, periods=n)
    r = edge + rng.normal(0, 1.0, n)
    rows = {"strategy": strategy, "symbol": "X", "as_of": days.date, "entry": 100.0, "stop": 95.0}
    for h in (5, 10, 20):
        rows |= {f"hit_{h}d": "time_exit", f"result_r_{h}d": r}
    return pd.DataFrame(rows)


def test_strong_edge_survives_both_windows_and_noise_does_not() -> None:
    shadow = pd.concat([frame("good", "2024-01-02", 0.8), frame("good", "2020-01-02", 0.8, seed=1),
                        frame("noise", "2024-01-02", 0.0, seed=2), frame("noise", "2020-01-02", 0.0, seed=3),
                        frame("one_window", "2024-01-02", 0.8, seed=4), frame("one_window", "2020-01-02", -0.5, seed=5)])
    board, n_trials = lb.leaderboard(shadow, WINDOWS, logged_trials=10)
    assert n_trials == 3 * 3 * 2
    surv = set(lb.survivors(board)["strategy"])
    assert surv == {"good"}
    # net subtracts 2 x 10bp x 100 / 5 = 0.04R per signal
    row = board.loc[(board.strategy == "good") & (board.window == 2024) & (board.horizon == 5)].iloc[0]
    assert abs((row.gross_r - row.net_r) - 0.04) < 1e-9
    text = lb.render(board, n_trials, WINDOWS)
    assert "**good**" in text and "| noise |" in text


def test_no_survivors_is_said_plainly() -> None:
    board, n = lb.leaderboard(frame("noise", "2024-01-02", 0.0), WINDOWS[:1])
    assert "None." in lb.render(board, n, WINDOWS[:1])


def test_board_looks_are_logged_once(tmp_path, monkeypatch) -> None:
    from swing_engine.research import trials

    path = tmp_path / "trials.jsonl"
    monkeypatch.setattr(lb, "iter_trials", lambda: trials.iter_trials(path))
    monkeypatch.setattr(lb, "log_trial", lambda *a, **k: trials.log_trial(*a, path=path, **k))
    board, _ = lb.leaderboard(frame("noise", "2024-01-02", 0.0), WINDOWS[:1])
    assert lb.log_board_trials(board) == 3 and lb.log_board_trials(board) == 0
    assert trials.trial_count(None, path) == 3


def test_liquid_variant_filters_and_renames() -> None:
    shadow = frame("s", "2024-01-02", 0.1).assign(dollar_volume=[1e6, 6e7] * 200)
    out = lb.liquid_variant(shadow, 5e7)
    assert len(out) == 200 and set(out["strategy"]) == {"s@liq50"}
