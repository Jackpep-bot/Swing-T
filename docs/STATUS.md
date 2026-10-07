# Project status: PAUSED (2026-10-06, usage limit reached)

## Built and verified (committed)
- All modules plus round 2 (float data from SEC filings, `swing doctor`, `swing nightly`, alert outcomes, halt log,
  docs/SETUP.md, docs/OPERATIONS.md, launchd/systemd units). 699 tests pass, ruff clean.
- Keys in `.env` (git-ignored, mode 600): Massive (verified live), Alpaca paper (verified: active, $100k virtual),
  EDGAR contact. `swing doctor --live`: Massive, Alpaca account+data, EDGAR, Nasdaq halts all OK.
- Still missing keys: ALPHAVANTAGE_API_KEY, ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID.

## Stopped mid-way (resume these)
1. Round 3 build (script: ~/.claude/projects/-Users-personal-Desktop-swing-engine/<session>/workflows/scripts/swing-engine-round3-*.js):
   autopilot paper execution + position manager, Massive grouped-daily ingest (fixes the slow per-symbol ingest
   that pages the whole ticker list at 5 calls/min), monitor wiring (halt log, small-cap meta, Telegram rating buttons),
   then review of rounds 2+3 and fixes. Any partial edits were stashed: `git stash list` -> "round3-partial".
   Round 2 code has NOT had its adversarial review yet (reviewers failed on the spend limit).
2. Methods work-up: 53 merged methods in docs/research-raw/methods-sweeps/merged_compact.json; some deep dives
   written under docs/methods/; synthesis into docs/methods.md and the fact-check not done
   (script: swing-methods-finish-*.js, resume with the same args).
