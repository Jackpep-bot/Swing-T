#!/bin/zsh
# Replay the event strategies that need no news data (13D drift, avoid-4.02) in both windows.
cd /Users/personal/Desktop/swing-engine
LOG=data/logs/research
for w in "2024-10-07 2026-10-05" "2017-01-01 2024-10-04"; do
  set -- ${=w}
  echo "=== events $1 $(date +%H:%M) ==="
  uv run swing --settings config/replay_events.yaml replay --start $1 --end $2 --no-router -s activist_13d_drift,pullback_trend_avoid_402 --tag v2c-events > $LOG/events_$1.log 2>&1; echo "exit $?"
done
echo "EVENTS DONE $(date +%H:%M)"
