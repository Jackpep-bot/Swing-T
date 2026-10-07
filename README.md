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
uv run swing ingest --provider sample      # ~60 synthetic symbols, 5 years, instant
uv run swing features                      # build the 64-column feature panel into DuckDB
uv run swing scan --as-of 2026-09-30       # run enabled strategies, save signals
uv run swing backtest pullback_trend --provider sample --start 2022-01-01
uv run swing backtest rsi2_meanrev   --provider sample --start 2022-01-01
uv run swing rank train                    # cross-sectional ranker (LightGBM, or scikit-learn fallback)
uv run swing size --as-of 2026-09-30 --equity 50000          # 1% risk sizing + reward:risk floor + caps
uv run swing paper --broker paper_sim --as-of 2026-09-30 --approve "your name"   # refuses without --approve
uv run swing monitor run --dry-run         # replays a fixture feed through rules -> alerts, then exits
uv run swing review --dry-run              # prints the Claude review prompt without calling the API
uv run pytest -q                           # 597 tests, no network
```
Create `state/KILL` to block every order path; delete it to resume.

## Going live with real data (paper account)
1. Massive (ex-Polygon) free key -> `MASSIVE_API_KEY`; `swing ingest --provider massive --symbols AAPL,MSFT,...`.
2. Alpaca paper keys -> `ALPACA_API_KEY/SECRET`, keep `ALPACA_PAPER=true`; `swing paper --broker alpaca ...`.
   Live trading additionally requires `SWING_ALLOW_LIVE=yes` and is blocked until the gates in `docs/gates.md` pass.
3. Telegram bot token + chat id (and optionally Pushover) for alerts; `swing monitor run`.
4. `ANTHROPIC_API_KEY` for `swing review` (Sonnet), the monitor's Haiku classifier, and the strategy lab.

## Extending it with Claude Code
Open this folder in Claude Code and use the skills in `.claude/skills/`: `add-strategy`, `backtest`, `add-feed`,
`tune-monitor`, `research-loop`. Every strategy, data provider, feed, rule, broker and deliverer is a plugin
registered through `swing_engine/core/registry.py`; see `docs/api-contract.md` and `docs/feature-contract.md`.

## Docs
`docs/research-architecture.md` (vendors, prices, methodology), `docs/research-monitor.md` (feeds, rules, alert
policy), `docs/smallcap-spec.md` (runner / pump track), `docs/sources-schwab-massive.md`, `docs/methods.md`
(swing-methods work-up), `docs/gates.md` (what must be true before live money), `docs/STATUS.md`.
