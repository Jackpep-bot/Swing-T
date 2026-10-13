# Project status: IDLE, video-model P0 and P1 first pass done (2026-10-13)

## Done (committed)
- Rounds 1-4: data, features, 7 strategies + 5 research strategies (shadow-only), backtester, ranker, risk,
  Alpaca paper autopilot + position manager, live monitor with small-cap track and Telegram ratings, float data,
  doctor/nightly, outcomes, playbook router + market breadth, historical replay, shadow ledger. All review
  findings through round 4 fixed. 1,193 tests pass.
- Settings files support `extends:`; config/live.yaml = settings.yaml + real-data store paths.
- Real data: data/live/market.duckdb (moved 2026-10-08) holds Massive grouped daily bars for every US ticker, 2024-10-07..2026-10-06
  (501 sessions, 16,027 tickers, splits table). scripts/extend_history_alpaca.py adds Alpaca SIP split-adjusted
  daily bars 2016-01-04..2024-10-06 for 4,770 liquid names + index/sector ETFs (survivorship bias before
  2024-10-07; recorded in ingest_meta 'alpaca_extension'). DONE 2026-10-07: 7,354,836 bars for 4,326 symbols,
  0 errors. Store now spans 2016-01-04..2026-10-06.
- GitHub: https://github.com/Jackpep-bot/Swing-T (public; origin/main). .env, data/ never committed.
- Claude Code add-ons (new sessions): ponytail plugin (enabled in ~/.claude/settings.json), graphify skill
  (`/graphify .`; CLI `graphify`), Anthropic Agent Skills already synced. OmniRoute NOT installed (gateway, not a
  plugin; user has not decided).
- caffeinate (-dims) is running at the user's request (2026-10-08); stop with `pkill caffeinate` when done.

## Done in the second session (branch claude/project-thread-jdz24e, PR https://github.com/Jackpep-bot/Swing-T/pull/1)
- Dashboard committed; `swing dashboard`; all 8 tabs checked on config/live.yaml; review fixes (newest live ledger row,
  SRI on the chart library). Monitor fix: Form 4 code A (grant) no longer counts as a buy.
- Research layer: catalog (281 items) and 130 strategy cards in docs/strategies/ (each ends with a pending
  `## Empirical (replay)` section). Partial fact-check table at the end of docs/catalog/CATALOG.md.
- Signal/OrderIntent `entry_type` (open | stop | limit): backtest/replay (`research.backtest.entry_fill`) and the shadow
  ledger fill stop/limit entries on the next session; the broker layer refuses non-open entries for now.
- Replay 2024-10-07..2026-10-05 (11 strategies, router on): -20.2%, PF 0.78, Sharpe -1.01, 666 trades, costs $9.5k.
  Shadow ledger gross R: breakout_52w +0.08, momentum_burst +0.07, rsi2 +0.05, sr_bounce +0.03; sr_breakout -0.13,
  pullback_trend -0.06, holy_grail -0.07, power_gap -0.21; qullamaggie_flag (3) and episodic_pivot (2) barely fire
  (suspect filters). (That JSON was overwritten by a 2026-10-08 timing run; the numbers above are the record.) `swing shadow report --replay`.
- Work-in-progress committed (all off by default, existing 1,219 tests pass, NEW CODE NOT YET TESTED):
  strategy hooks `engine_trail` / `trail_stop` (position manager + backtest), chandelier and extra exits,
  14 new breadth columns, data/edgar.py earnings 8-K + companyfacts, data/fundamentals.py.

## Done in the third session (2026-10-08, same branch / PR)
- Tests for the trail hooks, the 14 breadth columns and EDGAR earnings/fundamentals; bugs fixed: Zweig thrust fired
  twice per setup; a through-close strategy trail discarded a valid engine stop; chandelier on unsorted panels;
  per-day NYSE size breakpoint; EDGAR acceptanceDateTime is UTC (checked on MSFT), floored at the filing date.
- `swing ingest-edgar`; data.fundamentals.join_edgar adds sue, rev_surprise, gross_prof, shares_outstanding,
  turnover, days_since_earnings, is_earnings_window, days_since_filing to replay / CLI / nightly panels (cached
  `fundamental_events` table, rebuilt after each ingest).
- Fact-check fixes applied (CMP 82bp is long-short alpha; 80-20 direction; NR7 period; IBS borrow per day; Kaufman gap
  momentum formula; Ehlers caveat dropped).
- Risk tools (all off by default): Turtle N units and unit limits, monthly loss stop, drawdown-scaled equity, book
  vol scaling, rank hysteresis, Harvey-Liu haircut; deflated Sharpe now counts ALL trials; gates.md gate 2 spelled out.
- features/market_school.py (distribution days, follow-through days) and playbook overlays (market_school_pressure /
  correction, hill_bearish, mcclellan_negative, q25_bearish), all off by default, risk-reducing only.
- features/extra.py: ~220 on-demand indicators (exact and parametric names); strategies declare `extra_features`.
- 115 catalog strategies (docs/catalog decision implement -> shadow_only; implement_disabled_for_comparison ->
  disabled). Skipped: williams_oops (same-day gap entry), connors_cvr3_vix (no VIX), stine_insider_superstock_weekly
  (no float/PE). Review workflow: 54 confirmed defects fixed with regression tests; tests/test_strategies_all.py checks
  every registered strategy for point-in-time behaviour.
- `should_exit(row, bars_held, position)` gets a PositionContext (entry price, stops, best price, entry signal
  features); 7 strategies gained their card exits; intents persist signal features for live exits.
- Live/sample separation: config/live.yaml -> data/live/market.duckdb, state/live/orders.sqlite,
  state/live/limits.json; sample artifacts archived in data/sample_archive/ and state/sample_archive/.
  config/replay.yaml runs research replays on a copy (data/live/replay.duckdb).
- install-launchd.sh --settings (SWING_SETTINGS for both agents). `swing replay --tag`.
- 2,229 tests pass.

## Video-model work (2026-10-13, plan: docs/proposals/video-model-plan.md)
No jobs in flight. Weekend research finished: corrected-universe leaderboard (3,214 trials) has no survivors; batch 3
fails the alpha-vs-SPY rule. All strategies stay shadow-only.

Plan P0 (farm features on the swing engine) is DONE and usable:
- Receipts: `events` table (`ops/receipts.py`), every fire / refusal / exit / outcome with the deciding step and
  inputs, stamped with `engine_sig` (`core/signature.py`). `swing receipts backfill|show`. Backfilled 953 rows.
- Daily study: nightly `study` step writes `docs/studies/DATE.md` (`ops/study.py`, `swing study [--all]`), named in Telegram.
- Dashboard (`dashboard/farm.py`): chart layer toggles + Inspector (receipt JSON), intraday chart 2m-4h with
  market-structure layers, Studies tab, Vocabulary tab, coverage tiles and heatmap. Checked in the browser.
- Vocabulary: `uv run python -m swing_engine.ops.vocabulary` -> docs/vocabulary.md; rulings in docs/rulings.md.

Plan P1 (intraday lane) first pass is DONE:
- `swing ingest-intraday` -> data/live/intraday.duckdb (free Alpaca SIP 1-minute, SPY QQQ IWM GLD from 2016, BTC/USD
  from 2021, ~10M rows; resumable). `data/intraday.py` resamples without look-ahead.
- `features/market_structure.py` (21 event kinds, docs/market-structure.md, truncation test).
- Pre-registered docs/preregistration/2026-10-13-intraday-chains.md, run once by `research/intraday_chains.py`:
  all 3 cards FAIL net of costs (results file beside it). Gross R is about zero; costs decide it. 6 trials logged.

Also done 2026-10-13: zones drawn as filled boxes (app.js series primitive); broker stop/target fills logged as
`exit` receipts (`ops/reconcile.py`, nightly `reconcile` step, `swing receipts reconcile --since DATE`; 2 target fills found).

No jobs are running. Mac is on power (owner, 10:21 ET). Dashboard preview may be up on port 8765.

Queue for the next session, in order (owner 2026-10-13: "complete all workflows, every facet"; 44 GB budget, max two
long-window replays at once; pre-register before any new replay; commit and push each piece):
1. Merge residual_momentum's v2c-resmom 2024-26 re-replay (store replay_p3) into the cards and leaderboard; its first
   2024-26 result was invalid (warm-up too short). Then regrade batch 3 results doc if the verdict changes.
2. Duplicate rows under renamed tickers (BK/BNY, ERJ/EMBJ): dedupe in the universe, re-check affected board rows.
3. SPY-relative grading as the default yardstick on the leaderboard (alpha, not absolute R).
4. Fetch card branches `claude/batch2-cards` / `claude/batch3-cards` for any candidates not yet replayed; pre-register
   the next batch, run with `research.prereg_run`.
5. Intraday lane, round 2 (new pre-registration, new trials; never retune the three failed cards on the same windows):
   the first run showed gross R about zero and BTC costs near 1.9R per trade, and the full chains under 200 trades.
   Check `intraday_chains.py` and the dashboard use the same day clock for PDH/PDL. Add fires/refusals from
   `data/research/intraday_chains/*.parquet` as "trades / setups seen" layers on the intraday chart.
6. Receipts not yet hooked: in-strategy filters (min_stop), `swing paper --from-intents`; outcome events do not link
   to their fire; backfilled refusals have step `unknown` (runs/nightly JSON has the sizer reasons).
7. Dashboard polish: collapse a zone's lifecycle events into one box; filter box on Vocabulary; deep link to an
   intraday symbol/day; old daily markers duplicate the new layers.
8. Clean up lane store copies in data/live by hand (ask before deleting).
- Plan P2 (always-on host, intraday paper executor) WAITS for the owner's decision. Do not start it.

## Older resume notes (superseded by the section above) - updated 2026-10-09 22:30 ET
No survivors anywhere. Evidence: docs/leaderboard.md (2,394+ trials), docs/reality_check.md (White RC / SPA: no
window or horizon rejects "no edge"), pre-registered groups all FAIL: three picks, two picks, walk-forward ensemble
(docs/preregistration/*-results.md). Paper trading off; nightly scans shadow strategies and pushes to Telegram.

Running unattended (2026-10-10 09:00 ET, Mac on AC), detached with nohup:
a. Full leaderboard re-run on the corrected universe: `swing research run` (run 20261010-033614, 2 lanes, log
   data/logs/research/full_rerun.log); 2024-26 done, 2017-24 in progress. It rebuilds cards, leaderboard and
   reality check and Telegrams the summary at the end. Then: commit docs/leaderboard.md, docs/strategies, docs/reality_check.md.
b. scripts/after_rerun_b3.sh (started 13:00 ET, runs beside (a) within a 44GB budget) runs the batch 3 pre-registered group
   (docs/preregistration/2026-10-10-batch3.md; results -> ...-batch3-results.md, Telegram), then re-replays
   residual_momentum on 2024-26 (tag v2c-resmom, store replay_p3) because its earlier row had 3 graded signals
   (replay warm-up was too short for its 756-bar fit; fixed with per-strategy warmup_calendar_days).
c. 1R-exit family test (docs/preregistration/2026-10-10-exit-1r.md): regrade from existing ledgers into
   data/live/regrade_1r.duckdb -> docs/leaderboard_t1r.md (a worker is running it).
Done today: batch 2 (repurchasers PASS on its rule, zero alpha vs SPY, not enabled; FOMC and vol-managed SPY FAIL),
regime-cell walk-forward FAIL, docs/attribution.md (most gross edge is market drift; targets almost never hit).
Card branches: origin/claude/batch2-cards, origin/claude/batch3-cards (fetch for new files).

Queue:
1. New candidate cards arrive in docs/proposals/ from the "Online swing methodologies" thread. For each batch:
   research-ingest -> pre-registration doc committed BEFORE any replay -> `python -m swing_engine.research.prereg_run`
   (parallel, 40GB budget, identical to serial) -> results into the cards.
2. New data sources need Jack's approval before building.
3. Keep the Mac on AC power for long runs (it sleeps on battery / lid closed).

## Research commands
- Full research pass (every registered strategy, both windows, parallel lanes sized from free memory up to 40 GB,
  cards + leaderboard + Telegram summary at the end; refuses on battery and while the live store is being written):
  `nohup uv run swing --settings config/live.yaml research run --windows short,long > /dev/null 2>&1 &`
  Progress `tail -f data/logs/research/<run-id>.log`; manifest `data/live/runs/research/<run-id>.json`.
- Resume unfinished chunks: `uv run swing --settings config/live.yaml research run --resume latest`.
- Cards + leaderboard again over the latest run's lane stores: `uv run swing --settings config/live.yaml research rebuild`.
- The old scripts/lane_r*.sh and run_research_replays.sh are gone; replay_r1/r2.duckdb stay as the v2 record.
