"""research.runner: chunking, lane selection, manifest round trip, resume (subprocess calls mocked)."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from swing_engine.research import runner


def test_chunk_names_round_robin_covers_every_name_once():
    names = [f"s{k:03d}" for k in range(35)]
    chunks = runner.chunk_names(reversed(names), size=16)  # type: ignore[arg-type]
    assert len(chunks) == 3
    assert sorted(n for c in chunks for n in c) == names
    assert max(map(len, chunks)) - min(map(len, chunks)) <= 1
    assert chunks[0][:2] == ["s000", "s003"]  # neighbours land in different chunks
    assert runner.chunk_names([]) == []


@pytest.mark.parametrize(("requested", "free", "n_chunks", "want"), [
    ("auto", 100.0, 16, int(runner.MEMORY_CAP_GB // runner.LANE_GB)),  # capped at the owner's 40 GB
    ("auto", 5.0, 16, 1),  # never below one lane
    ("auto", 100.0, 1, 1),  # never more lanes than chunks
    ("3", 1.0, 16, 3),  # explicit count wins
])
def test_choose_lanes(requested, free, n_chunks, want):
    assert runner.choose_lanes(requested, n_chunks, free) == want


def _manifest(tmp_path: Path, n_lanes: int = 2) -> dict:
    return runner.plan("r1", ["short", "long"], [f"s{k}" for k in range(20)], tmp_path / "live.yaml",
                       tmp_path / "market.duckdb", tmp_path / "runs", n_lanes, size=8)


def test_plan_and_manifest_round_trip(tmp_path):
    m = _manifest(tmp_path)
    assert len(m["chunks"]) == 6 and {c["window"] for c in m["chunks"]} == {"short", "long"}
    assert [c["lane"] for c in m["chunks"]] == [0, 1, 0, 1, 0, 1]
    assert m["chunks"][0]["tag"] == "r1-short1" and m["chunks"][0]["start"] == "2024-10-07"
    assert m["lanes"][1]["store"].endswith("research_r1_l1.duckdb")
    runner.save_manifest(m, tmp_path / "runs")
    assert runner.load_manifest(tmp_path / "runs") == m == runner.load_manifest(tmp_path / "runs", "r1")
    with pytest.raises(ValueError):
        runner.plan("r2", ["medium"], ["s"], tmp_path, tmp_path, tmp_path, 1)


def _fake_runner(fail_tags: set[str], calls: list[str]):
    """subprocess.run stand-in: writes the replay JSON the real `swing replay` would, unless the tag fails."""
    def run(cmd, **kwargs):
        tag = cmd[cmd.index("--tag") + 1]
        calls.append(tag)
        if tag in fail_tags:
            return SimpleNamespace(returncode=1)
        start, end = cmd[cmd.index("--start") + 1], cmd[cmd.index("--end") + 1]
        store = Path(STORES[tag])
        out = store.parent / "runs" / "replay" / f"{start}_{end}_{tag}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("{}")
        return SimpleNamespace(returncode=0)
    return run


STORES: dict[str, str] = {}


def test_run_chunks_retries_then_resume_runs_only_unfinished(tmp_path):
    m = _manifest(tmp_path)
    STORES.update({c["tag"]: m["lanes"][c["lane"]]["store"] for c in m["chunks"]})
    calls: list[str] = []
    runner.run_chunks(m, tmp_path / "runs", lambda line: None, _fake_runner({"r1-long2"}, calls), tmp_path / "logs")
    assert calls.count("r1-long2") == runner.RETRIES + 1  # retried inline, still failing
    saved = runner.load_manifest(tmp_path / "runs", "r1")
    assert {c["tag"]: c["status"] for c in saved["chunks"]}["r1-long2"] == runner.FAILED
    assert sum(c["status"] == runner.DONE for c in saved["chunks"]) == 5
    assert (tmp_path / "logs" / "r1" / "r1-short1.log").exists()

    calls.clear()
    runner.run_chunks(saved, tmp_path / "runs", lambda line: None, _fake_runner(set(), calls), tmp_path / "logs")
    assert calls == ["r1-long2"]  # resume replays only the failed chunk, on its own lane
    assert all(c["status"] == runner.DONE for c in runner.load_manifest(tmp_path / "runs")["chunks"])


def test_chunk_without_replay_json_is_not_done(tmp_path):
    m = _manifest(tmp_path, n_lanes=1)
    m["chunks"] = m["chunks"][:1]
    runner.run_chunks(m, tmp_path / "runs", lambda line: None, lambda cmd, **k: SimpleNamespace(returncode=0),
                      tmp_path / "logs")
    assert m["chunks"][0]["status"] == runner.FAILED


def test_chunk_command_targets_the_lane_settings(tmp_path):
    m = _manifest(tmp_path)
    cmd = runner.chunk_command(m["chunks"][1], m["lanes"][1])
    assert cmd[cmd.index("--settings") + 1] == m["lanes"][1]["settings"]
    assert "--no-router" in cmd and cmd[cmd.index("-s") + 1] == ",".join(m["chunks"][1]["strategies"])


def test_run_refuses_on_battery(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "on_battery", lambda: True)
    with pytest.raises(RuntimeError, match="battery"):
        runner.run(tmp_path / "live.yaml", tmp_path / "market.duckdb", tmp_path / "runs")


def test_run_end_to_end_with_mocks(tmp_path, monkeypatch):
    src = tmp_path / "market.duckdb"
    import duckdb

    duckdb.connect(str(src)).close()
    monkeypatch.setattr(runner, "on_battery", lambda: False)
    monkeypatch.setattr(runner, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(runner, "file_logger", lambda run_id: lambda line: None)
    rebuilt: list[str] = []
    monkeypatch.setattr(runner, "rebuild", lambda m, log: rebuilt.append(m["run_id"]) or {"run_id": m["run_id"]})

    def fake(cmd, **kwargs):
        lane_yaml = Path(cmd[cmd.index("--settings") + 1])
        store = Path(lane_yaml.read_text().split("store_path: ")[1].strip())
        tag, start, end = (cmd[cmd.index(f) + 1] for f in ("--tag", "--start", "--end"))
        out = store.parent / "runs" / "replay" / f"{start}_{end}_{tag}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("{}")
        return SimpleNamespace(returncode=0)

    summary = runner.run(tmp_path / "live.yaml", src, tmp_path / "runs", windows=["short"], strategies=["a", "b"],
                         lanes="2", runner=fake)
    m = runner.load_manifest(tmp_path / "runs")
    assert summary == {"run_id": m["run_id"]} and rebuilt == [m["run_id"]]
    assert len(m["lanes"]) == 1  # one chunk: a second lane would only copy the store
    assert Path(m["lanes"][0]["store"]).exists()
    assert all(c["status"] == runner.DONE for c in m["chunks"])
