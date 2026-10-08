---
name: backtest
description: Run a single-strategy backtest or a multi-strategy replay on real data, with every run logged as a trial, and report it honestly (costs, drawdown, deflated and haircut Sharpe against all trials).
---
## Read first
`docs/gates.md` (gate 2), `docs/leaderboard.md`, `docs/STATUS.md` (current stores and runs).

## Data and settings
- Always pass `--settings config/replay.yaml`, which uses a copy of the live store (`data/live/replay.duckdb`). The
  default `config/settings.yaml` points at the old sample-era store `data/swing.duckdb`.
- Windows: `2024-10-07..2026-10-05` is survivorship-free, every US ticker. `2017-01-01..2024-10-04` holds survivors
  only (~4,300 names liquid in 2024), so it is biased upward. Report the two windows separately; never pool them.
- Prices are split-adjusted, not dividend-adjusted.

## Commands (`uv run swing <cmd> --help` lists all flags)
- One strategy over one period (a single portfolio run; the walk-forward skill does the walk-forward):
  `uv run swing --settings config/replay.yaml backtest <strategy> --start 2024-10-07 --end 2026-10-05 [-P k=v ...] [--cost k=v]`
  It logs one trial named `<strategy>` and prints the metrics and the deflated Sharpe against ALL logged trials.
  `-P` overrides a strategy param; params otherwise come from the settings file.
- The live pipeline replayed day by day over many strategies:
  `uv run swing --settings config/replay.yaml replay --start <d> --end <d> --no-router -s a,b --tag <tag>`.
  It logs one trial named `replay`, saves `data/live/runs/replay/<start>_<end>_<tag>.json`, and upserts every signal
  into `shadow_signals_replay` keyed (strategy, symbol, as_of). It has no `--param` flag: params come from settings.
- The replay ledger: `uv run swing --settings config/replay.yaml shadow report --replay --by strategy --horizon 10`.
- The trial log: `uv run swing trials --last 20 [--name <strategy>]`.

## Long jobs (replay over the long window, big grids)
- Check `pmset -g batt | head -1` says `AC Power`. On battery the Mac sleeps and caffeinate cannot stop it.
- Run with nohup in the background, logging to `data/logs/replay/<tag>.log` (see `scripts/run_research_replays.sh`).
  App restarts kill terminal tabs.
- Run at most 2 replays at once (~15-20 GB each on this 51 GB Mac), and never next to another heavy job.
- `replay` opens its store for writing. Never point it at the store the nightly or an ingest is writing. Each
  concurrent replay needs its own store copy and settings file, e.g. a scratch yaml with
  `extends: /Users/personal/Desktop/swing-engine/config/replay.yaml` and `data: {store_path: data/live/replay_b.duckdb}`.
  The leaderboard and cards merge them with `--store`.

## Trials and significance
- Every run you look at is logged. The log is `data/trials.jsonl`: never edit or prune it. `--no-log` is only for
  smoke runs on `--provider sample`.
- The deflated Sharpe that `backtest` prints already counts ALL logged trials (`trial_count(None)`). The haircut is
  not printed, so compute both from the printed `n_obs / skew / kurtosis`:
  `uv run python -c "from swing_engine.research.metrics import multiple_testing as m; print(m(SR, N_OBS, SKEW, KURT))"`.
- The trial log under-counts the looks. The leaderboard's 750 trials come from strategies x horizons x windows. When
  the leaderboard count is larger, use it:
  `uv run python -c "from swing_engine.research.metrics import haircut_sharpe as h; print(h(SR, YEARS, N))"`.
- "Tweak until it works" is a grid: write it down first, run every point, log all of them, and report the best one
  only together with its deflated and haircut Sharpe. Tuning and testing on separate data is the walk-forward skill.

## Report
Trades, win rate, avg R, profit factor, CAGR, max DD, Sharpe raw / deflated / haircut, the trial count used, turnover,
`total_costs` and `cost_drag`, and `n_entries_skipped`. Compare with SPY buy-and-hold (price only) over the same window:
`uv run python -c "from swing_engine.data.store import Store; c=Store('data/live/replay.duckdb', read_only=True).read_bars(['SPY'],'2024-10-07','2026-10-05')['close']; print(c.iloc[-1]/c.iloc[0]-1)"`.
Judge against `docs/gates.md`. A result that is not a leaderboard survivor is not an edge, whatever its raw Sharpe.
