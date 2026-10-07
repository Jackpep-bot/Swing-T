# Project status (2026-10-07)

## Done (committed)
- Rounds 1-3: data, features, 7 strategies, backtester, ranker, risk, Alpaca paper execution with autopilot and
  position manager, live monitor (news, EDGAR, halts, bar triggers, small-cap track, Telegram rating buttons),
  float data from SEC filings, doctor/nightly commands, outcome tracking, setup guide, launchd/systemd units.
- Review of rounds 2-3: all 17 high/medium findings fixed with regression tests (git log "Review fix: ...").
  875 tests pass.
- docs/methods.md: 14-method work-up with fact-check.
- Keys verified live (`swing doctor --live`): Massive, Alpaca paper, Alpha Vantage, Anthropic, Telegram
  (@tofu_swing_alerts_bot), EDGAR. User will not pay for data until the system proves itself (free tiers only).

## In progress
- Massive grouped-daily backfill of 2 years (free tier, ~100 min) into data/market.duckdb via config/live.yaml;
  log at data/logs/backfill-massive.log; resumable (re-run the same command).
- Round 4 build (workflow script swing-engine-round4-*.js): playbook router + breadth, five new strategies
  (pullback_holy_grail, base_breakout, power_gap, qullamaggie_flag, episodic_pivot), historical replay,
  shadow ledger, nightly wiring (panel built on the screened universe only).

## Next
1. Run `swing replay` on the real 2-year history (results decide which strategies stay enabled).
2. First real nightly on Alpaca paper (`--settings config/live.yaml --broker alpaca --execute`).
3. Install launchd units (scripts/install-launchd.sh) so nightly and monitor run on weekdays.
