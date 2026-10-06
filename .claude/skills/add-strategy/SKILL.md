---
name: add-strategy
description: Add a new swing-trading strategy module to swing-engine from a plain-English description, wire its params into settings.yaml, write tests, and run a quick backtest.
---
1. Read `swing_engine/core/interfaces.py` (Strategy) and one existing strategy (e.g. `strategies/pullback_trend.py`).
2. Translate the user's description into explicit rules: universe filter, regime filter, entry trigger, stop, target, holding period. Every threshold becomes a `default_params` entry.
3. Create `swing_engine/strategies/<name>.py` with `@register("strategy", "<name>")`, using only columns from `features/` (add a feature there if missing, with a test).
4. Add `<name>: {enabled: false}` to `config/settings.yaml`.
5. Add `tests/test_strategy_<name>.py` using the `sample` provider fixture.
6. Run `uv run pytest -q` and `uv run swing backtest <name> --start 2022-01-01 --provider sample`; report trades, win rate, profit factor, max drawdown, and the trial count logged.
Never emit numbers from the model into the strategy; derive thresholds from the description or ask.
