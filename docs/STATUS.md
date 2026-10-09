# Project status: RUNNING (third session, 2026-10-08)

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

## Resume here (in order) - updated 2026-10-09 14:30 ET
v2 results (repaired store with ~2,800 delisted names, insider/VIX/French data, per-stock spread costs):
docs/leaderboard.md over 794 trials - NO survivors; 128 cards updated. Stores: data/live/replay_r2.duckdb (2024-26 +
2017-24 chunks 7-8), data/live/replay_r1.duckdb (2017-24 chunks 1-6). Paper trading off; the launchd nightly ran on
its own 2026-10-09 (21 shadow strategies, weekly report data/journal/weekly-2026-W41.md).

Next (needs Jack's direction): the data and strategy catalog are exhausted without a survivor. Options in
docs/methods.md "Order of work": combine weak signals (ranker / signal combination) instead of single strategies,
bootstrap reality check / SPA across the 794 trials, longer shadow-ledger evidence before any paper trading.

## Research commands
- Full research pass (every registered strategy, both windows, parallel lanes sized from free memory up to 40 GB,
  cards + leaderboard + Telegram summary at the end; refuses on battery and while the live store is being written):
  `nohup uv run swing --settings config/live.yaml research run --windows short,long > /dev/null 2>&1 &`
  Progress `tail -f data/logs/research/<run-id>.log`; manifest `data/live/runs/research/<run-id>.json`.
- Resume unfinished chunks: `uv run swing --settings config/live.yaml research run --resume latest`.
- Cards + leaderboard again over the latest run's lane stores: `uv run swing --settings config/live.yaml research rebuild`.
- The old scripts/lane_r*.sh and run_research_replays.sh are gone; replay_r1/r2.duckdb stay as the v2 record.
