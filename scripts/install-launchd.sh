#!/usr/bin/env bash
# Install (or re-install) the swing-engine LaunchAgents for the current macOS user. Idempotent, no sudo.
#
#   scripts/install-launchd.sh [--monitor] [--nightly] [--hour H] [--minute M]
#                              [--hc-monitor URL] [--hc-nightly URL] [--dry-run]
#
# With neither --monitor nor --nightly both agents are installed. --dry-run renders the plists to stdout
# and validates them with plutil without touching ~/Library/LaunchAgents or launchd.
#
# What it does for each agent:
#   1. fills the @@PLACEHOLDERS@@ in deploy/launchd/<label>.plist (repo dir, uv dir, HOME, schedule, pings)
#   2. writes ~/Library/LaunchAgents/<label>.plist (0644) and validates it with plutil
#   3. launchctl bootout (if loaded) then bootstrap + enable, so re-running picks up changes
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
agents_dir="$HOME/Library/LaunchAgents"
template_dir="$repo_dir/deploy/launchd"
domain="gui/$(id -u)"

DEFAULT_HOUR=6      # 06:30 ET weekdays: before the nightly files land and well before the 08:30 digest
DEFAULT_MINUTE=30
ET_ZONE="America/New_York"

want_monitor=0
want_nightly=0
dry_run=0
hour=$DEFAULT_HOUR
minute=$DEFAULT_MINUTE
hc_monitor=""
hc_nightly=""

usage() { sed -n '2,15p' "$0"; exit "${1:-0}"; }

while [ "$#" -gt 0 ]; do
  case "$1" in
    --monitor) want_monitor=1 ;;
    --nightly) want_nightly=1 ;;
    --hour) hour="$2"; shift ;;
    --minute) minute="$2"; shift ;;
    --hc-monitor) hc_monitor="$2"; shift ;;
    --hc-nightly) hc_nightly="$2"; shift ;;
    --dry-run) dry_run=1 ;;
    -h|--help) usage 0 ;;
    *) echo "unknown argument: $1" >&2; usage 2 ;;
  esac
  shift
done
if [ "$want_monitor" -eq 0 ] && [ "$want_nightly" -eq 0 ]; then
  want_monitor=1
  want_nightly=1
fi

case "$(uname -s)" in
  Darwin) ;;
  *) echo "install-launchd: launchd is macOS only; use deploy/systemd on Linux" >&2; exit 1 ;;
esac
if ! [[ "$hour" =~ ^[0-9]+$ && "$hour" -le 23 && "$minute" =~ ^[0-9]+$ && "$minute" -le 59 ]]; then
  echo "install-launchd: --hour must be 0-23 and --minute 0-59" >&2
  exit 2
fi

uv_bin="$(command -v uv || true)"
if [ -z "$uv_bin" ]; then
  echo "install-launchd: uv not found on PATH; install it first (https://docs.astral.sh/uv/)" >&2
  exit 1
fi
uv_dir="$(dirname "$uv_bin")"

if [ ! -f "$repo_dir/.env" ]; then
  echo "install-launchd: warning: $repo_dir/.env is missing; the agents will exit until it exists" >&2
fi

# launchd evaluates StartCalendarInterval in the machine's local zone; warn when that is not ET.
local_zone="$(readlink /etc/localtime 2>/dev/null | sed 's#.*/zoneinfo/##' || true)"
if [ "$want_nightly" -eq 1 ] && [ "$local_zone" != "$ET_ZONE" ]; then
  echo "install-launchd: warning: this Mac's time zone is '${local_zone:-unknown}', not $ET_ZONE." >&2
  echo "  The nightly job fires at ${hour}:$(printf '%02d' "$minute") LOCAL time. Pass --hour/--minute to match 06:30 ET." >&2
fi

render() {
  # $1 = template path. Placeholders are replaced with sed; '|' is the delimiter so paths may contain '/'.
  # The schedule is rewritten from the template's literal defaults (Hour 6 / Minute 30) so the template stays
  # a valid plist on its own.
  sed \
    -e "s|@@REPO_DIR@@|$repo_dir|g" \
    -e "s|@@UV_DIR@@|$uv_dir|g" \
    -e "s|@@HOME@@|$HOME|g" \
    -e "s|<key>Hour</key><integer>$DEFAULT_HOUR</integer>|<key>Hour</key><integer>$hour</integer>|g" \
    -e "s|<key>Minute</key><integer>$DEFAULT_MINUTE</integer>|<key>Minute</key><integer>$minute</integer>|g" \
    -e "s|@@HEALTHCHECKS_MONITOR_URL@@|$hc_monitor|g" \
    -e "s|@@HEALTHCHECKS_NIGHTLY_URL@@|$hc_nightly|g" \
    "$1"
}

install_agent() {
  # $1 = label
  local label="$1"
  local template="$template_dir/$label.plist"
  local target="$agents_dir/$label.plist"
  if [ ! -f "$template" ]; then
    echo "install-launchd: missing template $template" >&2
    exit 1
  fi
  if [ "$dry_run" -eq 1 ]; then
    echo "----- $target (dry run) -----"
    render "$template" | tee /dev/stderr | plutil -lint - >/dev/null
    return
  fi
  mkdir -p "$agents_dir" "$repo_dir/data/logs"
  local tmp
  tmp="$(mktemp "$agents_dir/.$label.XXXXXX")"
  render "$template" > "$tmp"
  plutil -lint "$tmp" >/dev/null
  chmod 0644 "$tmp"
  mv -f "$tmp" "$target"
  # Unload a previous copy (ignore "not loaded"), then load the new one.
  launchctl bootout "$domain/$label" >/dev/null 2>&1 || true
  launchctl bootstrap "$domain" "$target"
  launchctl enable "$domain/$label"
  echo "installed $label -> $target"
}

[ "$want_monitor" -eq 1 ] && install_agent com.swing.monitor
[ "$want_nightly" -eq 1 ] && install_agent com.swing.nightly

if [ "$dry_run" -eq 0 ]; then
  echo
  echo "status:   launchctl print $domain/com.swing.monitor | head -20"
  echo "logs:     tail -f $repo_dir/data/logs/monitor.err.log"
  echo "run now:  launchctl kickstart -k $domain/com.swing.nightly"
  echo "remove:   scripts/uninstall-launchd.sh"
fi
