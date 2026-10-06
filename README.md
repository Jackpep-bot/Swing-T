# swing-engine

A personal swing-trading engine: nightly data ingest and feature pipeline, pluggable strategies, walk-forward
backtests, a LightGBM ranking model, a Claude analyst layer that reviews candidates and writes the journal, an
always-on live monitor (news, SEC filings, halts, bar triggers, social) that pushes alerts to your phone, and a
paper-trading executor on Alpaca with hard risk limits.

Status: scaffold. See `CLAUDE.md` for rules and layout, `docs/` for the research behind the design.

## Quick start
```bash
cp .env.example .env            # fill keys you have; everything degrades gracefully without them
uv sync --extra dev
uv run swing status             # shows which providers/keys are configured
uv run swing ingest --provider sample   # synthetic data, no keys needed
uv run swing scan --as-of 2026-10-03
uv run swing backtest pullback_trend --start 2021-01-01
uv run swing monitor --dry-run
```
