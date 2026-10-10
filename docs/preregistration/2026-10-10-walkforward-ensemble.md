# Pre-registration: walk-forward ensemble of the 2017-24 winners (2026-10-10)

COMMIT: <to fill>

One test, fixed before it is run. No replay is needed: it is graded on the existing replay shadow ledgers
(data/live/replay_r1.duckdb, replay_r2.duckdb, replay_news.duckdb) with `research.leaderboard.edge_stats`.

## Idea
Single strategies have no edge that survives costs and multiple testing in both windows. Published work on combining
many weak signals (docs/methods.md, "sizing and portfolio construction for many weak signals") says a pool can be
better than its parts. The honest way to pick the pool is walk-forward: select on the earlier window only, test on
the later one.

## Rule
- Selection window: 2017-01-01 .. 2024-10-04. Test window: 2024-10-07 .. 2026-10-05. The test window plays no part
  in selection.
- Horizon: 20 sessions only (the longest graded horizon; lowest turnover).
- Selected strategies: every base strategy (no `@liq` variants, no `_no_news` variants, none of the five
  pre-registered picks) whose selection-window row has net R per signal > 0 AND block t >= 2.0, as computed by
  `research.leaderboard.edge_stats` (executable filter, planned-risk R, per-stock costs).
- Ensemble: all signals of the selected strategies in the test window, pooled, each signal weighted equally.
- Statistic: net R per signal, block t (blocks of 20 sessions) and annual Sharpe = t / sqrt(years), from
  `edge_stats` on the pooled signals; Harvey-Liu haircut with n_trials = 1 (it is one pre-registered test).
- Also reported, not a criterion: the same pooled statistic on the selection window (in-sample, for contrast), the
  list of selected strategies, and the number of signals each contributes.

## Pass criteria
PASS only if, in the test window, pooled net R per signal > 0 AND block t >= 2.0. Otherwise FAIL.
If no strategy is selected the test is void and recorded as FAIL.

## Limits stated before the result
- The 2017-24 window is still partly survivor-biased before the delisted names were added for every year; selection
  on it may favour strategies that liked survivors.
- A pass would send the ensemble to a portfolio replay and the walk-forward skill; it would not enable anything.
- Any change after the result (threshold, horizon, weighting) is a new trial.
