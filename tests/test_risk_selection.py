"""Rank hysteresis: enter at the top-k, hold until the name drops below the top-m."""
from __future__ import annotations

import pytest

from swing_engine.risk.selection import rank_hysteresis

RANKED = [f"S{i}" for i in range(10)]  # S0 best


def test_enter_top_k_hold_top_m():
    assert rank_hysteresis(RANKED, [], 2, 4) == ["S0", "S1"]
    assert rank_hysteresis(RANKED, ["S3", "S5", "GONE"], 2, 4) == ["S0", "S1", "S3"]  # S5 below m, GONE unranked


def test_fractions_of_the_ranked_list():
    # enter top 10% (1 name), hold while in the top 30% (3 names)
    assert rank_hysteresis(RANKED, ["S2"], 0.1, 0.3) == ["S0", "S2"]


def test_hold_band_must_cover_entry_band():
    with pytest.raises(ValueError):
        rank_hysteresis(RANKED, [], 4, 2)
