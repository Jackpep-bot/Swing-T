#!/usr/bin/env bash
# Run the live monitor in the foreground; used by launchd (deploy/launchd) and systemd (deploy/systemd).
# Secrets come from <repo>/.env (read by the app, never by this script). Optional:
#   HEALTHCHECKS_URL   healthchecks.io ping URL; "/start" is sent before launch and "/fail" if the
#                      process exits non-zero (the supervisor restarts it either way).
#   SWING_MONITOR_ARGS extra arguments, e.g. "--feeds alpaca_news,edgar" (word-split on purpose).
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
mkdir -p data/logs

ping_hc() {
  # $1 = suffix ("/start", "/fail", "" for success); silent no-op when HEALTHCHECKS_URL is unset.
  if [ -n "${HEALTHCHECKS_URL:-}" ]; then
    curl -fsS -m 10 --retry 3 -o /dev/null "${HEALTHCHECKS_URL}$1" || true
  fi
}

if [ ! -f .env ]; then
  echo "run-monitor: $repo_dir/.env is missing; copy .env.example and fill in keys (docs/SETUP.md)" >&2
  exit 78  # EX_CONFIG
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "run-monitor: uv not on PATH ($PATH); install from https://docs.astral.sh/uv/" >&2
  exit 69  # EX_UNAVAILABLE
fi

ping_hc "/start"
# shellcheck disable=SC2086  # SWING_MONITOR_ARGS is intentionally word-split
if uv run swing monitor run ${SWING_MONITOR_ARGS:-}; then
  ping_hc ""
else
  rc=$?
  ping_hc "/fail"
  exit "$rc"
fi
