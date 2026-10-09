"""One command for the research replays (`swing research run` / `swing research rebuild`).

Replaces the hand-written scripts/lane_*.sh: copy the live store once per lane, split every registered strategy
into chunks, run each (window, chunk) as a `swing replay --no-router` subprocess on its lane's store copy, then
rebuild the strategy cards and the leaderboard over all lane stores. State lives in a small manifest,
``<runs>/research/<run-id>.json``: lane stores, chunk tags and each chunk's status, so a rerun with ``--resume``
only replays the chunks that are not done. Chunks are pinned to a lane at planning time, so a retried chunk
writes the same store its first attempt did. Progress lines go to ``data/logs/research/<run-id>.log``.
"""
from __future__ import annotations

import json
import os
import platform
import queue
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from swing_engine.research.cards import ROOT, WINDOWS, Window

#: `--windows` names -> research windows (research.cards.WINDOWS: survivorship-free first, long history second)
WINDOW_NAMES: dict[str, Window] = {"short": WINDOWS[0], "long": WINDOWS[1]}
#: strategies per replay subprocess (the lane scripts used 14-16)
CHUNK_SIZE = 16
#: GB per lane for `--lanes auto`: a 2017-2024 replay peaked at 16.7 GB RSS (2026-10-09, two strategies), plus
#: headroom for a 16-strategy chunk's extras
LANE_GB = 18.0
#: total memory the lanes may take (the owner's limit on this 48 GB Mac)
MEMORY_CAP_GB = 40.0
#: inline retries of a failed chunk before it is left for `--resume`
RETRIES = 1
LOG_DIR = ROOT / "data" / "logs" / "research"
DONE, FAILED, PENDING = "done", "failed", "pending"

Runner = Callable[..., Any]


def chunk_names(names: Sequence[str], size: int = CHUNK_SIZE) -> list[list[str]]:
    """Sorted names dealt round-robin into ceil(n / size) chunks (spreads neighbours such as a strategy family)."""
    names = sorted(dict.fromkeys(names))
    n = max(1, -(-len(names) // size)) if names else 0
    return [names[k::n] for k in range(n)]


def free_memory_gb() -> float:
    """Memory available without swapping: free + inactive + speculative pages (macOS vm_stat), else
    the kernel's available pages."""
    if platform.system() == "Darwin":
        out = subprocess.run(["vm_stat"], capture_output=True, text=True, check=True).stdout
        page = int(out.split("page size of ")[1].split()[0])
        stats = {k.strip(): int(v.strip().rstrip(".")) for k, v in
                 (line.split(":", 1) for line in out.splitlines()[1:] if ":" in line) if v.strip().rstrip(".").isdigit()}
        pages = sum(stats.get(f"Pages {k}", 0) for k in ("free", "inactive", "speculative"))
        return pages * page / 1e9
    return os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 1e9


def choose_lanes(requested: str, n_chunks: int, free_gb: float | None = None) -> int:
    """`--lanes N`, or `auto`: as many LANE_GB lanes as fit in min(free memory, MEMORY_CAP_GB); 1..n_chunks."""
    if requested == "auto":
        free = free_memory_gb() if free_gb is None else free_gb
        want = int(min(free, MEMORY_CAP_GB) // LANE_GB)
    else:
        want = int(requested)
    return max(1, min(want, n_chunks))


def on_battery() -> bool:
    if platform.system() != "Darwin":
        return False
    out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True).stdout
    return "Battery Power" in out.splitlines()[0] if out else False


# ----------------------------------------------------------------------------------------------- manifest


def manifest_dir(runs_root: Path) -> Path:
    return runs_root / "research"


def save_manifest(manifest: dict[str, Any], runs_root: Path) -> Path:
    path = manifest_dir(runs_root) / f"{manifest['run_id']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(manifest, indent=2))
    tmp.replace(path)
    return path


def load_manifest(runs_root: Path, run_id: str | None = None) -> dict[str, Any]:
    """The manifest of ``run_id``, or of the latest run (run ids sort by time)."""
    folder = manifest_dir(runs_root)
    if run_id is None:
        paths = sorted(folder.glob("*.json"))
        if not paths:
            raise FileNotFoundError(f"no research runs in {folder}")
        return json.loads(paths[-1].read_text())
    return json.loads((folder / f"{run_id}.json").read_text())


def plan(
    run_id: str,
    windows: Sequence[str],
    strategies: Sequence[str],
    settings_path: Path,
    source_store: Path,
    runs_root: Path,
    n_lanes: int,
    size: int = CHUNK_SIZE,
) -> dict[str, Any]:
    """Manifest for a new run: one lane store copy per lane, chunks dealt to lanes round-robin."""
    unknown = [w for w in windows if w not in WINDOW_NAMES]
    if unknown:
        raise ValueError(f"unknown windows {unknown}; choose from {sorted(WINDOW_NAMES)}")
    lanes = []
    for k in range(n_lanes):
        store = source_store.parent / f"research_{run_id}_l{k}.duckdb"
        lanes.append({"store": str(store), "settings": str(manifest_dir(runs_root) / run_id / f"lane{k}.yaml")})
    chunks = []
    for w in windows:
        for i, names in enumerate(chunk_names(strategies, size)):
            chunks.append({"window": w, "start": WINDOW_NAMES[w].start.isoformat(), "end": WINDOW_NAMES[w].end.isoformat(),
                           "tag": f"{run_id}-{w}{i + 1}", "strategies": names, "lane": len(chunks) % n_lanes,
                           "status": PENDING})
    return {"run_id": run_id, "created": datetime.now().isoformat(timespec="seconds"),
            "settings": str(settings_path), "source_store": str(source_store), "lanes": lanes, "chunks": chunks}


def prepare_lanes(manifest: dict[str, Any], log: Callable[[str], None]) -> None:
    """Copy the source store to each lane store that does not exist yet and write the lane settings files.

    Refuses when the source store is open for writing elsewhere (nightly, ingest): DuckDB then denies even a
    read-only connection, and a copy taken mid-write could be torn."""
    import duckdb

    src = Path(manifest["source_store"])
    base = Path(manifest["settings"]).resolve()
    for lane in manifest["lanes"]:
        store, yml = Path(lane["store"]), Path(lane["settings"])
        yml.parent.mkdir(parents=True, exist_ok=True)
        yml.write_text(f"extends: {base}\ndata:\n  store_path: {store}\n")
        if store.exists():
            continue
        try:
            duckdb.connect(str(src), read_only=True).close()
        except duckdb.Error as exc:
            raise RuntimeError(f"{src} is in use ({exc}); retry when the nightly / ingest is done") from exc
        log(f"copy {src} -> {store}")
        shutil.copy2(src, store)


# ----------------------------------------------------------------------------------------------- execution


def chunk_command(chunk: dict[str, Any], lane: dict[str, Any]) -> list[str]:
    return [sys.executable, "-m", "swing_engine.cli", "--settings", lane["settings"], "replay",
            "--start", chunk["start"], "--end", chunk["end"], "--no-router", "--tag", chunk["tag"],
            "-s", ",".join(chunk["strategies"])]


def _replay_json(chunk: dict[str, Any], lane: dict[str, Any]) -> Path:
    return Path(lane["store"]).parent / "runs" / "replay" / f"{chunk['start']}_{chunk['end']}_{chunk['tag']}.json"


def run_chunks(
    manifest: dict[str, Any],
    runs_root: Path,
    log: Callable[[str], None],
    runner: Runner = subprocess.run,
    log_dir: Path | None = None,
) -> dict[str, Any]:
    """Run every chunk not yet done, one thread per lane (chunks of a lane run in order), retrying a failed chunk
    RETRIES times. A chunk is done when its subprocess exits 0 and its runs/replay JSON exists. The manifest is
    saved after every chunk."""
    lock = threading.Lock()
    chunk_logs = (log_dir or LOG_DIR) / manifest["run_id"]
    chunk_logs.mkdir(parents=True, exist_ok=True)
    todo = [c for c in manifest["chunks"] if c["status"] != DONE]
    total = len(manifest["chunks"])

    def lane_worker(k: int, jobs: queue.Queue) -> None:
        lane = manifest["lanes"][k]
        while not jobs.empty():
            chunk = jobs.get()
            for attempt in range(RETRIES + 1):
                started = datetime.now()
                log(f"lane {k} start {chunk['tag']} ({len(chunk['strategies'])} strategies, attempt {attempt + 1})")
                with open(chunk_logs / f"{chunk['tag']}.log", "w") as out:
                    proc = runner(chunk_command(chunk, lane), stdout=out, stderr=subprocess.STDOUT, cwd=ROOT)
                ok = proc.returncode == 0 and _replay_json(chunk, lane).exists()
                mins = (datetime.now() - started).total_seconds() / 60
                with lock:
                    chunk["status"] = DONE if ok else FAILED
                    chunk["minutes"] = round(mins, 1)
                    save_manifest(manifest, runs_root)
                    n_done = sum(c["status"] == DONE for c in manifest["chunks"])
                log(f"lane {k} {'done' if ok else 'FAILED'} {chunk['tag']} exit {proc.returncode} in {mins:.1f} min "
                    f"({n_done}/{total} done)")
                if ok:
                    break

    queues: dict[int, queue.Queue] = {}
    for c in todo:
        queues.setdefault(int(c["lane"]), queue.Queue()).put(c)
    threads = [threading.Thread(target=lane_worker, args=(k, q), daemon=True) for k, q in sorted(queues.items())]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return manifest


def rebuild(manifest: dict[str, Any], log: Callable[[str], None]) -> dict[str, Any]:
    """Cards + leaderboard over the run's lane stores (research.cards / research.leaderboard main), then the
    ``ops.notify.notify_research_summary`` hook when it exists (a notification never fails the run)."""
    from swing_engine.research import cards, leaderboard

    lanes = manifest["lanes"]
    first, extra = lanes[0]["settings"], [a for lane in lanes[1:] for a in ("--store", lane["store"])]
    log("rebuild over " + " ".join(lane["store"] for lane in lanes))
    cards.main(["--settings", first, *extra, "--tag", manifest["run_id"]])
    board, n_trials = leaderboard.main(["--settings", first, *extra])
    surv = leaderboard.survivors(board)
    summary = {"run_id": manifest["run_id"], "chunks": len(manifest["chunks"]),
               "failed": [c["tag"] for c in manifest["chunks"] if c["status"] != DONE],
               "leaderboard_rows": len(board), "trials": n_trials,
               "survivors": sorted({f"{r.strategy}@{r.horizon}d" for r in surv.itertuples()})}
    log(f"rebuild done: {summary}")
    try:
        from swing_engine.ops.notify import notify_research_summary
    except ImportError:
        return summary
    try:
        top = board.sort_values("t", ascending=False).head(5) if len(board) else board
        notify_research_summary(surv, n_trials, top)
    except Exception as exc:  # noqa: BLE001 - a notification must not fail a finished run
        log(f"notify failed: {exc}")
    return summary


def run(
    settings_path: Path,
    source_store: Path,
    runs_root: Path,
    *,
    windows: Sequence[str] = ("short", "long"),
    strategies: Sequence[str] | None = None,
    lanes: str = "auto",
    resume: str | None = None,
    allow_battery: bool = False,
    size: int = CHUNK_SIZE,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    """`swing research run`: plan (or resume ``resume`` = run id / "latest"), copy stores, replay, rebuild, notify."""
    if not allow_battery and on_battery():
        raise RuntimeError("on battery power: the Mac sleeps mid-run; plug in or pass --allow-battery")
    if resume:
        manifest = load_manifest(runs_root, None if resume == "latest" else resume)
    else:
        from swing_engine.core import registry

        names = list(strategies or registry.names("strategy"))
        n_chunks = len(windows) * len(chunk_names(names, size))
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        manifest = plan(run_id, windows, names, settings_path, source_store, runs_root, choose_lanes(lanes, n_chunks),
                        size)
    log = file_logger(manifest["run_id"])
    todo = sum(c["status"] != DONE for c in manifest["chunks"])
    log(f"run {manifest['run_id']}: {todo}/{len(manifest['chunks'])} chunks on {len(manifest['lanes'])} lanes")
    prepare_lanes(manifest, log)
    save_manifest(manifest, runs_root)
    run_chunks(manifest, runs_root, log, runner)
    return rebuild(manifest, log)


def file_logger(run_id: str, log_dir: Path = LOG_DIR) -> Callable[[str], None]:
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{run_id}.log"
    lock = threading.Lock()

    def log(line: str) -> None:
        text = f"{datetime.now():%Y-%m-%d %H:%M:%S} {line}"
        with lock, open(path, "a") as f:
            f.write(text + "\n")
        print(text, flush=True)

    return log


__all__ = ["chunk_names", "choose_lanes", "load_manifest", "plan", "rebuild", "run", "run_chunks", "save_manifest"]
