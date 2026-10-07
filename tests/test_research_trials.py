"""JSONL trial log."""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from swing_engine.research.trials import log_trial, read_trials, trial_count


def test_log_and_count_trials(tmp_path):
    path = tmp_path / "trials.jsonl"
    assert trial_count(path=path) == 0
    rec = log_trial("sr_bounce", {"lookback": np.int64(60), "when": pd.Timestamp("2026-10-06")},
                    {"sharpe": np.float64(1.2), "max_dd": math.nan, "pf": math.inf}, path=path, notes="first", tags=["a"])
    log_trial("rsi2", {"n": 2}, {"sharpe": 0.3}, path=path)
    assert trial_count(path=path) == 2
    assert trial_count("sr_bounce", path=path) == 1
    assert trial_count("missing", path=path) == 0
    assert len(rec["trial_id"]) == 12 and rec["name"] == "sr_bounce"

    lines = path.read_text().strip().splitlines()
    first = json.loads(lines[0])
    assert first["params"] == {"lookback": 60, "when": "2026-10-06T00:00:00"}
    assert first["metrics"] == {"sharpe": 1.2, "max_dd": None, "pf": None}
    assert first["notes"] == "first" and first["tags"] == ["a"]


def test_read_trials_flattens_and_skips_malformed(tmp_path):
    path = tmp_path / "t.jsonl"
    assert read_trials(path).empty
    log_trial("x", {"a": 1}, {"sharpe": 2.0}, path=path)
    with path.open("a") as fh:
        fh.write("{not json\n")
    log_trial("y", {"a": 2}, {"sharpe": 3.0}, path=path)
    df = read_trials(path)
    assert len(df) == 2
    assert list(df["name"]) == ["x", "y"]
    assert df["metrics.sharpe"].tolist() == [2.0, 3.0]
    assert trial_count(path=path) == 2


def test_relative_path_resolves_under_project_root(tmp_path, monkeypatch):
    from swing_engine.research import trials

    monkeypatch.setattr(trials, "ROOT", tmp_path)
    log_trial("z", {}, {}, path="data/sub/trials.jsonl")
    assert (tmp_path / "data" / "sub" / "trials.jsonl").exists()
    assert trial_count("z", path="data/sub/trials.jsonl") == 1
