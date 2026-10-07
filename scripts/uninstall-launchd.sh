#!/usr/bin/env bash
# Remove the swing-engine LaunchAgents for the current macOS user. Idempotent, no sudo.
#   scripts/uninstall-launchd.sh [--monitor] [--nightly] [--keep-files]
# With neither flag both agents are removed. --keep-files unloads them but leaves the plists in place.
set -euo pipefail

agents_dir="$HOME/Library/LaunchAgents"
domain="gui/$(id -u)"
want_monitor=0
want_nightly=0
keep_files=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --monitor) want_monitor=1 ;;
    --nightly) want_nightly=1 ;;
    --keep-files) keep_files=1 ;;
    -h|--help) sed -n '2,5p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; sed -n '2,5p' "$0"; exit 2 ;;
  esac
  shift
done
if [ "$want_monitor" -eq 0 ] && [ "$want_nightly" -eq 0 ]; then
  want_monitor=1
  want_nightly=1
fi

remove_agent() {
  local label="$1"
  local target="$agents_dir/$label.plist"
  if launchctl print "$domain/$label" >/dev/null 2>&1; then
    # bootout sends SIGTERM; the monitor drains for up to ExitTimeOut seconds before SIGKILL.
    launchctl bootout "$domain/$label" || true
    echo "unloaded $label"
  else
    echo "$label was not loaded"
  fi
  if [ "$keep_files" -eq 0 ] && [ -f "$target" ]; then
    rm -f "$target"
    echo "removed $target"
  fi
}

[ "$want_monitor" -eq 1 ] && remove_agent com.swing.monitor
[ "$want_nightly" -eq 1 ] && remove_agent com.swing.nightly
exit 0
