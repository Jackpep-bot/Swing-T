# Project status: PAUSED (2026-10-06, usage limit reached)

## Done
- Scaffold, contracts (`core/`), config, CLAUDE.md, skills, research docs (`docs/research-*.md`, `docs/sources-schwab-massive.md`).
- Research complete and saved under `docs/research-raw/`: architecture.json, live-monitor.json, smallcap-pump.json
  (fact-check stage of the small-cap pass did not run), and four of six swing-methods sweeps
  (`methods-sweeps/`: youtube, fintwit, books_blogs, evidence). Reddit and 2025-26 events sweeps, deep dives and synthesis did NOT run.
- Parallel implementation was started and stopped mid-way; whatever landed in `swing_engine/` is uncommitted WIP from eight agents and is
  NOT integrated or tested.

## Resume plan
1. `git status`; review WIP files; run `uv run pytest -q` and `uv run ruff check .` to see what is broken.
2. Re-run the build workflow (script at ~/.claude/projects/.../workflows/scripts/build-swing-engine-wf_1023289f-d60.js) or
   re-launch per module from docs/api-contract.md; then integrate, review, fix.
3. Re-run the swing-methods workup for reddit + events sweeps, deep dives, synthesis; write docs/methods.md.
4. Fill `monitor.smallcap` thresholds from smallcap-pump.json (see signals: pre-market gap >= 50% for pump universe, RVOL >= 5x,
   float < 10-20M, 46.6% of highs by 9:45, 67% close below open, offering/424B5 same day = dump flag).
