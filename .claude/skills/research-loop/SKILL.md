---
name: research-loop
description: Take a strategy hypothesis from card to verdict - pre-register the test, implement it, replay both windows, rebuild the cards and leaderboard, and stop when the pre-registered grid fails the multiple-testing haircut.
---
## Read first
`docs/STATUS.md` (current stores, runs in flight), `docs/gates.md`, `docs/leaderboard.md`, the card
`docs/strategies/<slug>.md`, and the add-strategy, backtest and walk-forward skills.

## Loop
1. Pre-register before running anything. Write into the card's "Implementation spec for swing-engine": the hypothesis
   in one paragraph, the exact param grid (every point is a trial), the windows, the horizon you will judge (5/10/20d),
   and the stop rule ("drop it if no positive haircut Sharpe in both windows"). Do not add params after seeing results.
2. Implement or modify the module with the add-strategy skill. The full test suite and ruff must be green.
3. Replay both windows (backtest skill, "Long jobs"; AC power, detached):
   `nohup uv run swing --settings config/live.yaml research run --windows short,long -s <slug> > /dev/null 2>&1 &`
   It copies the live store per lane, replays, and rebuilds the cards and leaderboard over that run's stores
   (`swing research rebuild` repeats the rebuild). For each grid point other than the settings default, run a
   separate `research run` with a settings file that extends config/live.yaml and sets the params: the replay ledger
   upserts by (strategy, symbol, as_of), so two param sets in one store overwrite each other.
4. Read the result: `docs/leaderboard.md` (survivors) and the card's `## Empirical (replay)` section. The haircut uses
   max(logged trials, strategies x 3 horizons x 2 windows). A survivor has a positive haircut Sharpe at the same
   horizon in BOTH windows, net of per-stock spread costs, with R graded on planned risk and stops under the 0.25%
   floor dropped. The leaderboard of a `-s <slug>` run only covers that run's strategies: compare its trial count
   with the full board's before calling anything a survivor.
5. Verdict. Not a survivor: record it in the card and stop. Do not widen the grid, change the horizon or swap filters
   to rescue it; that is a new hypothesis and more trials. Survivor: run the walk-forward skill. For a published
   predictor, also do the manual Chen-Zimmermann check (gates.md gate 2). Plan on at most half the published edge.

## Never
- Report a number that `research/` code did not compute. Claude interprets; the metrics come from `research.metrics`,
  `research.leaderboard` and `research.cards`.
- Use `swing_engine/agent/strategy_lab.py`'s Opus path without Jack's OK. It is a paid API call, and
  `agent.llm_enabled` is false in `config/live.yaml` (free tiers only). Do the loop in this session instead.
- Enable anything. `config/live.yaml` changes go through the weekly-review skill.
