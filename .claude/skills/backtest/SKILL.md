---
name: backtest
description: Run a walk-forward backtest for one or more strategies, log the trial, and summarize metrics honestly (deflated Sharpe, costs, drawdown).
---
1. `uv run swing backtest <strategy> --start <date> [--end <date>] [--provider massive|sample] [--param k=v ...]`.
2. Every run appends to `data/trials.jsonl`; the summary must state the cumulative trial count and the Deflated Sharpe for that count.
3. Report: trades, win rate, avg R, profit factor, CAGR, max DD, Sharpe (raw and deflated), turnover, costs charged. Compare to SPY buy-and-hold over the same window.
4. If the user asks to "tweak until it works", refuse to parameter-hunt silently: run a grid, log all trials, and show the deflated result.
