#!/bin/zsh
# After the news ingest: copy the live store and replay the three no-news mean-reversion variants in both windows,
# then rebuild cards and the leaderboard over every v2 research store.
cd /Users/personal/Desktop/swing-engine
LOG=data/logs/research
until grep -q "NEWS DONE" data/logs/ingest-news.log; do sleep 60; done
cp data/live/market.duckdb data/live/replay_news.duckdb
uv run python -c "import duckdb; c=duckdb.connect('data/live/replay_news.duckdb'); c.execute('delete from shadow_signals_replay'); c.close()"
S=connors_rsi2_variants_no_news,connors_tps_scale_in_no_news,connors_hpetf_rsi_variants_no_news
for w in "2024-10-07 2026-10-05" "2017-01-01 2024-10-04"; do
  set -- ${=w}
  echo "=== news variants $1 $(date +%H:%M) ==="
  uv run swing --settings config/replay_news.yaml replay --start $1 --end $2 --no-router -s $S --tag v2c-news > $LOG/news_$1.log 2>&1; echo "exit $?"
done
A=(--settings config/replay_r2.yaml --store data/live/replay_r1.duckdb --store data/live/replay_p3.duckdb --store data/live/replay_news.duckdb)
uv run python -m swing_engine.research.leaderboard $A
uv run python -m swing_engine.research.cards $A
echo "NEWS REPLAYS DONE $(date +%H:%M)"
