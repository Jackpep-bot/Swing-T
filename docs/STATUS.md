# Project status: IDLE, queue of 2026-10-13 worked through; decisions wait for the owner (2026-10-13 11:10 ET)

## Fourth session (2026-10-13, branch claude/project-thread-4wq9xa, PR https://github.com/Jackpep-bot/Swing-T/pull/2; includes PR 1's commits)
No jobs running. Nothing enabled on paper (config/live.yaml enables no strategy). 2,564 tests pass.

Waiting for the owner (nothing else is blocked):
1. **Apply the renamed-ticker merge to the live store?** `swing --settings config/live.yaml repair-store --duplicates`
   (dry run), then `--apply`. Copy data/live/market.duckdb first. It was NOT applied: a session may not change the
   live store without the owner's word. Until then BNY, EMBJ and 61 other renamed tickers have a hole or another
   company's bars in their live history, and research ledgers are cleaned at read time instead.
2. **Dividend data?** `dividend_month_premium` (project file research/strategies/) is the only candidate card never
   replayed; it needs ex-dividend dates (Alpaca corporate actions, free) and total-return grading. New data source,
   so it waits for a yes.
3. Delete old lane store copies in data/live (replay*.duckdb, market_prerepair.duckdb, regrade_1r.duckdb: about
   25 GB)? Keep research_20261010-033614_l0/l1 (the current board reads them) and replay_p3 (pre-reg base).
4. Plan P2 (always-on host, intraday paper executor): still the owner's decision. Not started.

Done this session, in queue order:
- **Residual momentum 2024-26** merged from the v2c-resmom re-replay (rows copied into lane 1's ledger, noted in the
  run manifest): 2,556 signals, net +0.056R at 20d, -0.088R against SPY, t -1.69. Batch 3's verdict is about
  `large_cap_residual_momentum` and does not change.
- **Renamed tickers.** Not two pairs but 373 duplicate series: 63 renames inside the Massive window (BK/BNY, ERJ/EMBJ,
  MMC/MRSH, FI/FISV ...) and 310 `TICKER~date` delisted keys whose ticker was renamed or reused (some hold the wrong
  company: P~20190301 is Pure Storage, not Pandora). `data.repair.find_duplicates / merge_duplicates`, exact undo,
  tests. `research.cards.drop_renamed` removes the doubled signals from existing ledgers when they are read:
  384,311 of 17.8M rows (2.15%), largest change in net R 0.049, no haircut-Sharpe sign flips, no survivors either way.
  Known limit: a ticker handed from one company to another (Barrick GOLD -> B) is not re-homed; needs a ticker-change feed.
- **SPY-relative grading is the leaderboard default** (also cards `vs SPY` column and the reality check):
  net R minus SPY's R over the same holding span, beta 1. `--absolute` for the old yardstick. 846 new looks logged
  (4,099 trials before intraday round 2). No survivors. docs/leaderboard_liq*.md and _t1r.md are still absolute.
- **Next card batch**: the card branches hold nothing unreplayed. A new search (docs/proposals/swing-methods-2026-10/
  batch4/) checked 15 ideas, kept 1 (`month_end_rebalancing_avoidance_spy`) and shows it cannot reach the alpha-t rule
  in a 2-year window even if the paper is right. NOT pre-registered or run: a test that cannot pass only spends a trial.
- **Intraday round 2** (docs/preregistration/2026-10-13-intraday-round2*.md, `research/intraday_momentum.py`,
  4 trials, 4,103 total): `noise_area_momentum` (Zarattini-Aziz-Barbon 2024) FAIL, `first_half_hour_momentum`
  (Gao et al. 2018) FAIL. The noise-area rule has the paper's gross edge in 2016-23 (+2.9 bp a trade) but +0.9 bp
  after 1 bp a side, and +0.8 bp gross after publication. Round-1 cards were not touched.
- **Day clock**: the intraday chart now builds ETF structure from regular-hours bars like the replay (it used
  extended hours, so PDH/PDL differed). Chain trades (entry, path, stop, target) and refused setups are chart layers
  with their receipt; `chains_dir` on the dashboard data class.
- **Receipts**: strategy filter drops (min_stop, reward_risk, geometry) become refusals in the nightly (capped at
  100 per strategy per night: check the volume after the first run); `swing paper --from-intents` writes fires /
  refusals; `receipts.link_outcomes` ties an outcome to its fire or refusal (dashboard inspector shows
  `decision_event_id`). Only 1 backfilled refusal has step `unknown`, so no re-backfill was written.
- **Dashboard**: vocabulary filter box; deep link `#charts/intraday/SPY/2026-06-03/5m`; a zone's later events are
  listed in its box's receipt instead of drawn; the old Buy / Sell / Signal markers give way to a receipt marker on
  the same bar.
- **Bug found and fixed (paper)**: Alpaca's open-orders listing leaves out a filled bracket's `held` stop leg, so the
  position manager saw no stop and tried to arm a second one every night (4 errors on 10-12 and 10-13; harmless,
  the broker refused). `AlpacaBroker.open_orders` now lists the filled parent with both legs; breakeven and trail
  can find the stop again. Three paper positions are open from 2026-10-08 (BNS, PFG, DNTH; rsi2_meanrev), each
  with its stop and target at the broker.

Seen, not fixed:
- The 2026-10-13 nightly's ingest step failed (no network at 06:40 ET: DNS error), so the store ends 2026-10-09.
  The next nightly's ingest catches up; or run `swing --settings config/live.yaml ingest` by hand.
- Card front matter says `status: enabled` for the first five strategies; config/live.yaml enables none. The
  Vocabulary page shows the card's word.
- Rename merge does not touch `panel` (nightly rebuilds it) or the event tables keyed by the old ticker.

Next, when the owner has answered: apply the store merge, then `swing research run` on the repaired store only if a
new candidate needs it (the read-time dedupe already gives the corrected board). After a yes on dividends: ingest,
total-return grading, pre-register `dividend_month_premium`.

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

The queue that stood here was worked through in the fourth session: see the top section.

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
