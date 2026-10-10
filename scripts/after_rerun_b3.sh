#!/bin/zsh
# Batch 3 (prereg_run packs its jobs beside any other replay on the machine, 44GB budget): batch 3 pre-registered group, Telegram its table, then re-replay
# residual_momentum on 2024-26 with its longer warm-up (its earlier row had only 3 graded signals).
cd /Users/personal/Desktop/swing-engine
uv run python -m swing_engine.research.prereg_run --settings config/prereg_b3.yaml --book large_cap_gross_profitability=config/prereg_b3_gp.yaml --tag-prefix prereg-b3- --slugs large_cap_gross_profitability,large_cap_residual_momentum --n-trials 2 --benchmark SPY --alpha-slugs large_cap_gross_profitability,large_cap_residual_momentum --out docs/preregistration/2026-10-10-batch3-results.md > data/logs/research/prereg_b3.log 2>&1
uv run python -c "
from pathlib import Path
from swing_engine.ops.notify import deliver, truncate
p = Path('docs/preregistration/2026-10-10-batch3-results.md')
deliver('Batch 3 pre-registered group: results', truncate(p.read_text() if p.exists() else 'no results file (see data/logs/research/prereg_b3.log)'))
"
uv run swing --settings config/replay_events.yaml replay --start 2024-10-07 --end 2026-10-05 --no-router -s residual_momentum --tag v2c-resmom > data/logs/research/resmom_2024.log 2>&1
echo "B3 CHAIN DONE $(date +%H:%M)"
