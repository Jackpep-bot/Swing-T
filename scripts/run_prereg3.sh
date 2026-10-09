#!/bin/zsh
# Pre-registered three-pick group (docs/preregistration/2026-10-09-three-picks.md): runs after any live-store writer.
cd /Users/personal/Desktop/swing-engine
LOG=data/logs/research
mkdir -p $LOG
while pgrep -f "[i]ngest-edgar" >/dev/null; do sleep 30; done
echo "rebuild events on live $(date +%H:%M)"
uv run python -c "from swing_engine.data.store import Store; from swing_engine.data import fundamentals as F; s=Store('data/live/market.duckdb'); print(F.build_fundamental_events(s)); s.close()"
cp data/live/market.duckdb data/live/replay_p3.duckdb
for slug in ath_trend_following_wide_stop composite_cost_aware_rank earnings_seasonality; do
  for w in "2024-10-07 2026-10-05" "2017-01-01 2024-10-04"; do
    set -- ${=w}
    echo "=== $slug $1 $(date +%H:%M) ==="
    uv run swing --settings config/prereg3.yaml replay --start $1 --end $2 --no-router -s $slug --tag prereg3-$slug > $LOG/prereg3_${slug}_$1.log 2>&1; echo "exit $?"
  done
done
uv run python -m swing_engine.research.prereg_eval --settings config/prereg3.yaml
echo "PREREG3 DONE $(date +%H:%M)"
