"""Gate 2 multiple-testing helper: deflated and Harvey-Liu haircut Sharpe against ALL logged trials."""
from __future__ import annotations

import math

import pytest

from swing_engine.research.metrics import deflated_sharpe, haircut_sharpe, multiple_testing
from swing_engine.research.trials import log_trial


def test_haircut_grows_with_trials():
    sr1, h1 = haircut_sharpe(1.0, 10.0, 1)
    assert sr1 == pytest.approx(1.0) and h1 == pytest.approx(0.0, abs=1e-9)
    _, h10 = haircut_sharpe(1.0, 10.0, 10)
    _, h100 = haircut_sharpe(1.0, 10.0, 100)
    assert 0 < h10 < h100 < 1
    sr, h = haircut_sharpe(-0.5, 10.0, 10)
    assert sr == -0.5 and math.isnan(h)


def test_multiple_testing_uses_every_strategys_trials(tmp_path):
    path = tmp_path / "trials.jsonl"
    for name in ["a", "a", "b", "c", "c", "c"]:
        log_trial(name, {}, {}, path)
    out = multiple_testing(1.5, 1260, trials_path=str(path))
    assert out["n_trials_all"] == 6
    assert out["deflated_sharpe"] == pytest.approx(deflated_sharpe(1.5, 6, 1260))
    assert out["haircut_sharpe"] == pytest.approx(haircut_sharpe(1.5, 5.0, 6)[0])
    assert 0 < out["haircut"] < 1
