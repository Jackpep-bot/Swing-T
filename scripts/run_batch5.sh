#!/bin/zsh
# Batch 5 (docs/preregistration/2026-10-13-batch5.md): 15 single-strategy books. Power is
# scripts/on_power.sh's job. Waits for the small-cap map, replays every card on 2024-26, then 2017-24 for the cards that meet the rule in 2024-26 and for the
# three once-a-year cards, grades against SPY (and IWM for reading), and Telegrams the verdicts. Run detached:
#   nohup scripts/on_power.sh scripts/run_batch5.sh > data/logs/research/batch5.log 2>&1 &
cd /Users/personal/Desktop/swing-engine
SLUGS=russell_recon_deletion_rebound,russell_recon_addition_frontrun,tax_loss_loser_rebound,ceo_cfo_buy_5day,pre_earnings_runup_winners,double_surprise_smallmid,shareholder_yield_smallmid,clenow_stocks_on_the_move_midcap,piotroski_fscore8_small_value,code33_trend_template,pocket_pivot_morales_kacher,green_line_breakout_wish,bensdorp_mr_selloff,bensdorp_adx_reversal,sykes_first_green_day
ANNUAL=russell_recon_deletion_rebound,russell_recon_addition_frontrun,tax_loss_loser_rebound
OUT=docs/preregistration/2026-10-13-batch5-results.md
BOOKS=()
for s in ${(s:,:)SLUGS}; do BOOKS+=(--book $s=config/prereg_b5_$s.yaml); done
COMMON=(--settings config/prereg_b5.yaml --tag-prefix prereg-b5- --n-trials 15 --benchmark SPY --job-gb 2024=6,2017=30 $BOOKS)
# 2024=6: a 2024-26 replay on this 6,400-name screen held 3.4 GB after 28 minutes (2026-10-13), so 7 run at once.
# Slugs of $1 with no finished and no running replay for the window starting in year $2: a restart of this script
# never repeats a replay (each one logs a trial).
todo() {
  local out=() s
  for s in ${(s:,:)1}; do
    local done_=(data/live/runs/replay/$2-*_prereg-b5-$s.json(N))
    (( $#done_ )) && continue
    pgrep -f -- "--start $2-.* --tag prereg-b5-$s\$" > /dev/null || out+=($s)
  done
  echo ${(j:,:)out}
}
drain() { while pgrep -f -- "--tag prereg-b5-" > /dev/null; do sleep 30; done }  # replays an earlier start left running
while pgrep -f run_smallcap_map.sh > /dev/null; do sleep 60; done
echo "start $(date '+%F %H:%M')"
uv run python -m swing_engine.research.prereg_run $COMMON --slugs "$(todo $SLUGS 2024)" --alpha-slugs $SLUGS --window-years 2024 --out $OUT --no-eval
drain
LONG=$(uv run python - <<PY
import json
from pathlib import Path
import pandas as pd
from swing_engine.core.config import load_settings
from swing_engine.data.store import Store
from swing_engine.research import prereg_eval as pe
from swing_engine.research.cards import ROOT, WINDOWS
from swing_engine.research.costs import cost_table
slugs, annual = "$SLUGS".split(","), "$ANNUAL".split(",")
store_path = ROOT / load_settings.__wrapped__(Path("config/prereg_b5.yaml")).data.store_path
w = WINDOWS[0]
with Store(str(store_path), read_only=True) as store:
    bars = store.read_bars(None, w.start, w.end)
b = bars.loc[bars["symbol"] == "SPY"]
bench = pd.Series(b["close"].astype(float).to_numpy(), index=pe._bar_days(b["ts"])).sort_index()
costs = pe._cost_lookup(cost_table(bars))
crit = pe.alpha_t_critical(15)
keep = list(annual)
for s in slugs:
    path = store_path.parent / "runs" / "replay" / f"{w.start}_{w.end}_prereg-b5-{s}.json"
    if s in annual or not path.exists():
        continue
    g = pe.grade_run(json.loads(path.read_text()), costs, 15, bench)
    if g.get("haircut_sharpe", -1) > 0 and g.get("net_r", -1) > 0 and g.get("alpha_ann", -1) > 0 and g.get("alpha_t", -1) >= crit:
        keep.append(s)
print(",".join(keep))
PY
)
echo "2017-24 window for: $LONG"
uv run python -m swing_engine.research.prereg_run $COMMON --slugs "$(todo $LONG 2017)" --alpha-slugs $LONG --window-years 2017 --out $OUT --no-eval
drain
uv run python -m swing_engine.research.prereg_eval --settings config/prereg_b5.yaml --tag-prefix prereg-b5- --n-trials 15 --slugs $SLUGS --benchmark SPY --alpha-slugs $SLUGS --out $OUT
uv run python -m swing_engine.research.prereg_eval --settings config/prereg_b5.yaml --tag-prefix prereg-b5- --n-trials 15 --slugs $SLUGS --benchmark IWM --alpha-slugs $SLUGS --out ${OUT%.md}-iwm.md
uv run python -m swing_engine.research.income_view --settings config/live.yaml
uv run python -c "
from pathlib import Path
from swing_engine.ops.notify import deliver, truncate
p = Path('$OUT')
t = p.read_text() if p.exists() else 'no results file (see data/logs/research/batch5.log)'
deliver('Batch 5 (15 trader and event methods): results', truncate(t[t.find('## Verdicts'):] + '\n\n' + t[:1500]))
"
echo "BATCH5 DONE $(date '+%F %H:%M')"
