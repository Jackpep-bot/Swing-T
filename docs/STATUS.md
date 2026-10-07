# Project status: PAUSED (2026-10-07, by the user)

## Done (committed)
- Rounds 1-4: data, features, 7 strategies + 5 research strategies (shadow-only), backtester, ranker, risk,
  Alpaca paper autopilot + position manager, live monitor with small-cap track and Telegram ratings, float data,
  doctor/nightly, outcomes, playbook router + market breadth, historical replay, shadow ledger. All review
  findings through round 4 fixed. 1,193 tests pass.
- Settings files support `extends:`; config/live.yaml = settings.yaml + real-data store paths.
- Real data: data/market.duckdb holds Massive grouped daily bars for every US ticker, 2024-10-07..2026-10-06
  (501 sessions, 16,027 tickers, splits table). scripts/extend_history_alpaca.py adds Alpaca SIP split-adjusted
  daily bars 2016-01-04..2024-10-06 for 4,770 liquid names + index/sector ETFs (survivorship bias before
  2024-10-07; recorded in ingest_meta 'alpaca_extension'). Check data/logs/extend-alpaca.log; re-run if it did
  not finish (it refetches everything with full=True; harmless).

## Stopped mid-way (resume these)
1. Dashboard (swing_engine/dashboard/, uncommitted): built, integrated, reviewed; the final fix pass was
   interrupted. Resume: Workflow scriptPath .../workflows/scripts/swing-dashboard-*.js with
   resumeFromRunId wf_5867e398-c24 (cached agents replay), or finish the fixes by hand; then
   `uv run pytest tests/test_dashboard_*.py`, wire `swing dashboard`, and check every tab in a browser.
2. Research layer (docs/research-raw/brands/*.json written; docs/catalog/ in progress): resume
   swing-research-layer-*.js with resumeFromRunId wf_2011a74c-b99 (4 sweeps cached), then catalog -> cards ->
   fact-check; then an implementation round for everything the catalog marks implement/approximate.

## Next after that
1. `uv run swing --settings config/live.yaml replay --start 2024-10-07 --end 2026-10-05` (survivorship-free
   window) and `--start 2017-01-01 --end 2024-10-04` (longer, biased); per-strategy and per-regime results go
   into each strategy's knowledge card as an Empirical section.
2. First real nightly on Alpaca paper: `uv run swing --settings config/live.yaml nightly --broker alpaca --execute`.
3. scripts/install-launchd.sh so nightly and monitor run on weekdays.
