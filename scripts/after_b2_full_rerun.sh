#!/bin/zsh
# After the batch 2 group: re-run the full leaderboard on the live store now that the splits table is complete
# (universe screened on true as-traded prices). swing research run sizes lanes to memory and pushes to Telegram.
cd /Users/personal/Desktop/swing-engine
until grep -q "PREREG GROUP DONE\|Traceback" data/logs/research/prereg_b2.log; do sleep 60; done
uv run python -c "
from pathlib import Path
from swing_engine.ops.notify import deliver, truncate
p = Path('docs/preregistration/2026-10-10-batch2-results.md')
deliver('Batch 2 pre-registered group: results', truncate(p.read_text() if p.exists() else 'no results file (see data/logs/research/prereg_b2.log)'))
"
uv run swing --settings config/live.yaml research run --windows short,long --allow-battery
echo "FULL RERUN DONE $(date +%H:%M)"
