---
name: weekly-review
description: Weekly review of paper trading - read the weekly report, live-vs-replay drift, the shadow ledger and the leaderboard, and propose config changes as a diff for Jack to approve; only leaderboard survivors may be enabled, paper only.
---
## Read first
`docs/gates.md`, `docs/leaderboard.md` (the `## Survivors` section), `config/live.yaml`, the `playbook.regimes` block of
`config/settings.yaml`, and `docs/STATUS.md`.

## Inputs (all with `--settings config/live.yaml`)
1. Weekly report. The nightly writes it on the week's last session; otherwise
   `uv run swing --settings config/live.yaml weekly-report [--as-of YYYY-MM-DD]`. Read
   `data/journal/weekly-<ISO week>.md`: paper orders and fills, the shadow ledger top and bottom, drift, and the
   rule-based recommendations (`agent.weekly.recommendations`).
2. Drift (`research.drift.drift_table`). The live `shadow_signals` from the last 90 days against the store's
   `shadow_signals_replay` (2024-10-07+ only), net R per horizon. A flag needs >= 20 live trades and a gap > 2 SE. It is
   in the report and on the dashboard Drift tab (`uv run swing --settings config/live.yaml dashboard`, then
   http://127.0.0.1:8765/). An empty replay table there means drift has nothing to compare: say so.
3. Shadow ledger: `uv run swing --settings config/live.yaml shadow report --since <monday> --by strategy --horizon 10`,
   and `--taken` / `--untaken` to see what the engine passed on.
4. Leaderboard: the survivor list and each strategy's haircut Sharpe. The walk-forward result is in the card.
5. Gate progress: closed paper trades and months on paper against gate 1 (>= 100 trades, >= 3 months).

## Output: a short note plus a proposed diff, not applied
- What happened: trades, net result, and what fired in which regime.
- Drift flags and what they mean. "Below" on an enabled strategy means propose disabling it, or cutting its
  `playbook.regimes` multiplier. "Above" on a shadow-only one means it is a walk-forward candidate, not an enable.
- A unified diff against `config/live.yaml` (and `config/settings.yaml` `playbook.regimes` if needed), each hunk with
  its reason and numbers. Show it and wait for Jack's explicit yes. Apply only after that, then run `uv run pytest -q`
  and restart nothing yourself.
- Lead with anything Jack needs to decide or do.

## Hard rules
- Enable (`enabled: true`, or a non-zero regime multiplier) only a strategy that meets all three:
  - listed under `## Survivors` in `docs/leaderboard.md`,
  - passed its walk-forward (walk-forward skill),
  - at small risk, routed through the playbook.
  Today there are no survivors, so the only allowed proposals are risk-reducing ones.
- Paper only. Never touch `SWING_ALLOW_LIVE`, `execution.auto_submit_live`, `ALPACA_PAPER` or `.env`. Keep
  `agent.llm_enabled: false`.
- Risk-reducing changes (disable, lower a multiplier, enable an overlay) may be proposed freely, but they are still
  diffs for approval.
- Disabling does not close open paper positions; the position manager still manages them to exit. Say so when it
  matters.
- Never touch `state/KILL`. Recommend it only when a kill criterion (gates.md gate 4) is hit.
