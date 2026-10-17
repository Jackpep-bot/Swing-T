---
name: add-strategy
description: Add a swing-trading strategy module to swing-engine from a card or plain-English rules, point-in-time and with the stop floor, register it disabled in settings, test it with the all-strategy contract, and smoke-run a backtest.
---
## Read first
`CLAUDE.md`; `swing_engine/core/interfaces.py` (Strategy, `exit_takes_position`); `swing_engine/strategies/_base.py`
(PanelStrategy, `rows_as_of`, `RollingSpec`, `build_signal`, `MIN_STOP_FRACTION`, `should_exit`, `trail_stop`,
`engine_trail`, `extra_features`); one similar module (e.g. `strategies/pullback_holy_grail.py`; param-dependent extras:
`strategies/slope_performance_trend.py`); `swing_engine/strategies/_catalog1.py` helpers; `docs/feature-contract.md`;
the top docstring of `swing_engine/features/extra.py`; `tests/test_strategies_all.py`. From the catalog: the card
`docs/strategies/<slug>.md` and the `docs/catalog/catalog.json` item (`rules_or_formula`, `decision`, `maps_to`).

## Rules to code
1. Write the rules down: universe/regime filter, entry trigger, entry type, stop, target or rule exit, max hold. Every
   threshold is a `default_params` entry with a comment citing the card. Missing numbers: ask; never invent them.
   Long only (short-only rules: skip and say so). Data the engine lacks: closest daily approximation, stated in the
   module docstring, or no module.
2. `swing_engine/strategies/<slug>.py` (no leading underscore; discovery is automatic), `NAME = "<slug>"`,
   `@register("strategy", NAME)`, subclass `PanelStrategy`. Get rows with `self.rows_as_of(...)` or
   `_catalog1.rows/view`; make every Signal with `self.build_signal(...)`, never `Signal(...)` directly.
3. Point-in-time. Use only bars dated <= `as_of`: `RollingSpec(..., prior=True)` to exclude today; no `shift(-1)`,
   centred windows, or ranks/z-scores/means over the whole panel. Calendar flags come only from the published calendar.
   The pre-holiday flags once counted ad-hoc closures (9/11, Sandy) as holidays, which was a look-ahead bug (fixed in
   features/extra.py). Fundamentals are keyed on filing or acceptance time, never the period or transaction date. A
   signal uses the `as_of` close and fills next session: `EntryType.OPEN`, or `_catalog1.stop_entry(sig)` for a buy stop
   (the live broker still refuses stop/limit entries).
4. Stop floor. `build_signal` drops a stop closer than `MIN_STOP_FRACTION` = 0.25% of entry (param `min_stop_pct`). Never
   lower it to make a strategy fire. Sub-tick stops graded at 1e10 R in the 2026-10-08 replay. A rule exit with no
   target uses `target=None` and `min_reward_risk: 0.0`.
5. Features. Panel columns go in `features_required`. `features.extra` names go in `extra_features` (check with
   `uv run python -c "from swing_engine.features.extra import is_extra; print(is_extra('ema_8'))"`). The CLI, replay and
   nightly attach only the extras that each strategy declares (`required_extras` over instances). If the names depend
   on params, set `self.extra_features` in `__init__` after `super().__init__(params)`. A class attribute alone gives the
   default names. A missing indicator goes into `features/extra.py`, point-in-time, with a test in
   `tests/test_features_extra.py`. Re-read the file just before editing it.
6. Exits. Use `should_exit(self, row, bars_held, position=None)`, where `position` is a `PositionContext`. Read it with
   `_base.entry_feature` / `entry_price`, and do not fire when a fact is None (live has no entry features). The time stop
   is the `max_hold_days` param. Use `trail_stop(row) -> float | None` for indicator trails. Set `engine_trail = False`
   when the breakeven/N-day-low overlay would cut the trade the card relies on.

## Settings
Add one line under `strategies:` in `config/settings.yaml`, with flat params and a comment:
`<slug>: {enabled: false, shadow_only: true}` for catalog decision implement/approximate, otherwise `{enabled: false}`.
Never enable a strategy, and never edit `config/live.yaml`. Enabling happens only through the weekly-review skill after
a leaderboard pass and a walk-forward pass. The playbook router sizes only strategies listed under
`playbook.regimes`, while shadow-only ones are scanned in every regime.
Parallel workers do not edit `config/settings.yaml`. Each one writes its lines to a fragment file
(`<scratchpad>/settings_batch_<n>.yaml`) and reports it, and the lead merges once. Concurrent edits collided before.

## Tests and checks
- `tests/test_strategy_<slug>.py`: hand-built panels where it must fire and must not, geometry (stop < entry, target),
  and each exit path.
- `uv run pytest -q tests/test_strategy_<slug>.py tests/test_strategies_common.py tests/test_strategy_review_rows_as_of.py`
- `uv run pytest -q tests/test_strategies_all.py -k <slug>`: a GBM panel on the NYSE calendar; signals must not change
  when the panel is truncated at `as_of`; hooks survive panel rows and a PositionContext; undeclared extras fail here.
- `uv run pytest -q` then `uv run ruff check .`. Both must be green.
- Smoke only (synthetic data, no conclusions):
  `uv run swing backtest <slug> --start 2025-01-02 --end 2025-12-31 --provider sample --no-log`.
  Real evidence comes from the backtest, walk-forward and research-loop skills, and every run there is logged.
- Update the card's "Implementation spec for swing-engine". Leave `## Empirical (replay)` to `research.cards`.
