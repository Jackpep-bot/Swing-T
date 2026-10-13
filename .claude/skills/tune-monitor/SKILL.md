---
name: tune-monitor
description: Review the last N days of live monitor alerts, ratings and outcomes per rule and source, and propose threshold changes backed by before/after replay counts over the logged events.
---
## Read first
`docs/research-monitor.md` (stage-1 rules, alert policy), `docs/gates.md` gate 3, `swing_engine/monitor/constants.py`
and the `monitor:` block of `config/settings.yaml`.

Always pass `--settings config/live.yaml`. The live event log is `data/live/market_events.sqlite`; without the flag you
read the sample-era `data/events.sqlite`.

## Steps
1. Baseline: `uv run swing --settings config/live.yaml monitor report --days 7` (alerts per rule and source,
   duplicate rate, latency, Useful/Noise/Traded ratings) and `... monitor outcomes --days 30` (forward moves after
   alerts).
2. Where the thresholds live:
   - settings `monitor.*`: `rvol_gate`, `gap_pct_alert`, `per_ticker_cooldown_min`, `hourly_alert_cap`, `quiet_hours_et`,
     and the `smallcap` block.
   - `swing_engine/monitor/constants.py`: everything else.
   - `swing_engine/monitor/rules/*.py`: rule logic only (each is `@register("rule", name)`, <1 ms, no I/O).
3. Before/after: run `uv run swing --settings config/live.yaml monitor replay --days 7 [-r rule,...]` on the current
   code and save the counts. Make the change, replay again, and show both per rule and priority. Replay re-runs stage-1
   over the logged events and never delivers (`--dry-run` is the default; never pass `--deliver`).
4. Propose the change as a diff to `config/settings.yaml` / `monitor/constants.py`, with the before/after table and the
   ratings that motivate it. Jack approves it before it is applied. The launchd monitor picks it up on restart.
5. Policy: a rule with no acted-on (Traded or Useful) P2+ alert over 14 days is proposed for demotion to P1 (digest).
   Never demote account or ops events.
6. Tests: `uv run pytest -q tests/test_monitor_rules.py tests/test_monitor_pipeline.py tests/test_monitor_smallcap.py`,
   then `uv run pytest -q` and `uv run ruff check .`.

## Notes
- `agent.llm_enabled` is false in `config/live.yaml`, so live alerts carry no Haiku classification. Tune on stage-1
  rules and ratings, and do not turn the classifier on (free tiers only).
- Ratings come from Telegram buttons or `uv run swing monitor rate <event_id> useful|noise|traded`. Few ratings means say so;
  do not tune on a handful.
