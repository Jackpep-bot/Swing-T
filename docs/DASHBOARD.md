# Dashboard

A local, read-only page that ties the engine together on one screen: the equity curve against SPY, open
positions with entry, stop and target on a chart, today's regime and allowed strategies, the shadow ledger's win
rates, recent alerts, and the reasoning behind every signal, including the ones that were not taken. It reads the
engine's own records, so it shows what the Alpaca dashboard cannot: why a trade exists and why the others don't.

It is free, runs on your Mac only (bound to `127.0.0.1`), uses the Python standard library for the server, and
**never places, replaces or cancels an order**. The only two things it writes are an alert rating (the same
`useful / noise / traded` as the Telegram buttons) and tripping the kill switch. Clearing the kill switch is
deliberately not possible from the page.

## Run it

```bash
uv run python -m swing_engine.dashboard --settings config/live.yaml --open   # the paper setup
uv run python -m swing_engine.dashboard --open                               # config/settings.yaml
uv run python -m swing_engine.dashboard --demo --open                        # fake data, no keys, no files
uv run python -m swing_engine.dashboard --port 8800                          # another port (default 8765)
```

Then open <http://127.0.0.1:8765/> (`--open` does it for you). Stop it with Ctrl-C. `--demo` serves
deterministic made-up data (fictional tickers, a pinned clock) for every panel, so the page can be tried or
screenshotted without keys; nothing on disk is read or written in demo mode, and its kill switch is in memory.

From code (for a future `swing dashboard` command): `swing_engine.dashboard.serve(settings_path, port, demo,
open_browser)`.

The page loads its chart library from `https://unpkg.com`. Without internet the tables and numbers still work
and the charts say they are unavailable.

## What each panel shows and where the numbers come from

Every number on the page is copied from a file or service the engine already writes; the dashboard computes only
presentation values (rebasing to 100, moving averages for the chart, R multiples, drawdown).

| Panel | Shows | Source |
|---|---|---|
| Top bar | mode (PAPER / LIVE / DEMO), equity, day P/L, cash, buying power, market open/closed, kill switch | Alpaca account via `execution.alpaca_broker.AlpacaBroker.account()`; without keys, the newest account snapshot in `data/runs/autopilot/<date>.json` (labelled as such). Clock: the NYSE calendar (`data.calendar`, offline). Kill switch: whether `risk.kill_switch_file` (`state/KILL`) exists, and its text |
| Nightly | last run date, pass/fail, each step with its detail and time | `data/runs/nightly/<date>.json` (the newest) |
| Monitor | last event time per feed, alerts delivered in the last 24 h | event log SQLite (`data.event_log_path`), `events` and `alerts` tables, opened read-only |
| Equity vs SPY | account equity and SPY, both rebased to 100 at the first common date; return, SPY return, max drawdown | account: Alpaca `GET /v2/account/portfolio/history` on the **paper** host (daily); without keys or on a live account, one point per autopilot audit file. SPY: daily closes from the DuckDB `bars` table |
| Positions | qty, entry, current price, P/L, strategy, original stop and target, current stop, risk per share, R multiple, days held vs the strategy's time stop | positions: Alpaca. Strategy and original stop/target: the order ledger (`state/orders.sqlite`, the intent the engine submitted), else the newest `runs/intents/<date>.json` that sized the symbol. Current stop: the open stop leg at Alpaca (moves when the position manager trails it). Days held: NYSE sessions since the fill. Time stop: the signal's own `max_hold_days`, else `settings.strategies.<name>`, else the strategy's default |
| Chart | daily candles, SMA 20 / 50, entry / stop / target / current-stop lines, markers for signals, entries and exits | bars from DuckDB `bars`; levels from the ledger and the open stop leg; markers from `runs/signals/*.json`, the ledger's fills and Alpaca's closed orders |
| Chart layers + Inspector | tick boxes with counts: signals taken, setups seen (shadow fires), refusals, entries, stops, targets, exits, support / resistance, regime shading; "Declutter" and "Everything" presets; a status line "N bars · N events · N fires · sig <engine_sig>". Clicking a drawn marker or line shows its receipt JSON in the Inspector | decision receipts (DuckDB `events`, `ops.receipts`) for the symbol and the dates on screen; `features.levels` support_1 / resistance_1 computed from the stored bars (point-in-time); regime from `runs/regime/<date>.json` and the receipts' own `payload.regime`. An outcome's entry and exit are drawn once per signal, not once per horizon |
| Intraday | one market day of candles for SPY, QQQ, IWM, GLD or BTC/USD at 2m to 4h, with market-structure event layers (pools, sweeps, manipulation legs, inducements, swing structure, structure breaks, MSS / failed, OB zones, FVG / inversions, session opens, rejections) and the same Inspector. OB and FVG zones are filled translucent boxes (fill green for bull, red for bear; edge in the layer colour) from the event to the zone's end (`t2`), or to the right edge while still live; they are painted by one chart-library series primitive, so they do not count against the 300-line limit | `data.intraday.read_bars` on the intraday store (`data.intraday_store_path`, opened read-only), then `features.market_structure.extract_events` on that day plus at least 350 prior bars of warm-up, on request, cached 60 s. Only events whose `ts_event` falls inside the day are drawn. The time axis is New York time for the ETFs and UTC for BTC/USD; receipts keep UTC. A vocabulary, not a strategy (`docs/market-structure.md`) |
| Orders | open or closed orders with bracket legs and the strategy behind each | Alpaca (`open_orders()`, closed orders read-only); without keys, the order ledger |
| Regime | today's regime, SPY trend, volatility, breadth, the router's notes, allowed strategies with their risk multiplier, breadth history | `runs/regime/<date>.json` (written by the nightly scan from `strategies.playbook`); falls back to the nightly report's scan step. Breadth history: DuckDB `breadth` table (the features step) |
| Signals | every signal of a day: levels, R:R, score, rank, **taken or not and why**, Claude's review (decision, thesis, event-risk flags) | `runs/signals/<date>.json` joined to `runs/reviews`, `runs/intents`, `runs/autopilot` (vetoed / capped / staged / dry run), the size step's skips in the nightly report, and the order ledger |
| Shadow ledger | per strategy or per regime: graded signals, win rate, average R, expectancy, profit factor, pending | DuckDB `shadow_signals` summarised with `research.shadow.summarize_outcomes` (taken and not-taken signals are graded the same way; `pending` and `entry_skipped` are excluded from the R statistics) |
| Alerts | P1-P3 alerts of the last 48 h with rules hit and your rating; rate them in place | event log `events` (priority above P0 or in `alerts`), `alerts` for delivery, `meta.rating` / `alert_ratings` for ratings. Rating writes through `monitor.rate.rate_alert` (source `dashboard`), exactly like `swing monitor rate` |
| Journal | the day's journal entry | `data/journal/<date>.md` (`agent.journal`) |
| Replay | historical replay runs, the latest one's summary, per-strategy and per-regime tables and equity curve | `runs/replay/<id>.json` (written by `swing replay`) |
| Coverage (Overview) | tiles: days covered, events, fires, refusals, outcomes, studies (all-time); a heatmap of receipts per day for the last 60 days, by strategy or by symbol (the 40 busiest). A strategy cell lists that day's receipts (click a row for its JSON); a symbol cell opens its chart | DuckDB `events`; the studies count is the number of study files |
| Studies | the auto-written study of each session, newest first | `<data.studies_dir>/<date>.md` (`ops.study`, default `docs/studies`), shown through the page's own escaping markdown renderer |
| Vocabulary | every registered strategy with its one-line definition, status and evidence grade; the 21 market-structure event kinds with their definitions; dated operator rulings | `ops.vocabulary` (strategy cards, `docs/rulings.md`, the kind paragraphs of `docs/market-structure.md`) |

### Why a signal was not taken

The Signals panel answers it in this order: the order ledger shows the order was sent (taken); the autopilot
audit says `vetoed` (Claude's review said reject / needs_more_info, or the signal was not reviewed), `capped`
(`execution.max_new_orders_per_day`), `refused` (risk limits or the kill switch), `staged` (live account, waiting
for a human); the size step skipped it (reward:risk below the floor, sector or position caps); no intent was made
(no equity, or the regime gave the strategy a zero multiplier); or it was only planned in a dry run.

Claude's review is shown next to each signal. When the latest review step for that day was skipped (no
`ANTHROPIC_API_KEY`), failed or never finished (`runs/review_status/<date>.json`), a reviews file still on disk
is from an earlier run and was not applied: the page marks those reviews "(earlier run)", leaves them out of the
reviewed / vetoed counts and says why above the table.

Under each panel a small note says when a number is not first-hand: a cached copy served while the store was
locked, the account read from an autopilot audit file instead of Alpaca, orders read from the order ledger, or a
part that could not be read (for example SPY bars that end before the account history starts). A brand-new
paper account has no previous close, so "Today" shows a dash rather than the whole balance as a gain.

## Data freshness and the DuckDB lock

DuckDB allows one writer per file and refuses a read-only open while a writer is attached. The dashboard opens the
store read-only for one query at a time and closes it at once, and reuses each result for 60 seconds. When a
backfill, an ingest or the nightly holds the lock, panels that need the store show the last good copy with a
"stale" note (when, and why); a panel that was never loaded says it is waiting for the writer. Broker reads are
reused for 15 seconds and portfolio history for 60 seconds, so leaving the page open does not hammer Alpaca.

DuckDB locks work both ways: while the dashboard's read-only connection is open, a writer cannot open the file.
Each open lasts a few milliseconds and happens at most about once a minute per panel, so a collision with the
06:30 nightly or a manual `swing ingest` is very unlikely; if one happens, that command fails at start with a
DuckDB lock error and simply needs re-running. Closing the page (or stopping the dashboard) removes the chance
entirely.

## API

JSON over HTTP on `127.0.0.1` only. Every endpoint answers HTTP 200 with `{"ok": true, "data": ...}` or
`{"ok": false, "unavailable": "<reason>"}`; missing data is a reason, never a server error. A successful answer
may also carry `stale` (served from cache while the store was locked), `partial` (`{section: reason}` for the
parts that could not be read) and `source`; for dict-shaped `data` these are mirrored inside `data` too. Bad
parameters are HTTP 400, a non-local `Host` 403, unknown routes 404.

| Endpoint | Data |
|---|---|
| `GET /api/health` | version, settings and store paths, demo flag, whether the page files exist |
| `GET /api/summary` | mode, account, kill_switch, nightly, monitor, clock, generated_at |
| `GET /api/regime?date=YYYY-MM-DD` | state, allowed, blocked, breadth_history |
| `GET /api/equity?period=1M\|3M\|6M\|1Y\|ALL` | account, spy, normalized, stats |
| `GET /api/positions` | one row per open position |
| `GET /api/orders?status=open\|closed&limit=50` | orders with legs |
| `GET /api/chart/{SYMBOL}?days=180` | bars (calendar days back from the last stored bar), sma20, sma50, levels, markers |
| `GET /api/chart/{SYMBOL}/layers?start=&end=` | layers (key, label, count, default), objects (`{id, layer, shape: marker\|line\|zone\|band, t, t2, price, price2, dir, text, ref}`), receipts (`ref` -> the event row), status (events, fires, refusals, outcomes, engine_sig) |
| `GET /api/intraday/{SYMBOL}?day=YYYY-MM-DD&tf=2m\|5m\|15m\|30m\|1h\|4h` | SYMBOL is SPY, QQQ, IWM, GLD or BTC-USD; day defaults to the latest stored. bars (`t` = wall-clock seconds on the market's clock), layers, objects, receipts, status (bars, events, warmup_bars, extractor_version, engine_sig), first_day, last_day |
| `GET /api/signals?date=YYYY-MM-DD` | the day's signals with taken / skip_reason / review (`review.current` is false when the latest review step did not produce it), review_status |
| `GET /api/shadow?by=strategy\|regime` | rows, updated_at |
| `GET /api/events?as_of=&strategy=&symbol=&kind=&limit=` | events (decision receipts, newest first; `payload` is the JSON that decided each one), count |
| `GET /api/alerts?hours=48` | alerts, newest first |
| `POST /api/alerts/{event_id}/rate` `{"rating": "useful"\|"noise"\|"traded"}` | event_id, rating |
| `GET /api/journal?date=YYYY-MM-DD` | date, markdown, available_dates |
| `GET /api/studies` | studies (date, title, bytes), newest first |
| `GET /api/studies/{YYYY-MM-DD}` | date, markdown, available_dates. The path part must be a calendar date; nothing else reaches the file name |
| `GET /api/coverage?days=60` | tiles, days, strategies and symbols (`rows`: key, total, cells `{day: n}`) |
| `GET /api/vocabulary` | rulings_for_everything, strategies, structure (section, kinds, definition, rulings), structure_doc |
| `GET /api/replay` | runs, latest (`units: "fraction"`: returns, CAGR, drawdown and win rate as fractions) |
| `POST /api/killswitch/trip` `{"confirm": "TRIP"}` | tripped, path |

There is no endpoint to clear the kill switch. Clear it on the computer after journaling the cause
(`rm state/KILL`, see `docs/OPERATIONS.md` section 6).

## Security

- Listens on `127.0.0.1` only; requests whose `Host` header is not `localhost`, `127.0.0.1` or `[::1]` are refused
  (stops DNS-rebinding attacks from a web page you visit).
- POSTs must be `Content-Type: application/json`, at most 2 KB, and same-origin when the browser says where they
  come from, so another website cannot rate alerts or trip the switch through your browser. No CORS headers are
  sent, so other sites cannot read the data either.
- Content-Security-Policy allows scripts from the page itself and `https://unpkg.com` only (inline scripts by exact
  hash); `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, framing denied.
- Static files are served only from `swing_engine/dashboard/static/`, by extension allow-list, with no `..`,
  hidden files or symlinks out of the folder.
- No key, token or secret from `.env` or the environment ever appears in a response: every value is scrubbed from
  every body before it is sent. Alpaca keys travel only in request headers to the paper host.
- Inputs are validated: dates `YYYY-MM-DD`, symbols `^[A-Z.-]{1,10}$`, bounded integers, enum choices.
- On a live account (`ALPACA_PAPER=false`) the page shows LIVE and reads the account only when
  `SWING_ALLOW_LIVE=yes` is set (the same guard as the broker adapter); it still never trades.
