---
name: research-loop
description: Iterate on a strategy hypothesis with the Claude strategy lab: write/modify strategy code, run walk-forward backtests on the sample or Massive data, and log every trial for deflated-Sharpe accounting.
---
Use `swing_engine/agent/strategy_lab.py` conventions: each hypothesis gets an id, a one-paragraph spec, the exact param grid, and an entry in `data/trials.jsonl`. Keep the LLM to code and interpretation; all metrics come from `research/metrics.py`. Stop when the deflated Sharpe stays below the hurdle after the pre-registered grid; do not keep adding parameters.
