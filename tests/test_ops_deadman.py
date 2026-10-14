import json
from datetime import date

from swing_engine.ops.deadman import problem


def test_problem_by_report_state(tmp_path):
    day, path = date(2026, 10, 14), tmp_path / "2026-10-14.json"
    assert "has not started" in problem(path, day)
    path.write_text(json.dumps({"started_at": "2026-10-14T10:30:00Z", "finished_at": None}))
    assert "has not finished" in problem(path, day)
    path.write_text("{not json")
    assert "cannot be read" in problem(path, day)
    path.write_text(json.dumps({"started_at": "x", "finished_at": "2026-10-14T10:43:26Z"}))
    assert problem(path, day) is None
    assert problem(tmp_path / "missing.json", date(2026, 10, 17)) is None  # a Saturday
    assert problem(tmp_path / "missing.json", date(2026, 11, 26)) is None  # Thanksgiving
