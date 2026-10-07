#!/usr/bin/env bash
# Common developer commands for swing-engine. Usage: scripts/dev.sh <task> [extra args]
# Everything runs through `uv run` from the repo root; no network is needed for test/lint/status/sample.
set -euo pipefail
cd "$(dirname "$0")/.."

task="${1:-help}"
if [ "$#" -gt 0 ]; then shift; fi

case "$task" in
  test)      uv run pytest -q "$@" ;;
  test-cli)  uv run pytest -q tests/test_cli.py "$@" ;;
  lint)      uv run ruff check . "$@" ;;
  fmt)       uv run ruff format . && uv run ruff check --fix . ;;
  check)     uv run ruff check . && uv run pytest -q ;;
  status)    uv run swing status "$@" ;;
  sample)    uv run swing ingest --provider sample "$@" && uv run swing features ;;
  ingest)    uv run swing ingest "$@" ;;
  features)  uv run swing features "$@" ;;
  scan)      uv run swing scan "$@" ;;
  backtest)  uv run swing backtest "$@" ;;
  review)    uv run swing review --dry-run "$@" ;;
  monitor)   uv run swing monitor run --dry-run "$@" ;;
  report)    uv run swing monitor report "$@" ;;
  trials)    uv run swing trials "$@" ;;
  kill)      mkdir -p state && touch state/KILL && echo "kill switch SET: state/KILL blocks all orders" ;;
  unkill)    rm -f state/KILL && echo "kill switch cleared" ;;
  help|*)
    cat <<'USAGE'
scripts/dev.sh <task> [args]
  test        run the whole test suite            (uv run pytest -q)
  test-cli    run only the CLI tests
  lint        ruff check .
  fmt         ruff format . && ruff check --fix .
  check       lint + tests
  status      swing status (keys, store, plugins; no network)
  sample      ingest the synthetic `sample` provider, then build the feature panel
  ingest      swing ingest [--provider ...] [--start ...] [--end ...] [--symbols ...]
  features    swing features
  scan        swing scan [--as-of YYYY-MM-DD] [-s strategy]
  backtest    swing backtest <strategy> [--start ...] [--param k=v]
  review      swing review --dry-run (prints the prompt; no API call)
  monitor     swing monitor run --dry-run
  report      swing monitor report [--days N]
  trials      swing trials
  kill        create state/KILL (blocks every order)
  unkill      remove state/KILL
USAGE
    ;;
esac
