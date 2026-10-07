# Project status (2026-10-06)

## Built and verified
- All modules implemented and integrated; 597 tests pass, ruff clean. End-to-end CLI flow verified on the sample
  provider (ingest, features, scan, backtest x3, rank train, size, paper via paper_sim with approval and kill switch,
  Alpaca live refusal, review --dry-run, monitor dry-run replay).
- Adversarial review found 26 issues (6 high); all high and medium fixed with regression tests (see git log).
- Per-strategy reward:risk floor so rule-exit strategies (RSI-2) are not rejected by the 2:1 portfolio floor.

## Research
- docs/research-raw/: architecture, live-monitor, small-cap pump (its fact-check stage did not run), methods sweeps.
- docs/methods.md: written by the methods workup when it completes (reddit + events sweeps, deep dives, synthesis).

## Not yet done / next
1. Run with real keys: Massive free tier ingest on a real universe; Alpaca paper; verify the news/stock WebSocket
   adapters against live payloads (built from documented schemas and fixtures only).
2. Float data source for the small-cap track (not in Alpaca/Massive): FMP, sec-api, or an EDGAR cover-page parser.
3. Calibrate monitor thresholds after a two-week paper run (`swing monitor report`, `swing monitor replay`).
4. `brew install libomp` to enable LightGBM (scikit-learn fallback is used otherwise).
5. Optional: local web dashboard over DuckDB; VPS deployment unit for the monitor (see docs/research-monitor.md Ops).
