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

## strategies
- Each `Strategy.signals(panel, as_of, regime) -> list[Signal]`; use only panel columns from the contract; `score` for ranking;
  compute `reward_risk`. Provide `default_params`. Register `@register("strategy", name)`.

## research
- `research.backtest.run_backtest(strategy, panel, start, end, risk_cfg, costs: CostModel, market=None) -> BacktestResult`
  (next-open entry, stop/target/time exits, one position per symbol, portfolio-level sizing via risk.sizing, equity curve, trades df).
- `research.metrics.summarize(result) -> dict` (trades, win_rate, avg_r, profit_factor, cagr, max_dd, sharpe, turnover, cost_drag)
  and `deflated_sharpe(sharpe, n_trials, n_obs, skew, kurt) -> float`, `probability_backtest_overfit(...)`.
- `research.trials.log_trial(name, params, metrics, path='data/trials.jsonl')`, `trial_count(name|None)`.
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
replay | outcomes | rate <event_id> <useful|noise|traded>) | journal | trials.
