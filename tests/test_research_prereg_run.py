"""research.prereg_run: job plan and memory packing."""
from __future__ import annotations

from swing_engine.research import prereg_run as pr


def test_plan_and_packing_respect_the_budget() -> None:
    jobs = pr.plan(["a", "b", "c"])
    assert len(jobs) == 6 and jobs[0].gb >= jobs[-1].gb
    first = pr.next_batch(jobs, 0.0, budget=40.0)
    assert sum(j.gb for j in first) <= 40.0 and sum(j.gb == 18.0 for j in first) == 2  # two long + shorts
    assert pr.next_batch(jobs, 36.0, budget=40.0) == []  # nothing fits beside two long runs
    assert len(pr.next_batch(jobs[:1], 0.0, budget=1.0)) == 1  # never deadlocks on an oversize job


def test_benchmark_arguments_are_handed_to_the_grader() -> None:
    import argparse

    ns = argparse.Namespace(benchmark="SPY", benchmark_slugs="a,b")
    assert pr.eval_benchmark_args(ns) == ["--benchmark", "SPY", "--benchmark-slugs", "a,b"]
    assert pr.eval_benchmark_args(argparse.Namespace(benchmark=None, benchmark_slugs="")) == []
    ns = argparse.Namespace(benchmark="SPY", benchmark_slugs="", alpha_slugs="a,b")
    assert pr.eval_benchmark_args(ns) == ["--benchmark", "SPY", "--benchmark-slugs", "", "--alpha-slugs", "a,b"]


def test_reserved_gb_counts_every_replay_on_the_machine() -> None:
    lines = [
        "/x/python3 -m swing_engine.cli --settings a.yaml replay --start 2017-01-01 --end 2024-10-04 --no-router",
        "/x/python3 /x/.venv/bin/swing --settings b.yaml replay --start 2024-10-07 --end 2026-10-05",
        "/x/python3 -m pytest",
    ]
    assert pr.reserved_gb(lines) == pr.JOB_GB[2017] + pr.JOB_GB[2024]
