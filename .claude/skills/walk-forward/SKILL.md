---
name: walk-forward
description: Walk-forward test of a leaderboard survivor - tune params on one period, test the chosen set once on the next, roll forward, log every parameter set as a trial, and report deflated and haircut Sharpe; never tune and test on the same data.
---
## Read first
`docs/gates.md` (gate 2), `docs/leaderboard.md` (only survivors get a walk-forward), the backtest skill (settings,
windows, long jobs, significance commands), and `swing_engine/research/cv.py` (`purged_walk_forward`, `fold_dates`).

## 1. Pre-register (write it in the card's "Implementation spec" before any run)
- The param grid: k sets. Each set on each training fold is one trial, and every one is logged.
- The selection criterion used on training output only, e.g. highest `sharpe` with `trades` >= 30.
- The fold scheme and the pass rule. Pass needs all of:
  - the out-of-sample (OOS) haircut Sharpe > 0 after costs,
  - deflated Sharpe >= 0.95 against the full trial count,
  - a majority of test folds with Sharpe > 0.
  Plan on at most half the published edge.

## 2. Folds
Print the fold dates with the repo helper (purge = the strategy's `max_hold_days` in sessions, so no trade spans the
train/test boundary). Example: rolling 3-year train, 4 test folds:
```
uv run python -c "
from swing_engine.research.cv import purged_walk_forward, fold_dates
from swing_engine.data.calendar import trading_days
d = trading_days('2017-01-03', '2026-10-05')
for s in purged_walk_forward(d, n_splits=4, purge=20, window=756):
    tr, te = fold_dates(d, s); print(tr[0], tr[-1], '->', te[0], te[-1])"
```
Data before 2024-10-07 is survivors-only and biased upward. Report folds that test inside 2024-10-07..2026-10-05
separately, and give them the weight.

## 3. Per fold
- Tune, on training dates only, one logged run per param set:
  `uv run swing --settings config/replay.yaml backtest <strategy> --start <train_start> --end <train_end> -P k=v ...`
- Pick the set by the pre-registered criterion from those outputs alone.
- Test the chosen set once:
  `uv run swing --settings config/replay.yaml backtest <strategy> --start <test_start> --end <test_end> -P <chosen>`
  Never run other sets on a test fold. If one was run by mistake, it is logged and must be reported. Never move fold
  dates after seeing results.
- Use `backtest` (it has `-P`) for the grid. `replay` takes params only from a settings file and upserts its shadow
  ledger. Use it only for a final portfolio check of the chosen set, on its own store copy.

## 4. Score
- If the same set won every fold, run one more logged backtest of that set over the whole OOS span (first test start
  to last test end), and score it.
- If the chosen set changes from fold to fold, there is no stitched OOS series: the repo has no helper for one, so do
  not hand-stitch. Score each test fold and treat the unstable choice as evidence against the strategy.
- Scoring:
  - `uv run python -c "from swing_engine.research.metrics import multiple_testing as m; print(m(SR, N_OBS, SKEW, KURT))"`
    (from the printed `n_obs / skew / kurtosis`; it counts ALL logged trials).
  - If the leaderboard's trial count (`docs/leaderboard.md` header) is larger, use it:
    `uv run python -c "from swing_engine.research.metrics import haircut_sharpe as h; print(h(SR, YEARS, N))"`.
  - Then re-run `research.leaderboard` (research-loop skill, step 4) so its haircut picks up the new trial count.

## 5. Report
A table per fold: train dates, test dates, chosen params, test trades, win rate, avg R, PF, max DD, Sharpe. Then the
OOS deflated Sharpe, haircut Sharpe, the trial count used, and pass or fail against the pre-registered rule.
Passing makes a strategy a candidate for paper at small risk through the weekly-review skill. Nothing is enabled here.
