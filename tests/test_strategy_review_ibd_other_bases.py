"""Review regressions for ibd_other_bases: the double bottom's handle variant (pivot = handle high)."""
from __future__ import annotations

import numpy as np
import pytest

from swing_engine.features.extra import ensure_extra
from swing_engine.strategies.ibd_other_bases import IbdOtherBases
from tests.fixtures.strategies.panel import add_features, bars_from_closes, last_date

# _double_bottom's W from test_strategy_batch_0, then a handle dipping 94 -> 90 -> 94 before the 96.5 breakout
W_LEGS = [(100, 85, 11), (85, 95, 11), (95, 83, 11), (83, 94, 13)]
HANDLE_LEGS = [(94, 90, 7), (90, 94, 7)]


def _panel(legs):
    closes = list(np.linspace(50, 100, 200))
    for a, b, k in legs:
        closes += list(np.linspace(a, b, k)[1:])
    bars = bars_from_closes("AAA", [*closes, 96.5])
    bars.loc[bars.index[-1], "volume"] = 3e6
    return add_features(bars)


def _signals(params, panel):
    s = IbdOtherBases(params)
    return s.signals(ensure_extra(panel, s.extra_features), last_date(panel))


def test_double_bottom_with_handle_pivots_on_handle_high():
    sigs = _signals(None, _panel(W_LEGS + HANDLE_LEGS))
    assert len(sigs) == 1
    sig = sigs[0]
    assert sig.notes.startswith("double_bottom")
    assert sig.features["pivot"] == pytest.approx(94 * 1.005)  # handle high, not the 95 middle peak
    assert sig.entry == pytest.approx(96.5) and sig.stop == pytest.approx(96.5 * 0.93)
    w = {c: _panel(W_LEGS + HANDLE_LEGS)[c].to_numpy() for c in ("high", "low", "close")}
    base = IbdOtherBases()._double_bottom(w, len(w["close"]) - 2)
    assert base.floor == pytest.approx(90 * 0.995)  # handle low


def test_handle_off_restores_plain_w_only():
    assert _signals({"db_handle": False}, _panel(W_LEGS + HANDLE_LEGS)) == []
    sig = _signals({"db_handle": False}, _panel(W_LEGS))[0]
    assert sig.features["pivot"] == pytest.approx(95 * 1.005)
