"""Kill switch: file presence is the whole protocol."""
from __future__ import annotations

from swing_engine.core.config import ROOT
from swing_engine.risk import killswitch


def test_trip_status_reset(tmp_path):
    path = tmp_path / "KILL"
    assert not killswitch.is_tripped(path)
    killswitch.trip(path, "manual test")
    assert killswitch.is_tripped(path)
    assert "manual test" in killswitch.status(path)["reason"]
    assert killswitch.reset(path)
    assert not killswitch.is_tripped(path)
    assert not killswitch.reset(path)


def test_touched_empty_file_counts_as_tripped(tmp_path):
    path = tmp_path / "KILL"
    path.touch()
    assert killswitch.is_tripped(path)
    assert killswitch.status(path) == {"path": str(path), "tripped": True, "reason": ""}


def test_relative_paths_resolve_against_repo_root():
    assert killswitch.resolve_state_path("state/KILL") == ROOT / "state" / "KILL"
    assert killswitch.DEFAULT_KILL_SWITCH_FILE == "state/KILL"
