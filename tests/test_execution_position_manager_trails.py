"""execution.position_manager strategy trail hook + engine-trail opt-out (dd99dbe). No network."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from swing_engine.core.models import Position, Side
from swing_engine.execution.position_manager import (
    ExitReason,
    _Held,
    _trail_stop,
    engine_trail_enabled,
    review_positions,
    strategy_trail_level,
)
from tests.test_execution_position_manager import (
    AS_OF,
    ENTRY,
    SESSIONS,
    HoldOnly,
    kinds,
    make_settings,
    panel_for,
    sim_with_position,
)

NAN = float("nan")


class Trailing(HoldOnly):
    """Trail stop read from the panel row's ``st`` column."""

    name = "trailing"
    engine_trail = True

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        self.params = {"max_hold_days": 50, **(params or {})}

    def trail_stop(self, row: pd.Series) -> float | None:
        return row["st"]


class NoEngine(Trailing):
    engine_trail = False


class Broken(Trailing):
    def trail_stop(self, row: pd.Series) -> float | None:
        raise KeyError("supertrend")


def review(tmp_path: Path, strategy: Any, closes: list[float], st: list[float], stop_now: float | None = None):
    broker = sim_with_position(SESSIONS[-len(closes)], strategy=strategy.name)
    if stop_now is not None:
        broker.positions()[0].stop = stop_now
    panel = panel_for("ACME", closes, st=st)
    return review_positions(make_settings(tmp_path), broker, panel, AS_OF, {strategy.name: strategy})


# ----------------------------------------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------------------------------------
def test_engine_trail_enabled_params_over_attr() -> None:
    assert engine_trail_enabled(None) is True
    assert engine_trail_enabled(Trailing()) is True
    assert engine_trail_enabled(NoEngine()) is False
    assert engine_trail_enabled(NoEngine({"engine_trail": True})) is True
    assert engine_trail_enabled(Trailing({"engine_trail": False})) is False
    assert engine_trail_enabled(NoEngine({"engine_trail": None})) is False  # None defers to the attribute


@pytest.mark.parametrize(("value", "expected"), [(98.5, 98.5), ("97", 97.0), (None, None), (NAN, None),
                                                 (np.inf, None), (0.0, None), (-1.0, None), ("x", None)])
def test_strategy_trail_level_sanitises(value: Any, expected: float | None) -> None:
    s = Trailing()
    assert strategy_trail_level(s, pd.Series({"st": value})) == expected


def test_strategy_trail_level_without_hook_or_broken_hook() -> None:
    assert strategy_trail_level(HoldOnly(), pd.Series({"st": 1.0})) is None
    assert strategy_trail_level(Broken(), pd.Series({"st": 1.0})) is None


# ----------------------------------------------------------------------------------------------------------
# long, through review_positions (ENTRY 100, STOP 95, 1R = 5)
# ----------------------------------------------------------------------------------------------------------
def test_strategy_trail_below_one_r_and_rounded(tmp_path: Path) -> None:
    actions = review(tmp_path, Trailing(), [101.0, 103.0], [NAN, 98.456])  # +0.6R: no engine candidate
    assert kinds(actions) == [("replace_stop", "strategy_trail")]
    assert actions[0].new_stop == 98.46 and "trailing trail" in actions[0].detail


@pytest.mark.parametrize(("level", "reason", "stop"), [(98.0, "breakeven", ENTRY), (102.0, "strategy_trail", 102.0)])
def test_tightest_candidate_wins(tmp_path: Path, level: float, reason: str, stop: float) -> None:
    actions = review(tmp_path, Trailing(), [101.0, 106.0], [NAN, level])  # +1.2R: breakeven candidate 100
    assert kinds(actions) == [("replace_stop", reason)] and actions[0].new_stop == stop


def test_engine_trail_opt_out_keeps_strategy_trail(tmp_path: Path) -> None:
    assert review(tmp_path, NoEngine(), [101.0, 106.0], [NAN, NAN]) == []  # breakeven suppressed
    actions = review(tmp_path, NoEngine(), [101.0, 106.0], [NAN, 98.0])
    assert kinds(actions) == [("replace_stop", "strategy_trail")] and actions[0].new_stop == 98.0
    actions = review(tmp_path, NoEngine({"engine_trail": True}), [101.0, 106.0], [NAN, 98.0])  # param wins
    assert kinds(actions) == [("replace_stop", "breakeven")] and actions[0].new_stop == ENTRY


def test_strategy_trail_never_loosens(tmp_path: Path) -> None:
    # NoEngine: without a ledger the moved stop also becomes the R basis, which would wake the engine overlay
    assert review(tmp_path, NoEngine(), [101.0, 103.0], [NAN, 98.0], stop_now=99.0) == []
    assert review(tmp_path, NoEngine(), [101.0, 103.0], [NAN, 99.0], stop_now=99.0) == []  # no-op


def test_strategy_trail_never_through_close(tmp_path: Path) -> None:
    assert review(tmp_path, Trailing(), [101.0, 103.0], [NAN, 103.0]) == []
    assert review(tmp_path, Trailing(), [101.0, 103.0], [NAN, 104.0]) == []


def test_through_close_strategy_level_does_not_suppress_engine_candidate(tmp_path: Path) -> None:
    actions = review(tmp_path, Trailing(), [101.0, 106.0], [NAN, 107.0])
    assert kinds(actions) == [("replace_stop", "breakeven")] and actions[0].new_stop == ENTRY


def test_broken_hook_is_ignored(tmp_path: Path) -> None:
    actions = review(tmp_path, Broken(), [101.0, 106.0], [NAN, 98.0])
    assert kinds(actions) == [("replace_stop", "breakeven")]
    assert review(tmp_path, Broken(), [101.0, 103.0], [NAN, 98.0]) == []


# ----------------------------------------------------------------------------------------------------------
# short, direct (ENTRY 100, initial stop 105, 1R = 5)
# ----------------------------------------------------------------------------------------------------------
def short_trail(closes: list[float], level: float, current: float = 105.0, strategy: Any = None):
    held = _Held(
        position=Position(symbol="ACME", qty=100, avg_entry=ENTRY, side=Side.SHORT),
        strategy="trailing", initial_stop=105.0, current_stop=current,
    )
    frame = panel_for("ACME", closes, st=[NAN] * (len(closes) - 1) + [level])
    return _trail_stop(held, frame, make_settings(Path("/nonexistent")), strategy or Trailing())


def test_short_strategy_trail_and_tightest_wins() -> None:
    hit = short_trail([99.0, 97.0], 101.0)  # +0.6R: strategy only
    assert hit is not None and hit[:2] == (101.0, ExitReason.STRATEGY_TRAIL)
    hit = short_trail([99.0, 94.0], 99.0)  # +1.2R: breakeven 100 vs 99 -> 99 is tighter for a short
    assert hit is not None and hit[:2] == (99.0, ExitReason.STRATEGY_TRAIL)
    hit = short_trail([99.0, 94.0], 101.0)
    assert hit is not None and hit[:2] == (ENTRY, ExitReason.BREAKEVEN)


def test_short_never_loosens_or_crosses_close() -> None:
    assert short_trail([99.0, 97.0], 101.0, current=100.5) is None
    assert short_trail([99.0, 97.0], 97.0) is None
    assert short_trail([99.0, 97.0], 96.0) is None
    hit = short_trail([99.0, 94.0], 93.0)  # through the close: the engine breakeven still applies
    assert hit is not None and hit[:2] == (ENTRY, ExitReason.BREAKEVEN)


def test_short_engine_opt_out() -> None:
    assert short_trail([99.0, 94.0], NAN, strategy=NoEngine()) is None
    hit = short_trail([99.0, 94.0], 101.0, strategy=NoEngine())
    assert hit is not None and hit[:2] == (101.0, ExitReason.STRATEGY_TRAIL)
