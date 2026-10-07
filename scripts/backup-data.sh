#!/usr/bin/env bash
# Back up the engine's state: data/*.duckdb, data/events.sqlite, state/orders.sqlite, state/limits.json,
# data/trials.jsonl, data/journal/ and data/runs/.  Usage:
#   scripts/backup-data.sh [DEST_DIR] [--keep N]
# DEST_DIR defaults to data/backups; each run writes DEST_DIR/<UTC timestamp>/ and keeps the newest N (default 14).
#
# SQLite files are copied with the online backup API (`sqlite3 .backup`), which is safe while the monitor is
# writing (WAL mode). DuckDB is single-writer and has no online backup from the shell, so the .duckdb file is
# copied with cp; run this when the nightly job is not running (it is the only DuckDB writer; the monitor only
# reads the store at start-up). The script refuses the DuckDB copy if a swing process has the file open.
set -euo pipefail

DEFAULT_KEEP=14

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

dest_root="data/backups"
keep=$DEFAULT_KEEP
while [ "$#" -gt 0 ]; do
  case "$1" in
    --keep) keep="$2"; shift ;;
    -h|--help) sed -n '2,5p' "$0"; exit 0 ;;
    *) dest_root="$1" ;;
  esac
  shift
done
if ! [[ "$keep" =~ ^[0-9]+$ ]] || [ "$keep" -lt 1 ]; then
  echo "backup-data: --keep must be a positive integer" >&2
  exit 2
fi

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
dest="$dest_root/$stamp"
mkdir -p "$dest"

copy_sqlite() {
  # $1 = source db; uses the online backup API when the sqlite3 CLI exists, else a plain copy of db + wal.
  local src="$1"
  [ -f "$src" ] || return 0
  if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$src" ".backup '$dest/$(basename "$src")'"
  else
    cp -p "$src" "$dest/"
    [ -f "$src-wal" ] && cp -p "$src-wal" "$dest/"
  fi
  echo "  sqlite  $src"
}

copy_duckdb() {
  local src="$1"
  [ -f "$src" ] || return 0
  if command -v lsof >/dev/null 2>&1 && lsof -t -- "$src" >/dev/null 2>&1; then
    echo "backup-data: $src is open by another process (nightly running?); skipping the DuckDB copy" >&2
    return 0
  fi
  cp -p "$src" "$dest/"
  [ -f "$src.wal" ] && cp -p "$src.wal" "$dest/"
  echo "  duckdb  $src"
}

echo "backup-data: writing $dest"
for f in data/*.duckdb; do copy_duckdb "$f"; done
copy_sqlite data/events.sqlite
copy_sqlite state/orders.sqlite
for f in state/limits.json data/trials.jsonl data/ranker.pkl; do
  if [ -f "$f" ]; then cp -p "$f" "$dest/"; echo "  file    $f"; fi
done
for d in data/journal data/runs; do
  if [ -d "$d" ]; then
    mkdir -p "$dest/$(basename "$d")"
    cp -Rp "$d"/. "$dest/$(basename "$d")/"
    echo "  dir     $d"
  fi
done

# Prune to the newest $keep timestamped directories.
count=0
while IFS= read -r old; do
  count=$((count + 1))
  if [ "$count" -gt "$keep" ]; then
    rm -rf "$old"
    echo "  pruned  $old"
  fi
done < <(find "$dest_root" -mindepth 1 -maxdepth 1 -type d -name '*T*Z' | sort -r)

du -sh "$dest" | awk '{print "backup-data: done, " $1}'
