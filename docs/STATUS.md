# Project status: PAUSED again (2026-10-07 evening, by the user)

## Done (committed)
- Rounds 1-4: data, features, 7 strategies + 5 research strategies (shadow-only), backtester, ranker, risk,
  Alpaca paper autopilot + position manager, live monitor with small-cap track and Telegram ratings, float data,
  doctor/nightly, outcomes, playbook router + market breadth, historical replay, shadow ledger. All review
  findings through round 4 fixed. 1,193 tests pass.
- Settings files support `extends:`; config/live.yaml = settings.yaml + real-data store paths.
- Real data: data/market.duckdb holds Massive grouped daily bars for every US ticker, 2024-10-07..2026-10-06
  (501 sessions, 16,027 tickers, splits table). scripts/extend_history_alpaca.py adds Alpaca SIP split-adjusted
  daily bars 2016-01-04..2024-10-06 for 4,770 liquid names + index/sector ETFs (survivorship bias before
  2024-10-07; recorded in ingest_meta 'alpaca_extension'). DONE 2026-10-07: 7,354,836 bars for 4,326 symbols,
  0 errors. Store now spans 2016-01-04..2026-10-06.
- GitHub: https://github.com/Jackpep-bot/Swing-T (public; origin/main). .env, data/ never committed.
- Claude Code add-ons (new sessions): ponytail plugin (enabled in ~/.claude/settings.json), graphify skill
  (`/graphify .`; CLI `graphify`), Anthropic Agent Skills already synced. OmniRoute NOT installed (gateway, not a
  plugin; user has not decided).
- caffeinate was left running at the user's request; stop with `pkill caffeinate` when done.

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
  (suspect filters). Saved runs/replay/2024-10-07_2026-10-05.json; `swing shadow report --replay`.
- Work-in-progress committed (all off by default, existing 1,219 tests pass, NEW CODE NOT YET TESTED):
  strategy hooks `engine_trail` / `trail_stop` (position manager + backtest), chandelier and extra exits,
  14 new breadth columns, data/edgar.py earnings 8-K + companyfacts, data/fundamentals.py.

## Resume here (in order)
1. Finish the paused workers (notes below): tests for the risk hooks, breadth columns and EDGAR/fundamentals; the
   `swing ingest-edgar` CLI; features/extra.py on-demand features (design below); market_school.py and playbook
   overlays (off by default); the remaining risk tools; apply the fact-check fixes listed below.
2. Implement the ~118 catalog strategies (decisions implement / implement_disabled_for_comparison) on those features,
   all disabled or shadow_only; then the approximate ratings.
3. Re-run both replays (the 2017-01-01..2024-10-04 one was stopped) and write per-strategy, per-regime results into
   each card's Empirical section.
4. Before the first real nightly: separate live from sample data. data/runs, data/journal and state/orders.sqlite
   are shared by config/settings.yaml (sample) and config/live.yaml; state/orders.sqlite holds 6 sample
   (fictional-ticker) orders. Plan: move the live store to its own folder (e.g. data/live/) and give live.yaml its
   own ledger_file, or archive the sample artifacts. Then the paper nightly and scripts/install-launchd.sh.
5. cli deflated Sharpe uses trial_count(strategy); gate 2 needs the count of all trials.

### Paused-worker notes
## features worker (no files changed)
Call sites: replay.py:194-202 build_replay_panel (:512); cli.py:584-585 _read_panel (scan/backtest/ranker/regime/_signals_for), :885 features cmd, :992 _panel_from_provider; nightly.py:631-632 _step_features. backtest.py builds none.
adx_14/plus_di/minus_di/ema_20 exist in patterns2 as_of_view (on the fly). ibs == close_pos; ret_overnight == gap_pct; prev_close exists.
tests/test_strategies_common.py fixed allowed-columns list must widen. Cached panels from store lack extras -> need ensure_extra(panel, names, market).
Design: features/extra.py EXTRA_FEATURES registry w/ context cache; numpy loops psar/supertrend/kama; calendar via data/calendar.schedule; prev_<col>; required_extras(strategies). Choices: wide_range_bar range>=1.5x mean20; hot_by_price signed/EMA20|c-o|; mansfield/beta 252; id_score 252 skip 21.
## EDGAR worker: data/edgar.py + data/fundamentals.py written, ruff clean, UNTESTED.
Remaining: fixtures tests/fixtures/edgar, tests test_data_edgar_earnings.py/test_data_fundamentals.py; `swing ingest-edgar` CLI (refuse placeholder UA, Edgar(secrets.edgar_user_agent), run_edgar_ingest, _print_mapping); docs section; check acceptanceDateTime timezone against a real payload.
Panel hook: fundamentals.edgar_panel_features(store, panel) -> sue, rev_surprise, gross_prof, shares_outstanding, turnover, days_since_earnings, is_earnings_window (visible session after filed date).
Gaps: delisted tickers no CIK; no GrossProfit fallback; OCF is YTD.
## risk worker: _base.py hooks (engine_trail, trail_stop default_hook), position_manager._trail_stop combines overlay + strategy trail (ExitReason.STRATEGY_TRAIL), backtest trail_rule, TrailingStop.chandelier/with_atr_column/chandelier_stop, close_atr_mult/channel_bars/giveback_pct, profitable_closes (ExitReason.PROFITABLE_CLOSES), size_floor_universe. Ruff clean; existing tests pass; NO new tests.
Remaining: tests; turtle N units (sizing/limits); drawdown rules (6% monthly stop, DD-scaled equity); rank hysteresis helper; book vol scaling; multiple-testing helper on trial_count(None); gates.md haircut rule + CZ manual step.
Lead: core/config.py needs RiskConfig fields (max_monthly_loss_pct, max_units_per_sector). cli deflated Sharpe uses trial_count(strategy) -> gate 2 needs trial_count(None) (BUG).
## fact-check: table appended to CATALOG.md; fixes NOT applied:
1 CMP 82bp = VW L/S alpha (EW 180bp t=6.07; long-side +90bp t=4.64): catalog.json CMP notes/evidence + Stine item, CATALOG.md ~216, methods/14 lines 123,227, methods.md 718, strategies/insider_cluster.md, stine_insider_superstock_weekly.md
2 80-20: methods.md line 299 reversed (card right)
3 NR7 period 1980-2016 (catalog.json says 2011)
4 IBS borrow 0.15%/day not /yr (ibs_mean_reversion.md:56)
5 Kaufman gap momentum: non-cumulative 100*up/down gaps, SMA, defaults 40/20; fix card
Confirmed: Ehlers formulas (remove caveat), Turtle, Holy Grail ADX30/20EMA, Connors, HXZ etc. Not yet checked: ORB periods, Lakonishok-Lee, Zhao, Chordia, Bulkowski, EasySwing, Backtrex, JT93, Crabel exits.

## Older resume notes (first pause)

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
