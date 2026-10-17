#!/bin/zsh
# Runs a long job under the owner's power rule (2026-10-13: "start them I will plug in soon"): start on AC power,
# or on battery at or above BATT_FLOOR percent. If the battery falls below the floor the job's whole process tree is
# paused (SIGSTOP) and continued (SIGCONT) once AC power is back; nothing is lost and nothing needs a resume.
#   nohup scripts/on_power.sh scripts/run_smallcap_map.sh > data/logs/research/smallcap_map.log 2>&1 &
cd /Users/personal/Desktop/swing-engine
BATT_FLOOR=${BATT_FLOOR:-25}
on_ac() { pmset -g batt | head -1 | grep -q "AC Power" }
# no percentage in pmset's output fails the comparison, which reads as "not ok": the safe side
power_ok() { on_ac || (( $(pmset -g batt | grep -Eo '[0-9]+%' | head -1 | tr -d %) >= BATT_FLOOR )) 2> /dev/null }
tree() { local c; for c in $(pgrep -P $1); do echo $c; tree $c; done }
until power_ok; do sleep 60; done
echo "power ok ($(pmset -g batt | head -1)) $(date '+%F %H:%M'); starting $*"
"$@" &
JOB=$!
while kill -0 $JOB 2> /dev/null; do
  if ! power_ok; then
    kill -STOP $JOB $(tree $JOB)
    echo "battery below $BATT_FLOOR% $(date '+%F %H:%M'): paused until AC power"
    uv run python -c "from swing_engine.ops.notify import deliver; deliver('Research run paused: battery below $BATT_FLOOR%', 'Plug the Mac in and it continues by itself ($*).')"
    until on_ac; do sleep 60; done
    kill -CONT $JOB $(tree $JOB)
    echo "on AC power $(date '+%F %H:%M'): resumed"
  fi
  sleep 60
done
wait $JOB
