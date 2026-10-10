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
