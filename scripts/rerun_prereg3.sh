#!/bin/zsh
# Amendment 1 rerun of the pre-registered group on the existing research copy (no store rebuild).
cd /Users/personal/Desktop/swing-engine
LOG=data/logs/research
for slug in ath_trend_following_wide_stop composite_cost_aware_rank earnings_seasonality; do
  for w in "2024-10-07 2026-10-05" "2017-01-01 2024-10-04"; do
    set -- ${=w}
    echo "=== $slug $1 $(date +%H:%M) ==="
    uv run swing --settings config/prereg3.yaml replay --start $1 --end $2 --no-router -s $slug --tag prereg3-$slug > $LOG/prereg3_${slug}_$1.log 2>&1; echo "exit $?"
  done
done
uv run python -m swing_engine.research.prereg_eval --settings config/prereg3.yaml
echo "PREREG3 DONE $(date +%H:%M)"
