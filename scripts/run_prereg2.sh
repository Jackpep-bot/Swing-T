#!/bin/zsh
# Pre-registered two-pick group (docs/preregistration/2026-10-10-two-picks.md).
cd /Users/personal/Desktop/swing-engine
LOG=data/logs/research
cp data/live/replay_p3.duckdb data/live/replay_p2.duckdb
for slug in high_volume_return_premium momentum_volume_early_stage; do
  for w in "2024-10-07 2026-10-05" "2017-01-01 2024-10-04"; do
    set -- ${=w}
    echo "=== $slug $1 $(date +%H:%M) ==="
    uv run swing --settings config/prereg2.yaml replay --start $1 --end $2 --no-router -s $slug --tag prereg2-$slug > $LOG/prereg2_${slug}_$1.log 2>&1; echo "exit $?"
  done
done
uv run python -m swing_engine.research.prereg_eval --settings config/prereg2.yaml --slugs high_volume_return_premium,momentum_volume_early_stage --tag-prefix prereg2- --n-trials 2 --out docs/preregistration/2026-10-10-two-picks-results.md
echo "PREREG2 DONE $(date +%H:%M)"
