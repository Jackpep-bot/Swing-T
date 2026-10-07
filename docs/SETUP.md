# First-run setup (owner's guide)

This walks you from a fresh checkout to a running paper-trading loop: real daily bars from Massive, a
scan/backtest/size/paper cycle against an Alpaca **paper** account, the live monitor pushing alerts to your
phone, and the nightly job scheduled. Budget about 90 minutes, most of it waiting for account e-mails and the
first ingest.

Hard rules you are agreeing to (from `CLAUDE.md`): paper keys only until the gates in section 6 are met; the
language model never produces a number that reaches an order; `state/KILL` blocks every order path.

Vendor facts below were checked against the vendors' pages on 2026-10-06. Prices and limits change; the
"verify" links are where to re-check.

## 0. Prerequisites (10 min)

| Need | How | Check |
|---|---|---|
| macOS or Linux, 2 GB free disk | `data/swing.duckdb` is ~40 MB for 60 symbols x 5 years; budget 1-2 GB for a 1,500-name universe | `df -h .` |
| `uv` (Python manager) | run the standalone installer `curl -LsSf https://astral.sh/uv/install.sh` piped into `sh`; it installs to `~/.local/bin/uv` (verify: https://docs.astral.sh/uv/getting-started/installation/) | `uv --version` |
| Python 3.12/3.13 | `uv` downloads it on first sync | `uv run python --version` |
| Project deps | `uv sync --extra dev` from the repo root | `uv run swing --help` |
| Optional: LightGBM on macOS | `brew install libomp` (without it `swing rank train` silently uses the scikit-learn fallback; nothing else is affected) | `uv run python -c "import lightgbm"` |
| Optional: `sqlite3` CLI | ships with macOS; `apt install sqlite3` on Debian/Ubuntu (used by `scripts/backup-data.sh`) | `sqlite3 --version` |

```bash
cd ~/Desktop/swing-engine
uv sync --extra dev
cp .env.example .env
chmod 600 .env            # it will hold keys; never commit it (.gitignore already excludes it)
uv run pytest -q          # 597 tests, no network; proves the install before any key is involved
```

## 1. Accounts and keys (40 min, mostly waiting)

One row per key. Fill `.env` as you go; the variable names are exactly those in `.env.example`.

| Service | Used for | Cost | `.env` variable(s) |
|---|---|---|---|
| Massive (ex-Polygon), Stocks Basic | daily bars, reference data, splits | $0 | `MASSIVE_API_KEY` |
| Alpaca paper account | equity/positions, paper orders, news + halt + account websockets | $0 | `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_PAPER=true` |
| Telegram bot | P1/P2 alerts, digests | $0 | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| Anthropic (Claude) | Haiku classifier, Sonnet candidate review, Opus strategy lab | usage-based | `ANTHROPIC_API_KEY` |
| Pushover (optional) | P3 emergency alerts that repeat until acknowledged | $4.99 once per platform | `PUSHOVER_USER_KEY`, `PUSHOVER_APP_TOKEN` |
| SEC EDGAR | 8-K / Form 4 feeds | $0, needs a contact e-mail | `EDGAR_USER_AGENT` |
| Alpha Vantage (optional) | earnings calendar (blackout) | $0 | `ALPHAVANTAGE_API_KEY` |
| EODHD, Quiver (optional) | alternative bars; insider/congress data | paid | `EODHD_API_KEY`, `QUIVER_API_KEY` |

### 1.1 Massive: free "Stocks Basic"

1. Sign up at https://massive.com/dashboard/signup (verify plans at https://massive.com/pricing).
2. Pick **Stocks Basic** ($0/month). Facts that shape everything below: **5 API calls per minute**, **2 years**
   of history, 15-minute-delayed data. Starter ($29) is unlimited calls, 5 years, flat files.
3. Copy the key from https://massive.com/dashboard/keys into `MASSIVE_API_KEY=`.
4. Keep `data.bar_provider: massive` in `config/settings.yaml` (already the default).

Why the 5 calls/min matters: the provider fetches daily bars with **one aggregates call per symbol per ingest**
(`/v2/aggs/ticker/{symbol}/range/1/day/...`; a page holds 50,000 bars, so 2 years of dailies is one call).
The default screened universe is `universe.max_symbols: 1500`, which is 1,500 calls = **300 minutes every night**,
on top of ~33 paged calls to list the 32k active+delisted tickers. That does not fit between the 18:00 ET
FINRA files and the 06:30 nightly, so on Basic you run a **starter universe** (section 2.3) and move to
Starter ($29, unlimited calls, flat files) when you want the full screen or more than 2 years of history.

### 1.2 Alpaca: paper account and paper keys

1. Create an account at https://app.alpaca.markets/signup (paper trading needs no funding or identity
   verification; the paper account starts with a simulated $100,000; verify at
   https://docs.alpaca.markets/docs/paper-trading).
2. In the dashboard switch the account selector (top left) from Live to **Paper**. Open the paper overview and,
   under "API Keys", choose **Generate New Keys**. The secret is shown once.
3. Put them in `ALPACA_API_KEY=` and `ALPACA_SECRET_KEY=`. Leave `ALPACA_PAPER=true`. The broker adapter raises
   `LiveTradingBlocked` if `ALPACA_PAPER=false` unless the shell also has `SWING_ALLOW_LIVE=yes`, and that is
   gated by section 6.
4. Market data on the free **Basic** plan (verify: https://docs.alpaca.markets/docs/about-market-data-api):
   IEX prints only, **30 symbols per websocket subscription**, 200 REST requests/min. Consequences for the
   monitor are in section 4. Algo Trader Plus ($99/month) lifts this to SIP (all exchanges), unlimited
   symbols and real pre-market coverage; it is a go-live cost, not a paper cost.
5. The news websocket (Benzinga headlines) is expected to work on Basic; `swing doctor --live` confirms it with
   your key, which is the only real test.

### 1.3 Telegram: bot token and chat id

1. In Telegram open https://t.me/botfather and send `/newbot`. BotFather asks for a display name and a username
   ending in `bot`, then replies with a token shaped like `<bot id digits>:<35-character secret>`
   (verify: https://core.telegram.org/bots/features#botfather). Put it in `TELEGRAM_BOT_TOKEN=`.
2. Open the chat with your new bot and send it any message (`/start` is fine). The bot cannot message you first.
3. Get the chat id with `getUpdates` (verify: https://core.telegram.org/bots/api#getupdates):
   ```bash
   curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" | python3 -m json.tool
   ```
   Look for `"message": {"chat": {"id": 123456789, ...}}` in the first result. That number is
   `TELEGRAM_CHAT_ID=`. For a private chat it is positive; for a group it is negative (supergroups start with
   `-100`). Group use: add the bot to the group, send a message there, call `getUpdates` again.
4. If `result` is empty: you have not messaged the bot yet, or a webhook is set on the token (call
   `https://api.telegram.org/bot<TOKEN>/deleteWebhook` once). Bots in groups only see commands unless privacy
   mode is off (`/setprivacy` in BotFather); for a private chat this does not matter.
5. Test delivery end to end:
   ```bash
   curl -s -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage" -d chat_id=<CHAT_ID> -d text="swing-engine test"
   ```

### 1.4 Anthropic API key

1. Sign in at https://platform.claude.com, go to **Settings -> API keys**
   (https://platform.claude.com/settings/keys), **Create key**, choose "personal", copy the `sk-ant-...` value
   (shown once; verify: https://platform.claude.com/docs/en/get-api-key). Put it in `ANTHROPIC_API_KEY=`.
2. Add a small prepaid balance ($10 is plenty for a paper month; section 5).
3. Models used (set in `config/settings.yaml`): `claude-haiku-4-5` for the monitor's stage-2 classifier,
   `claude-sonnet-5-5` for `swing review`, `claude-opus-5-5` for the strategy lab. Prompt caching needs a
   prefix of at least **4,096 tokens on Haiku 4.5** (512 on Sonnet/Opus 5.5; verify:
   https://platform.claude.com/docs/en/build-with-claude/prompt-caching); the classifier pads its frozen system
   prompt past that minimum automatically (`monitor/classify.py: pad_prompt`), so cache reads cost 0.1x input.

### 1.5 Pushover (optional, recommended for P3)

1. Create an account at https://pushover.net; the **user key** is on the dashboard after login. Put it in
   `PUSHOVER_USER_KEY=`.
2. Register an application at https://pushover.net/apps/build (free) to get the **API token** ->
   `PUSHOVER_APP_TOKEN=` (verify: https://pushover.net/api).
3. Install the phone app. It is free for 30 days, then a **$4.99 one-time** purchase per platform; 10,000
   messages/month are included (verify: https://pushover.net/pricing).
4. P3 alerts are sent with emergency priority, which **repeats every 30 s until you acknowledge on the phone**
   (`PUSHOVER_EMERGENCY_RETRY_S` / `_EXPIRE_S` in `monitor/constants.py`). Both Telegram and Pushover can be
   configured; the alert policy routes by priority.

### 1.6 EDGAR contact and the optional keys

- `EDGAR_USER_AGENT="swing-engine you@example.com"`: the SEC fair-access policy requires a User-Agent of the
  form "Company Name AdminContact@domain.com" and caps you at 10 requests/second (verify:
  https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data). The EDGAR client refuses to
  start without an `@` in this string, and sec.gov answers 403 for about 10 minutes once you trip the limit.
- `ALPHAVANTAGE_API_KEY`: free key from https://www.alphavantage.co/support/#api-key, **25 requests/day**;
  the earnings calendar is one request, used nightly.
- Leave `EODHD_API_KEY`, `QUIVER_API_KEY` and `FMP_API_KEY` empty unless you bought them; everything degrades
  gracefully (`FMP_API_KEY` only adds a vendor float figure to the small-cap track; EDGAR is the primary source).

## 2. First run, in order

Run every command from the repo root with `uv run`. Each step says what success looks like and the usual
reasons it does not.

### 2.1 `uv run swing status` (no network)

Prints three tables: **Secrets** (one row per key: `set`, `missing`, or `default`; values are never printed),
**Configuration** (settings file, bar provider, store path and whether it exists, event log path,
`paper mode (ALPACA_PAPER) True`, `kill switch clear (…/state/KILL)`, trials logged, enabled strategies,
monitor feeds) and **Registered plugins** (bar providers `sample, massive, eodhd, alpaca`; strategies; brokers
`alpaca, paper_sim`; feeds; rules; deliverers). If a key you filled shows `missing`, the `.env` line is
malformed (no spaces around `=`, quotes only around values with spaces).

### 2.2 `uv run swing doctor --live`

`uv run swing doctor` without flags runs the offline checks only (no network; safe at any time).
Offline checks run always: `env_file` (which keys are set; values are never printed), `settings_yaml`,
`store_path` writable, `calendar`, `registry_plugins`, `kill_switch`, `limits_state`, `python` and package
versions. With `--live` it adds one cheap request per vendor whose key is set (Massive, the Alpaca paper
account and data endpoint, Alpha Vantage, Telegram `getMe`, Pushover, Anthropic, EDGAR with your User-Agent)
plus the public feeds (Nasdaq halts); `--send-test` additionally posts one message to `TELEGRAM_CHAT_ID`, which is the end-to-end proof
that alerts will reach your phone. Output is a table `check | status | detail` with `ok`, `warn`, `fail` or
`skip` (no key), then a count line such as `ok=12, skip=3`; exit code 1 if anything failed. `ALPACA_PAPER=false`
shows as a warning, an `EDGAR_USER_AGENT` without an e-mail fails before any request. Fix every `fail` before
continuing; the detail column is the vendor's message with secrets redacted. Appendix A has the equivalent
`curl`s if you want to see raw responses.

### 2.3 `uv run swing ingest --provider massive` (grouped backfill, or a starter list)

`swing ingest --mode auto|grouped|per-symbol` (default `auto`). **Grouped** fetches one session for the whole
US market per call (Massive grouped daily), so its cost depends on the number of sessions, not symbols.
**Per-symbol** makes one call per symbol (chunked). `auto` picks grouped when the provider supports it (Massive)
and you named no symbols (`--symbols` empty and `universe.static_symbols: []`, the shipped setting); otherwise
per-symbol. `--mode grouped` together with `--symbols` is refused.

**Grouped, the recommended path** (full screened universe, survivorship-aware):

```bash
uv run swing ingest --provider massive                 # grouped; prints an estimate first, then progress
uv run swing ingest --provider massive --start 2024-10-07   # same, capped to Basic's 2-year window
```

- Free tier (Basic, 5 calls/min = 12 s per call): 2 years is ~500 sessions, so **about 1 h 40 min**, plus a
  handful of reference-list calls (the common-stock, ETF and delisted lists are paged once and cached 7 days
  under `data/raw/massive/`). The estimate line counts every session in `data.history_years` (5 years:
  ~1,250 sessions, "~4 h"); on Basic the walk stops by itself at the plan's 2-year limit (the first HTTP 403
  on an older session) and remembers it, so the real time is the 2-year figure. `--start` avoids the overstated
  estimate.
- Resumable: each session is written as it arrives and recorded in the store table `ingest_grouped_days`.
  Ctrl-C (or a sleeping laptop) loses at most the session in flight; re-run the same command to continue.
  Progress prints every 10 sessions.
- Nightly refresh: one call per new session plus one splits call (names that split get their stored history
  refetched), i.e. ~2 calls / ~25 s on a normal day. A session that is not published yet (before the close)
  counts as pending, not as an error. Three failed sessions in a row (e.g. a bad key) stop the run.
- Paid plan: set `data.massive_calls_per_min` in `config/settings.yaml` (or export `MASSIVE_CALLS_PER_MIN` in
  the shell, which wins; it is not read from `.env`), e.g. 100, and the same backfill takes minutes.
- The universe is then screened from the stored bars (no extra bar calls). Known survivorship gap: a common
  stock that delisted (or changed ticker) before the backfill window and was never seen in an earlier snapshot
  is missing; the gap shrinks the longer the nightly runs.

Prints `Ingest via massive` with `mode grouped`, `sessions`, `sessions_fetched`, `sessions_present` (already
stored), `plan_limit_at` (where Basic's history ends), `sessions_remaining` (non-zero after a stopped run),
`bars_written`, `splits_repaired`, `estimate_s` and `errors`.

**Per-symbol starter list** (when you want a fixed 40-name list instead): pin it in `config/settings.yaml`, which
also makes `auto` pick per-symbol:

```yaml
universe:
  static_symbols: [SPY, AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, AVGO, AMD, NFLX, CRM, ORCL, ADBE,
                   INTC, QCOM, JPM, BAC, GS, V, MA, XOM, CVX, UNH, JNJ, PFE, MRK, LLY, HD, COST, WMT,
                   NKE, DIS, BA, CAT, HON, SLB, UBER, PLTR, COIN]
```

```bash
uv run swing ingest --provider massive --start 2024-10-01     # ~8 min for 40 symbols at 5 calls/min
```

Keep `SPY` in the list (the regime features need it). Prints `symbols_requested 40`, `symbols_with_bars 40`,
`bars_written ~20000`, `errors []`. Later runs are incremental but still one call per symbol: 40 symbols =
8 minutes a night, 300 symbols = 1 hour, which is why grouped mode is the default for a screened universe.
`--symbols AAPL,MSFT` overrides the list for a one-off (always per-symbol); only names missing from the store's
`symbols` table cost an extra metadata call.

### 2.4 `uv run swing features`

Builds the 64-column feature panel from the stored bars and caches it to the DuckDB table `panel`. Prints the
row count, symbol count and date range. Takes seconds for 40 symbols. The first ~200 trading days per symbol
have NaNs in the long-window columns (sma_200, 12-1 momentum); that is expected.

### 2.5 `uv run swing scan`

Runs the enabled strategies as of the last trading day. Prints `universe as of <date>: 40 symbols`, a table of
`Signal`s (symbol, strategy, side, entry, stop, target, reward_risk, score) and
`saved N signals to data/runs/signals/<date>.json`. Zero signals on a given day is normal for a 40-name
universe; try `--as-of` on a few earlier dates to see the output shape.

### 2.6 `uv run swing backtest pullback_trend --start 2025-06-01`

Walk-forward backtest with modeled costs (next-open entry, stop/target/time exits). Prints
`Backtest pullback_trend <start>..<end>` (params, sizer, costs, trades, win_rate, avg_r, profit_factor, cagr,
max_dd, sharpe, turnover, cost_drag) and `Significance (trial-count aware)` (sharpe, deflated sharpe, trials
logged for this strategy and in total). Every run appends to `data/trials.jsonl`; that count is what the
deflated Sharpe is judged against, so do not `--no-log` real experiments. On Basic you have 2 years of bars
and the panel needs ~400 calendar days of warm-up, so start dates before mid-2025 just shorten the warm-up.

### 2.7 `uv run swing review` (optional, needs `ANTHROPIC_API_KEY`)

Sends today's signals plus context to Sonnet with a cached rubric and saves `Review`s (enum decision + short
text, no numbers) to `data/runs/reviews/<date>.json`. `--dry-run` prints the prompt without calling the API.
`size` uses the reviews only as a filter on `decision`.

### 2.8 `uv run swing size --broker alpaca`

Reads equity and open positions from the paper account, applies fixed-fractional sizing (`risk_per_trade_pct
1.0` of equity / per-share risk), the per-strategy reward:risk floor and the position/sector caps. Prints
`Order intents as of <date> (k of n signals; equity 100,000)` with qty, entry_limit, stop, target, risk $ and a
`client_order_id`, a `Skipped by risk.sizing` table with the reason per rejected signal, and
`saved k intents to data/runs/intents/<date>.json`. Without `--broker` you must pass `--equity`.

### 2.9 `uv run swing paper --broker alpaca --approve "Your Name"`

Submits the saved intents as bracket orders (entry + stop + target) through `OrderManager`. It refuses without
`--approve` (2+ characters), when `state/KILL` exists, when `ALPACA_PAPER` is false without the override, and
when a limit (daily loss, drawdown, open positions, sector) would be breached. Prints
`Paper submissions via alpaca approved by <name>` (symbol, qty, client_order_id, status/order id or reason)
and saves `data/runs/fills/<date>.json`. Check the orders in the Alpaca paper dashboard; `--reconcile` pulls
fills back. Re-running is safe: `client_order_id` makes submission idempotent. This is the manual path; once
the nightly runs with execution on (2.11) the autopilot does this step on the paper account by itself.

### 2.10 `uv run swing monitor run`

First `uv run swing monitor run --dry-run`: replays a fixture feed through dedup -> rules -> policy and prints
the alerts to the console without delivering anything. Then the real thing:

```bash
uv run swing monitor run            # Ctrl-C stops it cleanly (drains in-flight work, up to 30 s)
```

Expect log lines `monitor_start`, `held_positions_loaded` (symbols from the paper account),
`bar_engine_ready`, then one connect/auth line per feed (`alpaca_news`, `alpaca_stocks`, `alpaca_account`,
`edgar`, `nasdaq_halts`) and after that only events. Outside 04:00-20:00 ET the feeds are mostly silent;
the staleness watchdog is market-hours aware and will not page you at night. Send yourself a test by adding a
liquid name to `monitor.watchlist` and waiting for its next headline, or run `swing monitor replay --days 1`.
Leave it running in a terminal for the first day; then install it as a service (`deploy/README.md`).

P2 and P3 alerts on Telegram carry three buttons, **Useful / Noise / Traded**. The running monitor long-polls
the bot for presses, records the rating on the event in `data/events.sqlite` and answers the press (the button
spinner stops). Only presses from `TELEGRAM_CHAT_ID` count (in a private chat, only from you); anything else is
logged and ignored. `--dry-run` never polls. From a terminal: `uv run swing monitor rate <event_id> useful|noise|traded`
(exit 5 when the event id is not in the log). How to use the ratings: `docs/OPERATIONS.md` section 4.

### 2.11 `uv run swing nightly` (and `swing autopilot`)

One command for the chain the scheduler runs each morning, each step timed and isolated: ingest
(incremental) -> features -> scan -> rank (when `data/ranker.pkl` exists) -> size -> review (Claude; vetoes
entries by decision) -> positions -> execute -> journal. Prints `Nightly <date> via massive, execute via alpaca`
as a table `step | status | seconds | detail` (`ok`, `fail`, `skip`), then `Files written` (signals, intents,
reviews, exits, autopilot audit, journal and the report `data/runs/nightly/<date>.json`). A failed step does
not stop the later ones; the exit code is 1 if any failed.

**Paper auto-executes by default.** As shipped, `execution.broker: alpaca` and `execution.nightly_execute: true`:
the nightly reads equity and open positions from the Alpaca account (`ALPACA_PAPER=true`), and the execute step
hands the sized, reviewed intents and the exit decisions to `execution.autopilot`, which

1. refuses entries, closes and stop changes while `state/KILL` exists (it only cancels resting unfilled entries);
2. reconciles the order ledger (`state/orders.sqlite`) with the broker;
3. approves automatically **only on a paper broker** (Alpaca with `ALPACA_PAPER=true`, or `paper_sim`) as
   `autopilot:paper`. A live account needs both `execution.auto_submit_live: true` in `settings.yaml` **and**
   `SWING_ALLOW_LIVE=yes` in the environment of the process (the shell or the service unit; it is not read from
   `.env`); otherwise nothing is sent and the plan is staged to `data/runs/pending/<date>.json`;
4. drops entries Claude vetoed (`reject` / `needs_more_info`); when the review step **failed**, or a signal was
   never reviewed while others were, the entry is held, not sent (`require_review_approval: true`). With no
   `ANTHROPIC_API_KEY` at all the review step is skipped and entries go through unreviewed;
5. runs exits first (position manager: cancel an entry still unfilled after
   `cancel_unfilled_entries_after_sessions`, stop to breakeven at +1R, trail from +2R to the lowest low of the
   last 10 sessions, flatten before earnings once an `earnings` table exists), then entries as GTC bracket
   orders (entry + stop + target; the legs carry across days, Alpaca cancels GTC after 90 days);
6. caps new orders at `execution.max_new_orders_per_day` (5) per date, counted across runs, and is idempotent
   on `client_order_id`, so a re-run reports `duplicate` instead of sending again;
7. appends an audit to `data/runs/autopilot/<date>.json` (every entry with its outcome: `submitted`, `vetoed`,
   `capped`, `duplicate`, `refused`, plus the account snapshot and limit state).

Useful switches: `--no-execute` (everything except orders), `--dry-run` (no Claude calls, never executes; data
still refreshes), `--broker paper_sim` (the in-memory simulator: nothing leaves the machine), `--equity N` (size
against N instead of the broker's equity). If the broker cannot be opened (keys missing, Alpaca down) the data
steps still run and the nightly exits non-zero when execution was intended.

`uv run swing autopilot [--dry-run]` runs size -> positions -> execute alone from the latest saved signals and
their reviews (refuses signals older than `execution.max_signal_age_days`, still manages positions); its report
is `data/runs/cycle/<date>.json`. Use it to re-plan after a kill-switch incident or a failed execute step.

Once it runs clean by hand, schedule it: `scripts/install-launchd.sh` on the Mac or the systemd units on a VPS
(`deploy/README.md`). To keep the scheduled run plan-only, set `execution.nightly_execute: false` (or put
`--no-execute` in `SWING_NIGHTLY_ARGS`) and submit with `swing paper` yourself.

## 3. Daily loop in one screen

```
06:30 ET  nightly (scheduled)      ingest -> features -> scan -> rank -> size -> review -> positions -> execute -> journal
                                   (paper: the autopilot submits up to 5 bracket orders and manages stops/exits)
08:30 ET  P1 digest on Telegram    pre-market gappers, filings overnight, today's candidates
09:00     you                      read data/journal/<date>.md and data/runs/autopilot/<date>.json; cancel in the
                                   Alpaca dashboard anything you disagree with (or `touch state/KILL` before 06:30)
09:30-16  monitor (always on)      P2/P3 to your phone; tap Useful / Noise / Traded (docs/OPERATIONS.md)
15:45 ET  P1 digest                positions, stops, what the ranker likes for tomorrow
18:30 ET  P1 digest                after-hours filings, next-day calendar
weekly    you                      `swing monitor report --days 7`, `swing monitor outcomes --days 30` (docs/OPERATIONS.md)
```

## 4. Common failures and fixes

| Symptom | Cause | Fix |
|---|---|---|
| `edgar: user_agent must include a contact email` at start-up | `EDGAR_USER_AGENT` has no `@` | `EDGAR_USER_AGENT="swing-engine you@example.com"` |
| EDGAR feed logs `403` and goes quiet for ~10 min | SEC fair-access limit tripped (no contact in User-Agent, or > 10 req/s from your IP) | fix the User-Agent; the adapter backs off `EDGAR_FORBIDDEN_RETRY_S = 600` s on its own; do not run two monitors from one IP |
| Massive ingest crawls, `429` in logs, or hours for a few hundred names | Basic tier: 5 calls/min, and per-symbol mode costs one call per symbol | empty `universe.static_symbols` and no `--symbols` so `auto` uses grouped mode (one call per session, any number of names); or buy Starter ($29, unlimited) and set `data.massive_calls_per_min`; the token bucket already paces calls so 429s mean another client shares the key |
| `provider massive returned no bars for 2021..` | Basic has 2 years of history | `--start` within the last 2 years, or Starter (5 y) / Developer (10 y) |
| `alpaca_stocks` logs `405 symbol limit exceeded` or `409 insufficient subscription` | Basic plan: 30 symbols per websocket, no `*` wildcard | set `monitor.watchlist` to <= 30 symbols (held positions first, then candidates); Plus removes the cap |
| `406 connection limit exceeded` on an Alpaca websocket | a second connection to the same endpoint (another monitor, a notebook, or the nightly) | one Alpaca socket per endpoint: stop the other process; the nightly job uses REST only |
| Small-cap runner alerts say "degraded", pre-market gaps look wrong | IEX feed on Basic misses most pre-market prints; effective coverage ~08:00-17:00 ET | expected on paper; Algo Trader Plus (SIP, 04:00-20:00) at go-live |
| `cache_read_input_tokens` stays 0 / classifier cost higher than expected | system prompt shorter than the 4,096-token Haiku minimum, or the prefix changes per call | keep `monitor/prompts/classify_system.md` frozen; padding is automatic; a changed prompt invalidates the cache once |
| `ANTHROPIC_API_KEY is not set; use --dry-run` | key empty | fill it, or run `review --dry-run`; the monitor falls back to rules-only priorities without it and still delivers P3 |
| `ALPACA_PAPER is false and SWING_ALLOW_LIVE != 'yes'; see docs/gates.md` | you flipped to live keys | put `ALPACA_PAPER=true` back; live requires the gates in section 6 and the explicit env override |
| `kill switch tripped (…/state/KILL); remove the file to resume` | `state/KILL` exists | intended; `rm state/KILL` only after the incident is understood (docs/OPERATIONS.md) |
| nightly `execute` shows `killed: entries {'refused': N}` | `state/KILL` exists | intended: the autopilot sends no entries, closes or stop changes, only cancels of resting unfilled entries; your Alpaca bracket legs still protect open positions |
| `nightly` exits 1 with `broker 'alpaca' unavailable; positions/execute were skipped` | Alpaca keys missing/invalid or the API is down | `swing doctor --live`; the data steps already ran, so `swing autopilot` later is enough; `--no-execute` to run data only |
| `execute` detail `N entries held (review step failed)` or `N unreviewed entries held` | the Claude review crashed (key, rate limit, outage), or more intents than `agent.max_candidates_per_day` reviews | fail-closed by design; fix the cause, `swing review --as-of <date>`, then `swing autopilot --as-of <date>` |
| `execute` shows `capped` | `execution.max_new_orders_per_day` already used for that date (counted across runs from the audit file) | intended; raise the cap in `settings.yaml` only on purpose |
| `execute` shows `duplicate` | that `client_order_id` is already in `state/orders.sqlite` (a re-run) | intended: re-runs never send twice |
| live account: nothing submitted, `data/runs/pending/<date>.json` written | `ALPACA_PAPER=false` without both `execution.auto_submit_live: true` and `SWING_ALLOW_LIVE=yes` | intended; `swing paper --approve` reads `data/runs/intents/`, not the pending file |
| `swing ingest --mode grouped`: `drop the symbol list` | grouped mode ingests the whole market | drop `--symbols`, or use `--mode per-symbol` |
| grouped ingest stops with `plan_limit_at <date>` | Basic serves 2 years | intended; `--full` retries it after a plan upgrade |
| Telegram rating buttons spin and nothing is recorded | the monitor is not running (it processes presses), it runs with `--dry-run`, or a webhook is set on the bot (`getUpdates` 409) | start `swing monitor run`; `deleteWebhook`; or rate with `swing monitor rate <event_id> <rating>` |
| `swing monitor rate` exits 5 `not rated: <id> (unknown_event)` | the id is not in `data/events.sqlite` (typo, or another machine's monitor) | copy the id from the alert's last line or from `swing monitor report` |
| `refusing to submit orders: a human must approve with --approve` | no `--approve NAME` | add it; it is logged with every order |
| `no saved signals for <date>; run swing scan --as-of <date> first` | `scan` saved under the last trading day, `size` defaulted to today | pass the same `--as-of` to both, or run `nightly` |
| `account equity unknown: pass --equity, set risk.account_equity_override, or --broker` (or `nightly` shows `size skip`) | sizing without a broker or equity | `swing size --broker alpaca` (reads paper equity), `--equity 100000`, or set `execution.broker: alpaca` (shipped) so the nightly reads the paper account; `risk.account_equity_override` only without a broker |
| `store data/swing.duckdb does not exist; run swing ingest first` | no ingest yet | section 2.3 |
| DuckDB `Could not set lock on file` / `IO Error` | two processes writing the store (nightly + manual ingest) | DuckDB is single-writer: wait for the nightly to finish; the monitor only reads at start-up |
| `lightgbm` import error (`libomp.dylib not found`) | macOS without OpenMP | harmless: ranker uses scikit-learn; `brew install libomp` to enable LightGBM |
| Telegram `getUpdates` returns `"result": []` | you have not messaged the bot, or a webhook is set | send `/start` to the bot; `deleteWebhook` |
| Telegram `400 chat not found` | wrong `TELEGRAM_CHAT_ID` (group ids are negative) | re-read the id from `getUpdates` |
| Pushover keeps buzzing | P3 uses emergency priority by design | acknowledge in the app; if it was noise, rate it so the rule gets demoted |
| Nothing arrives 22:00-06:00 ET | quiet hours (`monitor.quiet_hours_et: [22, 6]`) | P3 still goes through; change the window in `settings.yaml` |

## 5. What it costs

| Phase | Monthly | What is in it |
|---|---|---|
| Paper (now) | **$10-20** | Massive Basic $0; Alpaca paper + Basic data $0; Telegram $0; Haiku classifier $3-10 (bulk at $1/$5 per MTok, cache reads $0.10); Sonnet review ~$1-3 ($2/$10 per MTok, ~20 candidates/day); Pushover $4.99 once; optional VPS $6 |
| Paper with a full universe | +$29 | Massive Starter: unlimited calls, 5 years, flat files; needed above ~100 names |
| Live (after the gates) | **$160-200** | + Alpaca Algo Trader Plus $99 (SIP, unlimited symbols, pre-market); + Finviz Elite $39.50 (gapper/RVOL CSV) |
| Full | **$250-300** | + sec-api.io $49 (filing stream); + X pay-per-use credits ($20-50 cap) |

Claude usage is metered: Opus for the weekly strategy lab is $4/$20 per MTok, so a lab run is cents to a
dollar. Alpha Vantage, EDGAR, Nasdaq/FINRA nightly files, healthchecks.io (20 checks) are free.

## 6. Gates before any live capital (docs/gates.md)

1. **Paper phase**: at least 3 months of forward paper trading and at least 100 closed trades with modeled costs
   (10 bps/side large caps, 20 bps otherwise, plus SEC $20.60 per $1M sold and FINRA TAF $0.000195/share).
2. **Significance**: the strategy shows deflated-Sharpe significance with the full trial count logged
   (`swing trials`, `research/trials.py`).
3. **Monitor validation**: a two-week paper run logging per-source latency, alerts per rule, duplicate rate and
   your useful/noise ratings; rules that never produce an acted-on P2+ are pruned.
4. **Kill criterion written down** before go-live: max drawdown or rolling-Sharpe floor that stops trading.
5. **Taxes**: decide the Section 475(f) mark-to-market election by the prior-year filing deadline; log wash
   sales.

Only when all five hold: live keys in `.env` by you (never from a Claude session), `ALPACA_PAPER=false`,
`SWING_ALLOW_LIVE=yes` in the shell that runs `swing paper`, and a re-read of `docs/OPERATIONS.md`. The
nightly autopilot stays off for live money unless you also set `execution.auto_submit_live: true` and give the
scheduled job `SWING_ALLOW_LIVE=yes`; without both it stages the plan to `data/runs/pending/<date>.json`.

## Appendix A: checking each key by hand

```bash
set -a; . ./.env; set +a      # export .env into this shell only; run in a throwaway terminal
curl -s "https://api.massive.com/v3/reference/tickers?limit=1" -H "Authorization: Bearer $MASSIVE_API_KEY" | head -c 300
curl -s https://paper-api.alpaca.markets/v2/account -H "APCA-API-KEY-ID: $ALPACA_API_KEY" -H "APCA-API-SECRET-KEY: $ALPACA_SECRET_KEY"
curl -s "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe"
curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" -d chat_id="$TELEGRAM_CHAT_ID" -d text=ping
curl -s https://api.anthropic.com/v1/models -H "x-api-key: $ANTHROPIC_API_KEY" -H "anthropic-version: 2023-06-01" | head -c 300
curl -s "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&count=1&output=atom" -A "$EDGAR_USER_AGENT" | head -c 300
curl -s -X POST https://api.pushover.net/1/messages.json -d token="$PUSHOVER_APP_TOKEN" -d user="$PUSHOVER_USER_KEY" -d message=ping
```

## Appendix B: where things live

- Secrets: `.env` (0600, gitignored). Non-secret config: `config/settings.yaml`.
- Data: `data/swing.duckdb` (bars, panel, reference, `ingest_grouped_days`), `data/events.sqlite` (monitor
  event log, alerts, `alert_ratings`), `data/trials.jsonl`, `data/ranker.pkl`,
  `data/runs/{signals,reviews,intents,fills,exits,autopilot,pending,nightly,cycle}/<date>.json`,
  `data/journal/<date>.md`, `data/raw/massive/` (reference-list cache), `data/logs/`.
- State: `state/KILL` (kill switch), `state/orders.sqlite` (order manager), `state/limits.json` (peak equity).
- Services: `deploy/launchd` (Mac), `deploy/systemd` (VPS), `scripts/*.sh`.
