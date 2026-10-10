#!/bin/zsh
# Alpaca news ingest into the live store, started once the pre-registered run has copied the store.
cd /Users/personal/Desktop/swing-engine
until grep -q "^=== " data/logs/research/prereg3.log; do sleep 30; done
uv run swing --settings config/live.yaml ingest-news --start 2016-01-01 > data/logs/ingest-news.log 2>&1
echo "NEWS DONE $(date +%H:%M)" >> data/logs/ingest-news.log
