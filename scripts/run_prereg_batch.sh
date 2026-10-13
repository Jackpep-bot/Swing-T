#!/bin/zsh
# One pre-registered batch of single-strategy books, from replays to verdicts (batch 6 on; batch 5 keeps its own
# script). Replays every card on 2024-26, then 2017-24 for the cards that meet the rule in 2024-26 (and for
# ALWAYS_LONG), grades against SPY (and IWM for reading), refreshes docs/income_view.md and Telegrams the verdicts.
# A restart never repeats a finished or running replay (each one logs a trial). Run detached:
#   WAIT_FOR=run_batch5.sh N_TRIALS=5 BEFORE="uv run python -m swing_engine.research.vrp_overlay" \
#     nohup scripts/on_power.sh scripts/run_prereg_batch.sh b6 2026-10-13 slug1,slug2 > data/logs/research/batch6.log 2>&1 &
# $1 batch tag: config/prereg_<tag>.yaml, books config/prereg_<tag>_<slug>.yaml, replay tags prereg-<tag>-<slug>.
# $2 date of docs/preregistration/<date>-batch<N>.md (the results file is named after it). $3 slugs, comma-separated.
# Env: N_TRIALS (default: the number of slugs), WAIT_FOR (pgrep -f pattern of a run to wait for), BEFORE (a command
# run first, for a card that is not an engine strategy), ALWAYS_LONG (slugs replayed on 2017-24 whatever 2024-26
# says), GB24 / GB17 (memory budget per replay, default 6 / 30).
cd /Users/personal/Desktop/swing-engine
TAG=$1 SLUGS=$3
PREFIX=prereg-$TAG-
OUT=docs/preregistration/$2-batch${TAG#b}-results.md
N=${N_TRIALS:-${#${(s:,:)SLUGS}}}
BOOKS=()
for s in ${(s:,:)SLUGS}; do BOOKS+=(--book $s=config/prereg_${TAG}_$s.yaml); done
COMMON=(--settings config/prereg_$TAG.yaml --tag-prefix $PREFIX --n-trials $N --benchmark SPY --job-gb 2024=${GB24:-6},2017=${GB17:-30} $BOOKS)
# slugs of $1 with no finished and no running replay for the window starting in year $2
todo() {
  local out=() s
  for s in ${(s:,:)1}; do
    local done_=(data/live/runs/replay/$2-*_$PREFIX$s.json(N))
    (( $#done_ )) && continue
    pgrep -f -- "--start $2-.* --tag $PREFIX$s\$" > /dev/null || out+=($s)
  done
  echo ${(j:,:)out}
}
drain() { while pgrep -f -- "--tag $PREFIX" > /dev/null; do sleep 30; done }  # replays an earlier start left running
if [[ -n $WAIT_FOR ]]; then while pgrep -f -- "$WAIT_FOR" > /dev/null; do sleep 60; done; fi
echo "start $(date '+%F %H:%M')"
if [[ -n $BEFORE ]]; then ${=BEFORE} || echo "BEFORE FAILED: $BEFORE"; fi
uv run python -m swing_engine.research.prereg_run $COMMON --slugs "$(todo $SLUGS 2024)" --alpha-slugs $SLUGS --window-years 2024 --out $OUT --no-eval
drain
LONG=$(TAG=$TAG PREFIX=$PREFIX SLUGS=$SLUGS ALWAYS_LONG=$ALWAYS_LONG N=$N uv run python - <<'PY'
import json
import os
from pathlib import Path

import pandas as pd

from swing_engine.core.config import load_settings
from swing_engine.data.store import Store
from swing_engine.research import prereg_eval as pe
from swing_engine.research.cards import ROOT, WINDOWS
from swing_engine.research.costs import cost_table

env = os.environ
slugs, n = env["SLUGS"].split(","), int(env["N"])
keep = [s for s in env.get("ALWAYS_LONG", "").split(",") if s]
store_path = ROOT / load_settings.__wrapped__(Path(f"config/prereg_{env['TAG']}.yaml")).data.store_path
w = WINDOWS[0]
with Store(str(store_path), read_only=True) as store:
    bars = store.read_bars(None, w.start, w.end)
b = bars.loc[bars["symbol"] == "SPY"]
bench = pd.Series(b["close"].astype(float).to_numpy(), index=pe._bar_days(b["ts"])).sort_index()
costs = pe._cost_lookup(cost_table(bars))
crit = pe.alpha_t_critical(n)
for s in slugs:
    path = store_path.parent / "runs" / "replay" / f"{w.start}_{w.end}_{env['PREFIX']}{s}.json"
    if s in keep or not path.exists():
        continue
    g = pe.grade_run(json.loads(path.read_text()), costs, n, bench)
    if g.get("haircut_sharpe", -1) > 0 and g.get("net_r", -1) > 0 and g.get("alpha_ann", -1) > 0 and g.get("alpha_t", -1) >= crit:
        keep.append(s)
print(",".join(keep))
PY
)
echo "2017-24 window for: $LONG"
uv run python -m swing_engine.research.prereg_run $COMMON --slugs "$(todo "$LONG" 2017)" --alpha-slugs "$LONG" --window-years 2017 --out $OUT --no-eval
drain
uv run python -m swing_engine.research.prereg_eval --settings config/prereg_$TAG.yaml --tag-prefix $PREFIX --n-trials $N --slugs $SLUGS --benchmark SPY --alpha-slugs $SLUGS --out $OUT
uv run python -m swing_engine.research.prereg_eval --settings config/prereg_$TAG.yaml --tag-prefix $PREFIX --n-trials $N --slugs $SLUGS --benchmark IWM --alpha-slugs $SLUGS --out ${OUT%.md}-iwm.md
uv run python -m swing_engine.research.income_view --settings config/live.yaml
OUT=$OUT TAG=$TAG uv run python -c "
import os
from pathlib import Path
from swing_engine.ops.notify import deliver, truncate
p = Path(os.environ['OUT'])
t = p.read_text() if p.exists() else 'no results file (see data/logs/research/)'
deliver('Batch ' + os.environ['TAG'][1:] + ': results', truncate(t[t.find('## Verdicts'):] + '\n\n' + t[:1500]))
"
echo "BATCH $TAG DONE $(date '+%F %H:%M')"
