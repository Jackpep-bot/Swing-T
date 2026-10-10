# Pre-registration: walk-forward ensemble of (strategy, regime) cells (2026-10-10)

COMMIT: <to fill>

One test, fixed before it is run, graded on the existing replay shadow ledgers (replay_r1, replay_r2, replay_news;
these predate the 2026-10-10 splits backfill, which is noted as a limit). Same statistic and code path as
docs/preregistration/2026-10-10-walkforward-ensemble.md.

## Idea
The playbook router assumes a setup works in some market regimes and not others. If that is true, cells that worked
in 2017-24 should keep working in 2024-26 even though whole strategies did not.

## Rule
- Cell = (base strategy, router regime label on the signal day). Same exclusions as the ensemble test (no `@liq`
  or `_no_news` variants, none of the pre-registered picks).
- Selection window 2017-01-01 .. 2024-10-04; test window 2024-10-07 .. 2026-10-05; horizon 20 sessions.
- Selected cells: net R per signal > 0 AND block t >= 2.0 in the selection window, AND at least 200 traded signals
  there (a cell needs enough history to mean anything; fixed now).
- Ensemble: all signals of the selected cells in the test window, pooled, equal weight per signal.
- PASS only if pooled test-window net R per signal > 0 AND block t >= 2.0. n_trials = 1. Void = FAIL.

## Limits stated before the result
- Regime labels in the selection window come from breadth computed on a partly survivor-biased universe.
- With ~130 strategies x 5 regimes there are ~650 cells; selecting on t >= 2.0 will admit some by chance, which
  is exactly what the out-of-sample window is for.
- Any change after the result is a new trial.
