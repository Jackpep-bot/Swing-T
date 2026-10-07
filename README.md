# swing-engine

A personal swing-trading engine: nightly data ingest and feature pipeline, pluggable strategies, walk-forward
backtests with trial-count-aware (deflated) Sharpe, a ranking model, a Claude analyst layer that reviews
candidates and writes the journal, an always-on live monitor (news, SEC filings, halts, bar triggers, a small-cap
runner track) that pushes alerts to your phone, and a paper-trading executor on Alpaca with hard risk limits.

Hard rule everywhere: the language model never produces a number that reaches an order. See `CLAUDE.md`.

## Quick start (no API keys needed)
```bash
cp .env.example .env                       # fill in keys you have; everything degrades gracefully without them
uv sync --extra dev
uv run swing status                        # configured providers/keys, store counts, registered plugins
uv run swing doctor                        # offline pre-flight: .env keys, settings, store, calendar, plugins, versions
uv run swing ingest --provider sample      # ~60 synthetic symbols, 5 years, instant (--mode auto|grouped|per-symbol)
uv run swing features                      # build the 64-column feature panel into DuckDB
uv run swing scan --as-of 2026-09-30       # run enabled strategies, save signals
uv run swing backtest pullback_trend --provider sample --start 2022-01-01
uv run swing backtest rsi2_meanrev   --provider sample --start 2022-01-01
uv run swing rank train                    # cross-sectional ranker (LightGBM, or scikit-learn fallback)
uv run swing size --as-of 2026-09-30 --equity 50000          # 1% risk sizing + reward:risk floor + caps
uv run swing paper --broker paper_sim --as-of 2026-09-30 --approve "your name"   # refuses without --approve
uv run swing nightly --provider sample --as-of 2026-09-30 --dry-run   # the whole chain in one command, timed per step
uv run swing nightly --provider sample --as-of 2026-09-30 --broker paper_sim --execute
                                           # same chain plus positions -> execute: the autopilot submits through the
                                           # in-memory paper simulator (review calls Claude if ANTHROPIC_API_KEY is set)
uv run swing autopilot --as-of 2026-09-30 --broker paper_sim --dry-run   # size -> positions -> execute plan from saved signals
uv run swing monitor run --dry-run         # replays a fixture feed through rules -> alerts, then exits
uv run swing monitor rate <event_id> useful   # rate an alert: useful | noise | traded (same as the Telegram buttons)
uv run swing monitor outcomes --days 30    # forward returns after each logged alert (+5m .. +20d)
uv run swing review --dry-run              # prints the Claude review prompt without calling the API
uv run pytest -q                           # ~850 tests, no network
```
Create `state/KILL` to block every order path (the autopilot refuses entries, exits and cancels); delete it to
resume. Re-running a nightly or autopilot for the same date is safe: orders are idempotent on `client_order_id`
(`state/orders.sqlite`) and `execution.max_new_orders_per_day` counts across runs.

## Going live with real data (paper account)
Step-by-step account setup, the command order and a failure/fix table live in `docs/SETUP.md`; the daily
routine in `docs/OPERATIONS.md`; launchd/systemd units and install scripts in `deploy/`. `swing doctor --live`
probes every vendor whose key is set (`--send-test` also pushes one Telegram message).
1. Massive (ex-Polygon) free key -> `MASSIVE_API_KEY`; `swing ingest --provider massive`. With no symbols and an
   empty `universe.static_symbols` it runs in grouped mode: one call per session for the whole US market, so the
   free tier (5 calls/min, 12 s per call) backfills its 2 years in about 1 h 40 min, resumably, and the nightly
   refresh costs ~2 calls. `--symbols AAPL,MSFT` (or `--mode per-symbol`) fetches one call per symbol instead.
2. Alpaca paper keys -> `ALPACA_API_KEY/SECRET`, keep `ALPACA_PAPER=true`. As shipped (`execution.broker: alpaca`,
   `nightly_execute: true`) the nightly auto-executes on the paper account: it reconciles, manages open positions
   and submits at most `execution.max_new_orders_per_day` bracket orders approved as `autopilot:paper`.
   `--no-execute` plans only; `swing paper --broker alpaca --approve NAME` stays the manual path. A live account is
   never auto-traded unless both `execution.auto_submit_live: true` and `SWING_ALLOW_LIVE=yes` are set (and the
   gates in `docs/gates.md` pass); otherwise the plan is staged to `data/runs/pending/<date>.json`.
3. Telegram bot token + chat id (and optionally Pushover) for alerts; `swing monitor run`. P2/P3 alerts carry
   Useful / Noise / Traded buttons; presses are recorded by the running monitor (`swing monitor rate` does the same).
4. `ANTHROPIC_API_KEY` for `swing review` (Sonnet; in the nightly it can veto entries), the monitor's Haiku
   classifier, and the strategy lab.

## Extending it with Claude Code
Open this folder in Claude Code and use the skills in `.claude/skills/`: `add-strategy`, `backtest`, `add-feed`,
`tune-monitor`, `research-loop`. Every strategy, data provider, feed, rule, broker and deliverer is a plugin
registered through `swing_engine/core/registry.py`; see `docs/api-contract.md` and `docs/feature-contract.md`.

## Docs
`docs/research-architecture.md` (vendors, prices, methodology), `docs/research-monitor.md` (feeds, rules, alert
policy), `docs/smallcap-spec.md` (runner / pump track), `docs/sources-schwab-massive.md`, `docs/methods.md`
(swing-methods work-up), `docs/gates.md` (what must be true before live money), `docs/SETUP.md`,
`docs/OPERATIONS.md`, `deploy/README.md`, `docs/STATUS.md`.
