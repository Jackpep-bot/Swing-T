# swing-engine

A personal swing-trading engine: nightly data ingest and feature pipeline, pluggable strategies, walk-forward
backtests, a LightGBM ranking model, a Claude analyst layer that reviews candidates and writes the journal, an
always-on live monitor (news, SEC filings, halts, bar triggers, social) that pushes alerts to your phone, and a
paper-trading executor on Alpaca with hard risk limits.

Status: integrated. All modules land, `uv run pytest` is green and the sample-provider flow below runs end to end
with no keys. See `CLAUDE.md` for rules and layout, `docs/` for the research behind the design.

## Quick start (sample data, no keys)
```bash
cp .env.example .env                 # optional: fill keys you have; everything degrades gracefully without them
uv sync --extra dev
uv run swing status                  # configured keys, store counts, kill switch, registered plugins

# 1. data -> features
uv run swing ingest --provider sample            # synthetic GBM bars for 60 names (2021-10 .. 2026-09-30)
uv run swing features                           # caches the 64-column feature panel to the store table `panel`

# 2. research
uv run swing backtest pullback_trend --provider sample --start 2022-01-01
uv run swing backtest sr_breakout   --provider sample --start 2022-01-01
uv run swing trials                             # every logged run; the count feeds deflated Sharpe

# 3. daily loop (point-in-time; the sample data ends 2026-09-30)
uv run swing scan   --as-of 2026-09-30                       # screened universe -> Signals -> runs/signals/<date>.json
uv run swing review --as-of 2026-09-30 --dry-run             # prints the Claude prompt; the real call needs ANTHROPIC_API_KEY
uv run swing size   --as-of 2026-09-30 --equity 50000        # Signals -> OrderIntents (risk.sizing); reviews only filter
uv run swing paper  --as-of 2026-09-30 --broker paper_sim --approve "<your name>"   # refuses without --approve
uv run swing journal --as-of 2026-09-30                      # tables-only without a key

# 4. live monitor
uv run swing monitor run --dry-run              # replays tests/fixtures/monitor/replay_events.jsonl to the console and exits
uv run swing monitor report --days 7
uv run swing monitor replay --days 7
```

Notes
- Commands that chain through `runs/<kind>/<date>.json` (`review`, `size`, `paper`, `journal`) default `--as-of` to today;
  pass the scan date explicitly. A missing file lists the dates that do exist.
- `scan` screens the stored names with `settings.universe` as of `--as-of` (ETFs, OTC and names delisted before the date drop
  out); `backtest` keeps every name that passed the screen at either `--start` or `--end`, so delistings inside the window
  are traded and exited, not erased.
- `ingest` defaults to `history_years` before today; for backtests that start in 2022 pass `--start 2020-10-01` so the
  252-bar features are warm from day one.
- Paper only: `paper --broker alpaca` needs `ALPACA_API_KEY`/`ALPACA_SECRET_KEY` and refuses when `ALPACA_PAPER=false`
  unless `SWING_ALLOW_LIVE=yes` is also set (`docs/gates.md`). `touch state/KILL` blocks every order; `swing status` shows it.
- Real providers: set `data.bar_provider` in `config/settings.yaml` (`massive` | `eodhd` | `alpaca`) and the matching key in `.env`.
