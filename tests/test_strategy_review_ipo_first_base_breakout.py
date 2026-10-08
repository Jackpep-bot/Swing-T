"""Review regressions for ipo_first_base_breakout."""
from __future__ import annotations

import pandas as pd
import pytest

from swing_engine.core import registry
from swing_engine.strategies import ipo_first_base_breakout as mod
from tests.fixtures.strategies.panel import add_features, bars_from_ohlc, last_date, trend_rows

OLD = bars_from_ohlc("OLD", trend_rows(100))  # starts the panel, so later first bars are new listings
LISTED = str(OLD["ts"].iloc[70].date())


def _base_rows() -> list[list[float]]:
    """Listing day, a 20-bar first base under a 23.0 left-side high, a breakout on day 21, a higher close on day 22."""
    rows = [[20.0, 22.0, 19.5, 21.0, 5e6], [22.0, 23.0, 21.5, 22.0, 1e6]]
    rows += [[22.0, 22.5, 21.0, 22.0, 1e6]] * 19
    return [*rows, [22.5, 23.6, 22.4, 23.5, 3e6], [23.5, 24.2, 23.4, 24.0, 3e6]]


def _signals(*frames: pd.DataFrame):
    p = add_features(pd.concat([OLD, *frames], ignore_index=True))
    return registry.get("strategy", mod.NAME)().signals(p, last_date(frames[-1]))


def test_pivot_is_the_left_side_high_not_yesterdays_high():
    (sig,) = _signals(bars_from_ohlc("NEW", _base_rows()[:22], start=LISTED))  # day 21: the real breakout
    assert sig.features["pivot"] == pytest.approx(23.0)
    # day 22: the base would have to include day 21's breakout, so there is no first base to break out of
    assert _signals(bars_from_ohlc("NEW", _base_rows(), start=LISTED)) == []


def test_zero_volume_listing_does_not_abort_the_scan():
    zero = [[10.0, 10.0, 10.0, 10.0, 0.0]] * 21 + [[10.0, 10.2, 10.0, 10.2, 1000.0]]
    good = bars_from_ohlc("GOOD", _base_rows()[:22], start=LISTED)
    sigs = _signals(bars_from_ohlc("ZERO", zero, start=LISTED), good)
    assert [s.symbol for s in sigs] == ["GOOD"]


def test_failed_breakout_exit_is_declared_as_built():
    doc = " ".join(mod.__doc__.split())
    assert "failed-breakout exit, a close back below the entry signal's pivot" in doc
