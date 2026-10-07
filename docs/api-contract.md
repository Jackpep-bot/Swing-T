# Module API contract (what other modules may call)

## data
- `data.store.Store(path: str)`: `.write_bars(df)` (upsert on symbol+ts), `.read_bars(symbols|None, start, end) -> df`,
  `.write_table(name, df, keys)`, `.read_table(name, where=None) -> df`, `.snapshot_date()`; DuckDB; single-writer.
- `data.calendar.trading_days(start, end) -> list[date]`, `.is_open(dt)`, `.next_open(dt)`, `.prev_trading_day(d)`; NYSE via pandas_market_calendars.
- `data.universe.build_universe(provider, settings, as_of, *, bars=None, store=None) -> list[str]` (applies UniverseConfig; keeps
  delisted names that were active at as_of; `bars`/`store` screen without fetching the liquidity window).
- `data.ingest.run_ingest(settings, secrets, provider_name, symbols|None, start, end, store, *, full=False, mode='auto',
  splits=True, reference=True, progress=None) -> dict` (counts, elapsed). `mode`: `auto | symbols | grouped` (grouped = one
  call per session for the whole market via `MassiveProvider.grouped_daily`, resumable through the `ingest_grouped_days`
  table); `progress(line)` receives estimate/progress lines.
- Providers register `@register("bar_provider", name)`: `sample` (deterministic synthetic GBM with regimes, splits and a few delistings;
  seedable; no network), `massive`, `eodhd`, `alpaca`. Each honors its rate limit with a token bucket and caches raw JSON under `data/raw/`.
- `data.edgar.Edgar(user_agent)`: `.current_filings(form_types, count=100) -> df`, `.form4_buys(since) -> df` (edgartools),
  `.company_tickers() -> df` (SEC company_tickers.json).  `data.alphavantage.earnings_calendar(key, horizon='3month') -> df`.
  `data.quiver.Quiver(key)`: `.insiders(...)`, `.congress(...)` with point-in-time timestamp columns.
- `data.altdata.nightly_files(date) -> dict[str, df]`: SSR list, Reg SHO threshold, FINRA short volume (free, no key).

## features
- `features.panel.build_panel(bars, market=None) -> df` (see feature-contract.md); `features.indicators.*`, etc. as pure functions.
- `features.breadth.market_breadth(panel, *, exclude=()) -> df`: one row per session (index `session`, naive New York
  midnight) with `BREADTH_COLUMNS` = pct_above_50, pct_above_200, up4_count, down4_count, ratio_10d, new_highs, new_lows,
  n_symbols. Uses the panel's sma_50 / sma_200 / prev_close / high_52w / low_52w when present. 4% counts follow Stockbee
  (|close/prev_close - 1| >= 4%, volume >= 100k and above the prior day); `ratio_10d` floors its denominator at 1 and is NaN
  when the window has no 4% moves. Pass `exclude=(index ETFs,)` so SPY/QQQ/IWM are not counted as stocks. Also
  `breadth_as_of(breadth, as_of) -> Series | None`, `ratio_10d(up, down, window=10)`, `empty_breadth()`.
- `features.patterns2.add_patterns2(df) -> df` (df sorted by symbol, ts) appends `PATTERNS2_COLUMNS`: ema_20, adx_14,
  plus_di_14, minus_di_14, adr_pct_20, atr_40, avg_vol_50d_prev, vol_ratio_50d_prev, gap_atr40, run_up_42, rs_63d_rank (0-1
  percentile of the 63-bar return across the panel's symbols on the same session, so it depends on universe size). All causal.
  `patterns2_frame(panel)` returns them (from the panel, else computed once per panel object and cached);
  `as_of_view(panel, as_of, columns)`; geometry detectors `flat_base`, `cup_with_handle`, `flag`, `gap_consolidation`,
  `prior_advance` look only at indices <= `end`. Callers that slice the panel per day (replay) should run `add_patterns2`
  once up front.

## strategies
- Each `Strategy.signals(panel, as_of, regime) -> list[Signal]`; use only panel columns from the contract; `score` for ranking;
  compute `reward_risk`. Provide `default_params`. Register `@register("strategy", name)`. Optional
  `should_exit(row, bars_held) -> bool` (rule exit decided at the close, filled next open by the position manager) and a
  `max_hold_days` param (time stop).
- Registered: `sr_bounce`, `sr_breakout`, `pullback_trend`, `breakout_52w`, `momentum_burst`, `rsi2_meanrev`,
  `insider_cluster`, and the docs/methods.md 7b modules (patterns2 columns; enabled in settings.yaml for paper + shadow):
  `pullback_holy_grail` (ADX > 30 rising, low touches ema_20, first close above the touch-bar high; target = prior swing high,
  `min_reward_risk: 1.0`; time stop 10), `base_breakout` (cup-with-handle / flat base, close > pivot on >= 1.4x prior 50-day
  volume; exit on a heavy-volume close below sma_50; 40), `power_gap` (gap >= 10% or >= 0.75x ATR40 on 2x volume, break of a
  2-30 bar hold; exit on a close below sma_20; 60; `earnings_verified=0`, a "volume gap"), `qullamaggie_flag` (rs_63d_rank >=
  0.98, >= 30% prior move, ADR >= 5%, 10-40 bar flag; exit on a close below sma_20; 60), `episodic_pivot` (day-2 / delayed EP:
  day 2 closes above the day-1 high, fills day-3 open; exit on a close below sma_10 from bar 3; 60; `catalyst_verified=0`).
  The three trailing strategies set target = entry + 10R only so `risk.sizing` can size them; their MA exit closes the trade.
- `strategies.playbook` (market-regime router; not registered as a strategy): `MarketState(as_of, spy_trend: up|down|mixed,
  vol_regime: low|normal|high, breadth: strong|neutral|weak, regime, notes, inputs: dict[str, float])`;
  `market_state(panel, as_of, breadth=None, settings=None) -> MarketState` reads only rows dated <= as_of (SPY =
  `settings.playbook.market_symbol`; falls back to market_trend_state / market_vol_regime columns; no market data -> choppy).
  Regime = first match of high_vol_selloff, correction, healthy_uptrend, narrow_uptrend, choppy.
  `select_strategies(state, settings=None) -> {strategy: multiplier}` (sorted; enabled strategies with multiplier > 0 only;
  `playbook.enabled: false` -> every enabled strategy at 1.0). The table is `settings.playbook.regimes`
  (`core.config.default_playbook_table()` mirrors settings.yaml); a strategy absent from a regime may not open there. Every
  enabled strategy must appear in at least one regime or the router never selects it. Also `classify_trend`, `classify_vol`,
  `classify_breadth`, `classify_regime`, `enabled_strategy_names`.

## research
- `research.backtest.run_backtest(strategy, panel, start, end, risk_cfg, costs: CostModel, market=None) -> BacktestResult`
  (next-open entry, stop/target/time exits, one position per symbol, portfolio-level sizing via risk.sizing, equity curve, trades df).
- `research.metrics.summarize(result) -> dict` (trades, win_rate, avg_r, profit_factor, cagr, max_dd, sharpe, turnover, cost_drag)
  and `deflated_sharpe(sharpe, n_trials, n_obs, skew, kurt) -> float`, `probability_backtest_overfit(...)`.
- `research.trials.log_trial(name, params, metrics, path='data/trials.jsonl')`, `trial_count(name|None)`.
- `research.shadow`: forward outcomes of every signal, taken or not, keyed (strategy, symbol, as_of).
  `record_signals(store, signals, taken, as_of, regime, *, source='live', table=SHADOW_TABLE) -> int` (upsert; keeps grades
  already settled; `taken` holds `signal_key(sig)` = "strategy:symbol", client order ids or bare symbols);
  `grade_signals(store, as_of, horizons=(5, 10, 20), *, table=SHADOW_TABLE) -> int` (bars strictly after the signal date and
  <= as_of; stop first; next-open entry; gap through stop/target exits at the open; R before costs; per-horizon columns
  `hit_5d`, `result_r_5d`, `mfe_r_5d`, `mae_r_5d`, `exit_date_5d`, ...; unsuffixed = longest horizon);
  `shadow_report(store, since=None, group_by=('strategy', 'regime'), *, horizon=None, taken=None, table=SHADOW_TABLE) -> df`.
  Tables: `SHADOW_TABLE = 'shadow_signals'` (nightly, `source=live`) and `REPLAY_SHADOW_TABLE = 'shadow_signals_replay'`
  (replay, `source=replay`); the two never mix.
- `research.replay.run_replay(settings, store, start, end, *, strategies=None, use_router=True, equity=100000, costs=None,
  panel=None, record_shadow=True, shadow_table=REPLAY_SHADOW_TABLE, trials_path=DEFAULT_TRIALS_PATH) -> ReplayResult`: the
  nightly + autopilot loop replayed session by session (router on rows <= D, all enabled strategies compete for slots, sizing
  via `risk.sizing.size_signal_detail` with `risk_per_trade_pct x multiplier`, position-manager exits, next-open fills, costs);
  logs a trial. `ReplayResult(equity_curve, trades (+ signal_date, regime, risk_mult), daily, by_strategy, by_regime, summary)`.
  `build_replay_panel(store, start, end)`.
- `research.ranker.train_ranker(panel, horizon=10, start, end) -> RankerModel` (LightGBM if importable else sklearn
  HistGradientBoostingRegressor), `.predict(panel_as_of) -> Series`; `research.cv.purged_walk_forward(dates, n_splits, purge, embargo)`.

## risk / execution
- `risk.sizing.size_signal(signal, equity, risk_cfg, open_positions, sector_map=None) -> OrderIntent | None` (fixed-fractional
  risk_per_trade_pct / risk_per_share, capped by max_position_pct, optional vol-target; Schwab example: 50000*1% / 2 = 250 sh).
- `risk.limits.LimitState` (daily loss, drawdown, open positions, sector) `.check(intent, account) -> (ok, reason)`;
  `risk.killswitch.is_tripped(path) -> bool`.
- `execution.order_manager.OrderManager(broker, limits, killswitch_path)`: `.submit(intent, approved_by: str) -> dict`
  (refuses without approval or when kill switch tripped; idempotent via client_order_id; bracket with stop + target);
  `.reconcile() -> dict`.
  Also `.close_position(symbol, approved_by, qty=None, price=None, reason='')` (allowed under the kill switch, like a cancel),
  `.replace_stop(symbol, new_stop, approved_by, order_id=None)` (tighten only; refused under the kill switch),
  `.place_stop(symbol, stop, approved_by)` (arm a stop on a position with none; refused under the kill switch),
  `.cancel_order(order_id, client_order_id=None)`.
- Brokers `@register("broker", name)`: `alpaca` (paper by default, raises if ALPACA_PAPER is false and env SWING_ALLOW_LIVE != "yes";
  `.close_position`, `.replace_stop`), `paper_sim` (in-memory fills at next open with slippage; used by tests and backtests).
- `execution.position_manager.review_positions(settings, broker, panel, as_of, strategies=None, earnings=None, *, ledger=None,
  now=None) -> list[ExitAction]`; `ExitAction(kind: close|replace_stop|place_stop|cancel_order|flag, symbol, reason, qty, new_stop, order_id,
  client_order_id, strategy, side, ref_price, detail)`; `flag` is reported only, never executed.
- `execution.autopilot.run_autopilot(settings, secrets, as_of, broker, intents, reviews=None, exit_actions=None, dry_run=False, *,
  ledger=None, env=None) -> AutopilotReport`: kill switch -> reconcile -> mode (automatic approval `autopilot:paper` on a paper
  broker only; `autopilot:live` needs `execution.auto_submit_live` AND env SWING_ALLOW_LIVE=yes; otherwise staged to
  `runs/pending/<date>.json`) -> review vetoes -> exits -> entries (daily cap across runs, idempotent) -> audit
  `runs/autopilot/<date>.json`. All four names are exported from `swing_engine.execution`.
- `ops.nightly.run_nightly(settings, secrets, as_of, provider, equity, dry_run, *, store, broker, execute=None, ...)` and
  `run_cycle(settings, secrets, as_of, broker, dry_run, *, equity=None, store=None)`; orders leave only through the execute step,
  which holds entries when the review step failed or a signal was not reviewed (`execution.require_review_approval`).
  Steps (`STEP_NAMES`): ingest, float (skipped on dry runs and the sample provider), features (screened universe + index ETFs +
  held names; breadth to the `breadth` table), scan (playbook-routed; state saved to `runs/regime/<date>.json`; a playbook
  error fails the scan), rank, size (`risk_per_trade_pct x multiplier`), review, shadow (`research.shadow` record + grade),
  positions, execute, journal. Helpers: `compute_regime`, `route_strategies`, `screened_breadth`, `regime_name`,
  `regime_markdown`, `contract_fn`.

## monitor
- `monitor.service.run_monitor(settings, secrets, dry_run=False, feeds=None)`: asyncio supervisor; each Feed task -> queue ->
  `pipeline.process(event)`; staleness watchdog; graceful shutdown.
- `monitor.eventlog.EventLog(path)` sqlite WAL: `.append(event) -> bool` (False on duplicate), `.cursor(source)`, `.recent(hours)`.
- `monitor.dedup.Deduper` (provider id + simhash of normalized title+primary ticker within 30 min).
- `monitor.matcher.Matcher(tickers, aliases, keywords)` ahocorasick with the word-like-ticker guard; `.match(text) -> (symbols, keywords)`.
- `monitor.rules.*` register `@register("rule", name)`; `monitor.pipeline.Pipeline(rules, classifier, policy, deliverers)`.
- `monitor.classify.HaikuClassifier(model, api_key)` structured output -> `Classification`; tickers subset check; rules-only fallback.
- `monitor.alerts.AlertPolicy` cooldown/caps/quiet hours/routing P1-P3; `monitor.delivery.{telegram,pushover,ntfy,console}` deliverers.
- `monitor.smallcap.SmallCapTrack` runner detector: long triggers and avoid/dump warnings from settings.monitor.smallcap.
- `monitor.report.report(days)` (`notable` entries carry `event_id` and `rating`) and `monitor.replay.replay(days, rules)`.
- `monitor.rate.rate_alert(eventlog, event_id, rating, source, *, now=None) -> RatingResult` and `rate_cli(settings, event_id,
  rating) -> RatingResult` (`useful | noise | traded`; ValueError on anything else, `ok=False, reason='unknown_event'` for an unknown
  id); stored in `event.meta['rating']` plus the `alert_ratings` table. Telegram P2/P3 alerts carry the buttons
  (`TelegramDeliverer(rating_buttons=True)`); `monitor.service.TelegramUpdatesFeed` records presses from `TELEGRAM_CHAT_ID` only.

## agent
- `agent.client.get_client(secrets=None)` / `get_async_client(secrets=None)` anthropic clients (pass `Secrets`: the key lives in
  `.env`, which the SDK alone does not read); `agent.review.review_candidates(signals, context_by_symbol, settings, client=None) -> list[Review]`
  (Sonnet, structured output `Review`, cached system prompt from `agent/prompts/review_system.md`).
- `agent.journal.write_entry(date, signals, reviews, intents, fills) -> str` and `agent.strategy_lab.run(hypothesis: str, ...)`.

## cli (`swing`)
status | doctor | ingest (--mode auto|grouped|per-symbol) | universe | features | scan | backtest | rank | review | size |
paper (submit with --approve) | nightly (--execute/--no-execute, --broker) | autopilot (--dry-run) | monitor (run | report |
replay | outcomes | rate <event_id> <useful|noise|traded>) | journal | trials | regime (--as-of) | replay (--start, --end,
-s/--strategy, --no-router, --equity, --cost k=v; saves `runs/replay/<start>_<end>.json`, ledger `shadow_signals_replay`) |
shadow report (--since, --by, --horizon, --taken/--untaken, --replay, --all-columns).
`scan` and `size` are not routed by the playbook (they show every enabled strategy); `nightly` is, and `autopilot`
re-applies the multipliers saved in `runs/regime/<date>.json` for its signals day when that file exists.
