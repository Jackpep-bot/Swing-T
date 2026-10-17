#!/bin/zsh
# Small-cap edge map (docs/preregistration/2026-10-13-smallcap-map.md). Power is scripts/on_power.sh's job (starts on
# AC or a charged battery, pauses on a low one). Replays every strategy on config/research_smallcap.yaml for 2024-26
# without touching the main leaderboard, writes docs/edge_map_smallcap.md and sends its top to Telegram. Run detached:
#   nohup scripts/on_power.sh scripts/run_smallcap_map.sh > data/logs/research/smallcap_map.log 2>&1 &
cd /Users/personal/Desktop/swing-engine
# 4 lanes: a 2024-26 replay of 16 strategies on this universe held 3.1 GB (measured 2026-10-13); auto sizes for 2017-24
uv run swing --settings config/research_smallcap.yaml research run --windows short --no-rebuild --allow-battery --lanes ${LANES:-4} || echo "RUN FAILED (resume: swing --settings config/research_smallcap.yaml research run --resume latest --no-rebuild)"
uv run python - <<'PY'
import json, sys
from pathlib import Path
from swing_engine.research import edge_map
from swing_engine.ops.notify import deliver, truncate
m = json.loads(sorted(Path("data/live/runs/research").glob("*.json"))[-1].read_text())
if "research_smallcap" not in m["settings"] or any(c["status"] != "done" for c in m["chunks"]):
    deliver("Small-cap map: run incomplete", f"run {m['run_id']}: " + ", ".join(f"{c['tag']}={c['status']}" for c in m["chunks"] if c["status"] != "done"))
    sys.exit(1)
lanes = m["lanes"]
edge_map.main(["--settings", lanes[0]["settings"], *[a for lane in lanes[1:] for a in ("--store", lane["store"])],
               "--tag", ".small", "--windows", "2024-10-07:2025-10-03,2025-10-06:2026-10-05",
               "--out", "docs/edge_map_smallcap.md",
               "--note", "Universe: config/research_smallcap.yaml (the 2,500 stocks after the 1,500 most liquid). "
                         "Windows: the two halves of 2024-10-07 .. 2026-10-05. Pre-registered in "
                         "docs/preregistration/2026-10-13-smallcap-map.md."])
text = Path("docs/edge_map_smallcap.md").read_text()
deliver("Small-cap edge map done", truncate(text[text.index("## All strategies pooled"):]))
PY
echo "SMALLCAP MAP DONE $(date '+%F %H:%M')"
