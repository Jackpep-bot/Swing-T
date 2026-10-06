# swing-engine

Research, live-monitoring and paper-execution engine for US-equity swing trading, with Claude as the
analyst/strategy-iteration layer. Owner is learning swing trading; this repo is designed to be extended
by Claude Code sessions (see `.claude/skills/`).

## Non-negotiable rules
1. The LLM never emits a price, share count, stop, target, or statistic that reaches an order. Those come
   from `risk/` and `strategies/` code. Claude returns enums and short text (`core/models.py: Review`,
   `Classification`).
2. Paper trading only (`ALPACA_PAPER=true`) until the gate in `docs/gates.md` is met. Never put live keys in
   `.env` from a Claude session.
3. Point-in-time discipline: every feature uses only data available on `as_of`; filings are timestamped on
   filing/upload date, never transaction date; delisted symbols stay in the universe.
4. Every strategy/rule threshold is a versioned constant or a `settings.yaml` param, never a magic number.
5. Order tools require a human approval; a kill-switch file (`state/KILL`) blocks all orders.

## Layout
- `swing_engine/core` contracts (models, interfaces, registry, config). Do not import other packages here.
- `swing_engine/data` bar/reference providers (massive, eodhd, alpaca, sample) + EDGAR/Quiver/alt-data + ingest.
- `swing_engine/features` indicators, cross-sectional features, pattern detectors, regime.
- `swing_engine/strategies` one module per setup; registered with `@register("strategy")`.
- `swing_engine/research` backtest (walk-forward), metrics (deflated Sharpe), ML ranker, trial log.
- `swing_engine/risk` sizing, limits, kill switch. `execution` broker adapters (alpaca paper) + order manager.
- `swing_engine/monitor` live service: feeds -> dedup -> matcher -> rules -> Haiku classify -> alerts.
- `swing_engine/agent` Claude layer: candidate review, journal, strategy lab.
- `swing_engine/cli.py` `swing <command>`; `tests/` pytest; `docs/` research summaries and decisions.

## Dev
- `uv sync --extra dev` then `uv run swing --help`, `uv run pytest`, `uv run ruff check .`
- No network in tests: use `sample` provider and fixtures under `tests/fixtures`.
- Python 3.12. Do not edit `pyproject.toml` dependencies without noting it in the PR/summary.

## Where the knowledge lives
- `docs/research-architecture.md` verified vendor facts, prices, limits (Oct 2026).
- `docs/research-monitor.md` live-feed facts, stage-1 rules, alert policy.
- `docs/methods.md` swing methods work-up (filled in as research completes).
