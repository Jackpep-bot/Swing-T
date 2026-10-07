#!/usr/bin/env bash
# Nightly pipeline runner for launchd / systemd. Prefers `swing nightly`; on a build that does not have that
# command yet it runs the same chain step by step (ingest -> features -> scan -> rank -> size -> review -> journal).
# It never submits orders: `swing paper` needs a human `--approve` and is run by hand (docs/OPERATIONS.md).
# Optional environment:
#   HEALTHCHECKS_URL    healthchecks.io ping URL ("/start" before, "" on success, "/fail" on error)
#   SWING_NIGHTLY_ARGS  extra arguments passed to `swing nightly` (word-split on purpose)
#   SWING_INGEST_ARGS   extra arguments for the fallback `swing ingest` step, e.g. "--provider massive"
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
mkdir -p data/logs

ping_hc() {
  if [ -n "${HEALTHCHECKS_URL:-}" ]; then
    curl -fsS -m 10 --retry 3 -o /dev/null "${HEALTHCHECKS_URL}$1" || true
  fi
}

fail() {
  echo "run-nightly: $*" >&2
  ping_hc "/fail"
  exit 1
}

if [ ! -f .env ]; then
  fail "$repo_dir/.env is missing; copy .env.example and fill in keys (docs/SETUP.md)"
fi
if ! command -v uv >/dev/null 2>&1; then
  fail "uv not on PATH ($PATH); install from https://docs.astral.sh/uv/"
fi
if [ -e state/KILL ]; then
  # The kill switch only blocks orders, but a tripped switch means a human is handling an incident;
  # keep data fresh but say so loudly in the log.
  echo "run-nightly: state/KILL is present; pipeline runs, no orders are possible" >&2
fi

ping_hc "/start"
started=$(date +%s)
echo "run-nightly: start $(date -u +%FT%TZ) in $repo_dir"

if uv run swing nightly --help >/dev/null 2>&1; then
  # shellcheck disable=SC2086  # SWING_NIGHTLY_ARGS is intentionally word-split
  uv run swing nightly ${SWING_NIGHTLY_ARGS:-} || fail "swing nightly exited $?"
else
  echo "run-nightly: this build has no 'swing nightly'; running the chain step by step" >&2
  # Same stages as ops.nightly; here `review` runs before `size` because the CLI's `swing size` applies the
  # saved reviews as a filter, and `size --broker alpaca` reads equity from the paper account.
  # shellcheck disable=SC2086  # SWING_INGEST_ARGS is intentionally word-split
  uv run swing ingest ${SWING_INGEST_ARGS:-} || fail "ingest failed"
  uv run swing features || fail "features failed"
  uv run swing scan || fail "scan failed"
  if [ -f data/ranker.pkl ]; then
    uv run swing rank predict || echo "run-nightly: rank predict failed; continuing" >&2
  fi
  # review needs ANTHROPIC_API_KEY; without it `size` sizes every signal (reviews only filter).
  if grep -Eq '^ANTHROPIC_API_KEY=[^[:space:]#]' .env; then
    uv run swing review || echo "run-nightly: review failed; continuing without reviews" >&2
  fi
  uv run swing size --broker alpaca || fail "size failed"
  uv run swing journal || echo "run-nightly: journal failed; continuing" >&2
fi

echo "run-nightly: done in $(( $(date +%s) - started )) s"
ping_hc ""
