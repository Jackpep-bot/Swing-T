# Operations (paper phase)

How to run the engine day to day once `docs/SETUP.md` is done. Everything here assumes paper keys
(`ALPACA_PAPER=true`); the live checklist is the gate list in `docs/gates.md`, not this file.

## 1. Daily routine (weekdays, ~20 minutes of your attention)

| When (ET) | What runs | What you do |
|---|---|---|
| 06:30 | `swing nightly` (launchd/systemd): ingest -> features -> scan -> rank -> size -> review -> shadow -> positions -> execute -> journal; report in `data/runs/nightly/<date>.json`. The scan runs only the strategies the market regime allows (section 1.2). On paper the execute step is the autopilot (section 1.1): it manages open positions and submits up to 5 new bracket orders | nothing; check `data/logs/nightly.err.log` only if the healthchecks.io ping is missing or the report shows a `fail` step |
| 08:30 | P1 digest to Telegram | read it with `data/journal/<today>.md` (its "Market regime" section says which strategies were allowed and at what size) and `data/runs/autopilot/<today>.json`: candidates, reviews, what was submitted / vetoed / capped, exits, open positions |
| 09:00-09:25 | - | check the Alpaca paper dashboard against the audit. Disagree with an entry? Cancel it in the dashboard (the ledger reconciles on the next run; it will not be re-sent for that date). Never edit numbers in the run files. With execution off (`execution.nightly_execute: false`) this is where you run `uv run swing paper --broker alpaca --approve "<your name>"` |
| 09:30-10:30 | monitor: P2 (watchlist halts, insider clusters, 52w breaks, gap+RVOL+news) and P3 (anything on a held position) | act on P3 immediately (halt, SSR, severe 8-K, >= 5% adverse move, order rejection); glance at P2; tap Useful / Noise / Traded on both (section 4) |
| 10:30-15:30 | monitor | nothing unless P3. Long alerts from the small-cap track are never emitted after 10:30 by design |
| 15:45 | P1 digest | positions vs stops, what the ranker likes for tomorrow |
| 16:05-18:30 | nightly files (SSR, Reg SHO, FINRA short volume) land; 18:30 P1 digest | read after-hours filings on held names (424B5s post ~16:05) |
| any time | `uv run swing status` | kill switch state, store counts, keys present |

Rules of the loop: numbers come from `scan`/`size`; reviews and alerts only change whether you act, never the
price, stop, target or size. If you want a different size, change `risk.*` in `config/settings.yaml` and re-run
`swing size`, so the change is versioned.

### 1.1 The paper autopilot

As shipped (`execution.broker: alpaca`, `execution.nightly_execute: true`, `execution.auto_submit_paper: true`,
`ALPACA_PAPER=true` in `.env`) the paper account trades by itself; every order is approved as `autopilot:paper`
and logged in `state/orders.sqlite` and `data/runs/autopilot/<date>.json`.

- **Paper only.** Automatic approval happens only on a paper broker (Alpaca with `ALPACA_PAPER=true`, or the
  local `paper_sim`). A live account needs **both** `execution.auto_submit_live: true` **and**
  `SWING_ALLOW_LIVE=yes` in the environment of the scheduled job (not `.env`); with either missing the
  autopilot stages its plan to `data/runs/pending/<date>.json` and sends nothing. Leave both off until every
  gate in `docs/gates.md` passes.
- **Order of work each run:** kill switch check -> reconcile ledger with the broker -> exits (cancel entries
  unfilled after `cancel_unfilled_entries_after_sessions`, stop to breakeven at `breakeven_after_r`, trail from
  `trail_after_r`, flatten before earnings once an `earnings` table is ingested) -> entries (GTC brackets, at
  most `max_new_orders_per_day` per date across all runs, idempotent on `client_order_id`).
- **Claude's review gates entries:** `reject` / `needs_more_info` vetoes an entry. If the review step fails, or
  a signal was not among the reviewed candidates, the entry is held (`require_review_approval: true`). Without
  an `ANTHROPIC_API_KEY` the review is skipped and entries go through on code alone.
- **Stopping it:** `touch state/KILL` stops autopilot entries, closes and stop changes at the next run; the
  only thing it still does is cancel every resting unfilled `swing-*` entry (a GTC entry would otherwise keep
  working for up to 90 days). Bracket legs already at Alpaca keep protecting positions. `execution.nightly_execute: false` (or
  `SWING_NIGHTLY_ARGS=--no-execute`) turns it into plan-only and you go back to `swing paper --approve`.
- **Re-running:** `uv run swing autopilot [--dry-run]` re-plans from the latest saved signals and reviews
  (e.g. after clearing a kill switch or a failed execute step). Re-runs never double-submit: already-sent
  intents show as `duplicate`, the daily cap counts submitted and errored entries from the audit file plus
  anything the ledger shows an autopilot already sent; an overlapping run aborts on `state/autopilot.lock`.
  A run whose review crashed (`runs/review_status/<date>.json` = `fail`/`running`) has its entries held by
  `swing autopilot` too. A live account's staged plan (`runs/pending/<date>.json`) is executed exactly with
  `swing paper --approve NAME --as-of <date>`.

### 1.2 Market regime and the playbook router

Every school gates setups behind the market (docs/methods.md sections 0 and 2a: gate first, then select, then
trigger). The nightly does it in three places:

- **features** builds the panel only for the names that pass the universe screen at the run date
  (`universe.*`: price, average volume, dollar volume, common stock, not OTC; split-adjusted history is
  un-adjusted first so a later reverse split cannot sneak a penny stock in). With the whole market in the store
  (~12,000 tickers from grouped ingest) that is about `universe.max_symbols` names, plus SPY, QQQ and IWM and
  anything you hold or have an open order on (so exits always have data). The step detail shows the counts.
  It also computes market breadth over the screened names (% above the 50/200-day, Stockbee 4% up/down counts
  and their 10-day ratio, new highs/lows) into the store table `breadth`, one row per session.
- **scan** classifies the day (`strategies.playbook.market_state`): SPY trend (vs its 50/200-day and the
  50-day slope), volatility (SPY's 21-day vol percentile) and breadth -> one of `healthy_uptrend`,
  `narrow_uptrend`, `choppy`, `correction`, `high_vol_selloff`. The table in `settings.playbook.regimes` then
  says which strategies may open new trades and at what fraction of `risk.risk_per_trade_pct`. As shipped:
  breakouts only in `healthy_uptrend`; pullbacks in healthy (full size) and narrow (half size) uptrends; RSI-2
  in uptrends and chop, and at a quarter size in a high-vol selloff; nothing new in a `correction`. The
  decision is saved to `data/runs/regime/<date>.json`, shown at the end of the nightly output, and written
  into the journal.
- **size** multiplies `risk_per_trade_pct` by the strategy's multiplier (never above 1). `swing autopilot`
  re-applies the multipliers saved with the signals it sizes.

`uv run swing regime --as-of <date>` prints the same state and the allowed / blocked strategies with the risk
each would get, without running anything. A day with zero signals in a `correction` is the router working,
not a failure. The router is a veto layer, so it fails closed: if the playbook raises (at import or when
called) or is missing, the scan step fails, an empty signal list is saved for the day and no new entries are
sized (exits still run). `swing autopilot` likewise refuses to size saved signals that have no saved routing
(`runs/regime/<day>.json` with an `allowed` table). `playbook.enabled: false` turns routing off (every enabled
strategy at 1.0). Change the
table only on replay evidence (section 2), never because a week felt wrong.

### 1.3 Shadow ledger

The `shadow` step (after `review`) writes every signal of the day into the store table `shadow_signals`, the
ones the engine took (sized and not vetoed) and the ones it passed on, with the regime. A strategy set to
`{enabled: false, shadow_only: true}` in `settings.yaml` (the methods.md 7b P1 modules, until `docs/gates.md` is
met) is scanned every night in every regime and recorded here, but never sized, reviewed or executed. Rows are
dated by the session of the bars the signal was computed from (the 06:30 ET run records the previous close),
so grading starts at the session the autopilot enters on. Each night it grades
the signals whose 5/10/20-session horizons have matured on daily bars: entry at the next open (skipped if it
gapped through the stop), stop-first when a bar touches both stop and target, else exit at the horizon close;
result, MFE and MAE in R. `uv run swing shadow report [--since DATE] [--by strategy,regime] [--horizon 10]
[--taken|--untaken]` prints win rate, average R, expectancy and profit factor per group. It is the evidence for
"does this setup work in this regime", for setups you did not trade as much as for those you did.

## 2. Weekly routine (Saturday, ~45 minutes)

1. `uv run swing monitor report --days 7` and read it with section 3.
2. `uv run swing monitor outcomes --days 30`: realized returns after each alert (+5 min, +30 min, close, +1 d,
   +5 d, +20 d) joined to classifier, grade and scores. This is the evidence for gate 3 and for the small-cap
   track's warn/fade posture; a rule whose alerts are followed by nothing is noise even if it "felt right".
3. `uv run swing trials --last 20`: every backtest you ran is a trial; the deflated Sharpe in the next backtest
   is judged against that count. Do not delete `data/trials.jsonl` to "reset" it.
4. `uv run swing shadow report --since <4 weeks ago>` (and `--by regime`): expectancy per strategy and regime
   from the shadow ledger (section 1.3). Before changing `playbook.regimes`, run
   `uv run swing replay --start <date> --end <date>` and the same with `--no-router`: the replay walks every
   session with only the data available that day, routes, sizes, fills at the next open (marketable-limit
   rule), applies the exit rules and costs, prints summary / by-strategy / by-regime tables, saves
   `data/runs/replay/<start>_<end>.json` and logs a trial. Its signals are graded into a separate table
   (`swing shadow report --replay`), never the live ledger. It opens the DuckDB store for writing, so run it
   when the nightly and ingest are not running. Judge the router by drawdown reduction, not CAGR
   (docs/methods.md 7a).
5. Sizing input: with `execution.broker: alpaca` (shipped) the nightly reads equity from the paper account, so
   there is nothing to copy. Only if you run without a broker, copy the paper equity into
   `risk.account_equity_override` and commit the change.
6. `scripts/backup-data.sh` (section 7). Check `du -sh data` and that `data/backups` is pruning.
7. Rotate logs if `data/logs/*.log` is over ~100 MB (launchd/systemd append forever): stop the agent, move the
   file aside, start it (`deploy/README.md`).
8. Reconcile: every autopilot run reconciles the ledger with the broker (`reconcile` in the audit file lists
   unresolved orders and unknown positions). Compare the week's `data/runs/autopilot/*.json` with the Alpaca
   paper dashboard; `uv run swing paper --broker alpaca --approve "<you>" --reconcile` also pulls fills.
9. Paper-gate ledger: closed trades so far, months elapsed, strategies with deflated-Sharpe evidence.
   Keep it at the top of `data/journal/README.md` (or wherever you keep notes) so the gate decision is not
   made from memory.
10. Optional, with Claude Code: the `tune-monitor` skill proposes threshold changes from the report and a replay;
   the `research-loop` skill runs the strategy lab on one hypothesis. Both produce diffs you review.

## 3. Reading `swing monitor report`

`uv run swing monitor report --days 7` prints one mapping; here is what each key means and what healthy looks
like for a 30-name watchlist on paper.

| Key | Meaning | Healthy | Act when |
|---|---|---|---|
| `events` | raw events after dedup | hundreds to a few thousand per week (news ~600-900/day before matching) | 0 on a trading day = a feed never connected |
| `by_source` | events per feed (`alpaca_news`, `edgar`, `nasdaq_halts`, `alpaca_stocks`, `alpaca_account`) | every configured feed non-zero on trading days | a source at 0 while others move = auth or subscription problem (`405`/`409` in `monitor.err.log`) |
| `by_kind` | news / filing / halt / bar / account | filings and halts non-zero most days | all `news` = EDGAR or halts feed dead |
| `by_priority` | P0 (log only) .. P3 | P3 rare (held names only); P2 single digits/day; P1 digests | daily P2 > 20 = `hourly_alert_cap` is doing the filtering for you: raise `rvol_gate` or trim rules |
| `top_rules` | which stage-1 rules fire | spread across rules | one rule dominating = that rule's threshold; `watchlist_hit` dominating = watchlist too broad |
| `top_symbols` | which names fire | no single name > ~20% of events | one name dominating = an alias/matcher false positive (word-like ticker) |
| `alerts` / `alerts_delivered` | alerts the policy produced / actually sent | delivered close to alerts outside quiet hours | gap = cooldown/caps/quiet hours; a large gap during market hours = a deliverer failing (Telegram 4xx) |
| `alert_channels` | per channel (`telegram`, `pushover`, `console`) | pushover only for P3 | pushover count > P3 count = routing misconfigured |
| `notable` | the highest-priority recent events with their rule hits | you remember seeing these | you did not = delivery or phone-side problem |
| `duplicate rate` (when present) | share of events dropped by dedup | 20-40% for news is normal | > 60% = a feed replaying; < 5% with Benzinga = dedup not seeing the provider id |
| per-source `latency` (when present) | receipt time minus source time | news/halts seconds; EDGAR 15-60 s (poll interval) | minutes = clock drift (`chrony`/time sync) or a stalled feed |

Also look at `data/logs/monitor.err.log` for `stale_feed` (watchdog), `reconnect`, `429` (Haiku rate limit:
the classifier falls back to rules-only priorities) and `delivery_failed`.

## 4. Rating alerts

The gate needs a useful/noise ratio per rule and the tuning skill needs it per rule and per source. Every P2
and P3 alert on Telegram has three buttons:

| Button | Means |
|---|---|
| **Useful** | right to know, no action |
| **Noise** | should not have been sent (wrong name, stale, an offering dressed as news, too late to matter) |
| **Traded** | you did something because of it (entered, exited, moved a stop) |

- A press is recorded by the running monitor (`swing monitor run` long-polls the bot): the rating goes into the
  event's `meta` (`rating`, `rating_source`, `rated_at`) in `data/events.sqlite`, and every press is appended
  to the `alert_ratings` table, so a changed mind is a new row and the latest press wins. The button spinner
  stops when the press is saved. Presses are processed only while the monitor runs and not under `--dry-run`;
  only the configured `TELEGRAM_CHAT_ID` (and, in a private chat, only you) can rate.
- From a terminal, or for an alert you saw elsewhere: `uv run swing monitor rate <event_id> useful|noise|traded`.
  The id is in `swing monitor report` (each `notable` entry shows `event_id` and any `rating`). Exit 5 means
  the id is not in the event log.
- Rate P3 and P2 the same day; P1 digests have no buttons and are not rated.
- Weekly, `uv run swing monitor outcomes --days 30` joins ratings to forward returns: per rule `rated`,
  `useful` (Useful + Traded), `traded` and `precision_proxy` = useful / rated. A rule with zero `traded` P2+ in
  14 days is demoted to P1 (digest) by editing its priority constant; a rule above ~50% noise gets its
  threshold raised in `config/settings.yaml` and checked with `swing monitor replay --days 14 --rules <name>`
  before and after.

If you kept the old `data/alert_ratings.csv`, re-enter its rows with `swing monitor rate` (`acted` -> `traded`,
`useful` -> `useful`, `noise` and `late` -> `noise`) and archive the file.

## 5. When to recalibrate

Recalibrate thresholds only on evidence, and only one knob at a time:

- **After the first two weeks** of paper monitoring (gate 3): run `swing monitor report --days 14`, apply the
  rating rules above, prune rules that never produced a `traded` P2+.
- **When the hourly cap bites**: `alerts` much larger than `alerts_delivered` during market hours means
  `hourly_alert_cap: 20` is choosing for you. Raise `rvol_gate` (2.0 -> 2.5) or `gap_pct_alert` (8 -> 10) rather
  than the cap.
- **When a source changes**: Alpaca plan upgrade (pre-market appears: the small-cap `rvol_min` and
  `premarket_volume_min` suddenly see real volume), a new feed, or a watchlist that doubled. Re-run the
  replay over the last 7 days before trusting the new counts.
- **Small-cap track**: it is warn/fade by posture. Only raise `bagholder_alert_threshold` (6) after at least 20
  rated bag-holder alerts; never lower `never_long_after_et`.
- **Strategies**: do not change `strategies.*` params from live observations. Change them in a backtest, log
  the trial, compare deflated Sharpe, then edit `settings.yaml`. The walk-forward and trial log exist so that
  "it felt noisy this week" does not become a parameter.
- **Sizing**: `risk_per_trade_pct` stays at 1.0 on paper. Changing it mid-run makes the 100-trade gate sample
  heterogeneous; if you must, note the date in the journal.

Every change: commit `config/settings.yaml` with the before/after alert counts from the replay in the message.

## 6. Kill-switch procedure

`state/KILL` blocks every order path (`swing paper`, the order manager, and the autopilot in `swing nightly` /
`swing autopilot`, which then refuses entries, closes and stop changes and reports `killed`). The one action
it still takes is cancelling resting unfilled `swing-*` entries, which only removes exposure. It does not stop
the monitor or the nightly job; data keeps flowing. Stop and target legs already resting at Alpaca stay active.

**Trip it** (any of: you do not understand a fill, the account equity is not what the journal says, a feed is
dead during market hours and you hold positions, a deploy is in progress, you are travelling):

```bash
touch state/KILL          # or scripts/dev.sh kill
uv run swing status       # shows "kill switch TRIPPED"
```

Then, by hand in the Alpaca paper dashboard: check open orders and positions; cancel or close what you need.
`swing paper` cannot help you here by design.

**Clear it** only after the cause is written in the journal (`data/journal/<date>.md`, a "Incident" heading):

```bash
rm state/KILL             # or scripts/dev.sh unkill
uv run swing autopilot --dry-run   # reconcile + see what the autopilot would do now; drop --dry-run to act
```

The monitor sends a P3 when it sees the switch trip; it does not send one when it clears.

Related stops that are not the kill switch: `max_daily_loss_pct` (3%) and `max_drawdown_pct` (15%) in
`risk.*` refuse new orders through `LimitState`; the peak equity they compare against is in
`state/limits.json`. Do not edit that file to "unstick" a drawdown halt.

## 7. Backups

What matters, in order: `data/events.sqlite` (the only record of alerts and ratings, incl. `alert_ratings`, for gate 3),
`data/trials.jsonl` (the trial count for gate 2), `state/orders.sqlite` + `state/limits.json` (order
idempotency and the drawdown peak), `data/journal/` and `data/runs/`, then `data/swing.duckdb` (bars can be
re-ingested, but the point-in-time panel and reference snapshots are hours of API budget on Basic).

```bash
scripts/backup-data.sh                  # -> data/backups/<UTC stamp>/, keeps the newest 14
scripts/backup-data.sh ~/Backups/swing --keep 30
```

- SQLite files are copied with the online backup API, safe while the monitor writes (WAL mode).
- DuckDB is single-writer and has no online backup from the shell: the script copies the file and skips it if
  another process has it open. Run backups when the nightly is not running (anything after 07:30 ET is fine).
- Restore: stop the services, copy the files back to `data/` and `state/`, `uv run swing status`, start.
- Off-machine copy: point the destination at a synced folder, or `rsync -a data/backups/ host:swing-backups/`
  from the weekly routine. Keep `.env` out of backups; it is a secret, not data.
- Mac Time Machine: exclude `data/swing.duckdb` only if the hourly snapshots are a problem; the rest is small.

## 8. Incident playbook

| Symptom | First check | Then |
|---|---|---|
| no alerts all morning | `launchctl print gui/$UID/com.swing.monitor` / `systemctl --user status swing-monitor`; `tail data/logs/monitor.err.log` | if `stale_feed`: Alpaca status page, your network; the supervisor reconnects on its own. If the process is dead: KeepAlive/Restart brought it back? Look at the last traceback |
| healthchecks.io says the nightly is late | `tail -50 data/logs/nightly.err.log` | Massive 429 (budget), EDGAR 403, DuckDB lock (a manual ingest overlapped) |
| Telegram silent, console shows alerts | `curl .../getMe` and a manual `sendMessage` | token revoked or chat id changed (new group id after a group-to-supergroup upgrade) |
| Pushover alarm will not stop | acknowledge in the app | if the alert was wrong, rate it `noise` and look at the rule the same day |
| Telegram rating buttons spin forever | is the monitor running (not `--dry-run`)? `tail data/logs/monitor.err.log` for `telegram_updates` errors | a webhook on the bot blocks `getUpdates` (409): `deleteWebhook`; meanwhile `swing monitor rate <event_id> <rating>` |
| the autopilot submitted something you did not expect | `data/runs/autopilot/<date>.json` (outcome and review decision per entry) | cancel/close in the Alpaca dashboard; `touch state/KILL` if you do not understand why; journal it before clearing |
| nightly `scan` shows 0 signals, `regime correction: allowed none` | `uv run swing regime --as-of <date>` | expected: no new longs in a correction; exits still run. Nothing to fix |
| nightly `scan` fails with a playbook / `market_state` error | `scan` detail in `data/runs/nightly/<date>.json`; is SPY in the store (`swing status`)? | the router fails closed (no new entries). Ingest SPY or fix the module, then `swing nightly --as-of <date>` |
| nightly `execute` shows `entries held (review step failed)` | `review` step detail in `data/runs/nightly/<date>.json` | fix the key/outage, `swing review --as-of <date>`, then `swing autopilot --as-of <date>` |
| equity in the digest differs from the dashboard | `swing paper ... --reconcile` | a fill the engine did not see (account websocket down) |
| disk nearly full | `du -sh data/* data/logs/*` | rotate logs, prune `data/backups`, `data/raw/` (provider JSON cache) can be deleted |
| clock drift warning | `sntp -sS time.apple.com` (Mac, needs sudo) / `chronyc tracking` (VPS) | latency numbers in the report are meaningless until fixed |
| you changed `.env` | restart the monitor (it reads `.env` at start) | `scripts/install-launchd.sh --monitor` re-bootstraps it; `systemctl --user restart swing-monitor` |
