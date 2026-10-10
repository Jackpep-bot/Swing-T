"""Run a pre-registered group's replays in parallel, one strategy and window per process, each on its own store copy.

DuckDB allows one writer per file, so every job gets a copy of the group's store; the replay JSONs land in the shared
runs/replay folder and research.prereg_eval grades from those plus the base store's bars. Jobs are packed under a
memory budget (a single-strategy replay peaks near 5 GB on the 2024-26 window and 18 GB on 2017-24). Results are the
same as serial runs: each replay is deterministic and independent. Run detached::

    nohup uv run python -m swing_engine.research.prereg_run --settings config/prereg2.yaml --tag-prefix prereg2- \
        --slugs a,b --n-trials 2 --out docs/preregistration/<file>-results.md > data/logs/research/<name>.log 2>&1 &

``--benchmark`` / ``--benchmark-slugs`` go to the grader; ``--benchmark-settings`` is the settings file (own book and
universe) for the replays of the benchmark slugs (docs/preregistration/2026-10-10-batch2.md).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from swing_engine.research.cards import ROOT, WINDOWS

#: Peak memory of a single-strategy replay by window start year (GB), measured 2026-10-09 (research/runner.py notes).
JOB_GB = {2024: 5.0, 2017: 18.0}
MEMORY_BUDGET_GB = 40.0
POLL_S = 5.0


@dataclass(frozen=True)
class Job:
    slug: str
    start: str
    end: str
    gb: float


def plan(slugs: Sequence[str]) -> list[Job]:
    """Every (slug, window), biggest jobs first so the packing fills the budget early."""
    jobs = [Job(s, w.start.isoformat(), w.end.isoformat(), JOB_GB.get(w.start.year, max(JOB_GB.values())))
            for s in slugs for w in WINDOWS]
    return sorted(jobs, key=lambda j: -j.gb)


def next_batch(pending: list[Job], running_gb: float, budget: float = MEMORY_BUDGET_GB) -> list[Job]:
    """Jobs from ``pending`` (in order) that fit beside what is running; at least one when nothing runs."""
    out: list[Job] = []
    used = running_gb
    for job in pending:
        if used + job.gb <= budget or (used == 0 and not out):
            out.append(job)
            used += job.gb
    return out


def eval_benchmark_args(args: argparse.Namespace) -> list[str]:
    """The ``--benchmark`` / ``--benchmark-slugs`` arguments to hand on to ``prereg_eval`` (none when unset)."""
    if not args.benchmark:
        return []
    return ["--benchmark", args.benchmark, "--benchmark-slugs", args.benchmark_slugs]


def main(argv: Sequence[str] | None = None) -> None:
    from swing_engine.core.config import load_settings
    from swing_engine.research import prereg_eval

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--settings", required=True)
    ap.add_argument("--slugs", required=True)
    ap.add_argument("--tag-prefix", required=True)
    ap.add_argument("--n-trials", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--benchmark", default=None, help="passed to prereg_eval")
    ap.add_argument("--benchmark-slugs", default="", help="passed to prereg_eval")
    ap.add_argument("--benchmark-settings", default=None,
                    help="settings file for the replays of --benchmark-slugs (their own book); default --settings")
    args = ap.parse_args(argv)
    slugs = [s for s in args.slugs.split(",") if s]
    bench_slugs = {s for s in args.benchmark_slugs.split(",") if s}
    base = ROOT / load_settings.__wrapped__(Path(args.settings)).data.store_path
    pending, running = plan(slugs), {}
    while pending or running:
        for job, (proc, store, cfg) in list(running.items()):
            if proc.poll() is not None:
                print(f"done {job.slug} {job.start} exit {proc.returncode}", flush=True)
                for path in (store, cfg, Path(f"{store}.wal")):
                    path.unlink(missing_ok=True)
                del running[job]
        for job in next_batch(pending, sum(j.gb for j in running)):
            pending.remove(job)
            stem = f"pr_{args.tag_prefix}{job.slug}_{job.start[:4]}"
            store, cfg = base.with_name(f"{stem}.duckdb"), base.with_name(f"{stem}.yaml")
            shutil.copyfile(base, store)
            parent = args.benchmark_settings if args.benchmark_settings and job.slug in bench_slugs else args.settings
            cfg.write_text(f"extends: {(ROOT / parent).resolve()}\ndata:\n  store_path: {store.relative_to(ROOT)}\n")
            log = ROOT / "data" / "logs" / "research" / f"{stem}.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            cmd = [sys.executable, "-m", "swing_engine.cli", "--settings", str(cfg), "replay", "--start", job.start,
                   "--end", job.end, "--no-router", "-s", job.slug, "--tag", f"{args.tag_prefix}{job.slug}"]
            running[job] = (subprocess.Popen(cmd, cwd=ROOT, stdout=log.open("w"), stderr=subprocess.STDOUT), store, cfg)
            print(f"start {job.slug} {job.start}", flush=True)
        time.sleep(POLL_S)
    prereg_eval.main(["--settings", args.settings, "--slugs", ",".join(slugs), "--tag-prefix", args.tag_prefix,
                      "--n-trials", str(args.n_trials), "--out", args.out, *eval_benchmark_args(args)])
    print("PREREG GROUP DONE", flush=True)


if __name__ == "__main__":
    main()
