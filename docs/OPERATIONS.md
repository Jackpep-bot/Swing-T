# Operations (paper phase)

How to run the engine day to day once `docs/SETUP.md` is done. Everything here assumes paper keys
(`ALPACA_PAPER=true`); the live checklist is the gate list in `docs/gates.md`, not this file.

## 1. Daily routine (weekdays, ~20 minutes of your attention)

| When (ET) | What runs | What you do |
|---|---|---|
| 06:30 | `swing nightly` (launchd/systemd): ingest -> features -> scan -> rank -> size -> review -> journal; report in `data/runs/nightly/<date>.json` | nothing; check `data/logs/nightly.err.log` only if the healthchecks.io ping is missing or the report shows a `fail` step |
| 08:30 | P1 digest to Telegram | read it with `data/journal/<today>.md`: candidates, reviews, intents, open positions |
| 09:00-09:25 | - | decide. `uv run swing paper --broker alpaca --approve "<your name>"` submits the saved intents as bracket orders. Skip a name by deleting it from `data/runs/intents/<date>.json` before submitting, never by editing numbers |
| 09:30-10:30 | monitor: P2 (watchlist halts, insider clusters, 52w breaks, gap+RVOL+news) and P3 (anything on a held position) | act on P3 immediately (halt, SSR, severe 8-K, >= 5% adverse move, order rejection); glance at P2; rate both (section 3) |
| 10:30-15:30 | monitor | nothing unless P3. Long alerts from the small-cap track are never emitted after 10:30 by design |
| 15:45 | P1 digest | positions vs stops, what the ranker likes for tomorrow |
| 16:05-18:30 | nightly files (SSR, Reg SHO, FINRA short volume) land; 18:30 P1 digest | read after-hours filings on held names (424B5s post ~16:05) |
| any time | `uv run swing status` | kill switch state, store counts, keys present |

Rules of the loop: numbers come from `scan`/`size`; reviews and alerts only change whether you act, never the
price, stop, target or size. If you want a different size, change `risk.*` in `config/settings.yaml` and re-run
`swing size`, so the change is versioned.

## 2. Weekly routine (Saturday, ~45 minutes)

1. `uv run swing monitor report --days 7` and read it with section 3.
2. `uv run swing monitor outcomes --days 30`: realized returns after each alert (+5 min, +30 min, close, +1 d,
   +5 d, +20 d) joined to classifier, grade and scores. This is the evidence for gate 3 and for the small-cap
   track's warn/fade posture; a rule whose alerts are followed by nothing is noise even if it "felt right".
3. `uv run swing trials --last 20`: every backtest you ran is a trial; the deflated Sharpe in the next backtest
   is judged against that count. Do not delete `data/trials.jsonl` to "reset" it.
4. Sizing input: copy the paper account's equity from the Alpaca dashboard into
   `risk.account_equity_override` so the scheduled `nightly` sizes against this week's equity (it does not read
   the broker; `swing size --broker alpaca` does). Commit the change.
5. `scripts/backup-data.sh` (section 7). Check `du -sh data` and that `data/backups` is pruning.
6. Rotate logs if `data/logs/*.log` is over ~100 MB (launchd/systemd append forever): stop the agent, move the
   file aside, start it (`deploy/README.md`).
7. Reconcile: `uv run swing paper --broker alpaca --approve "<you>" --reconcile` on a day with no new intents
   is a no-op submit plus a fills reconcile; compare with the Alpaca paper dashboard.
8. Paper-gate ledger: closed trades so far, months elapsed, strategies with deflated-Sharpe evidence.
   Keep it at the top of `data/journal/README.md` (or wherever you keep notes) so the gate decision is not
   made from memory.
9. Optional, with Claude Code: the `tune-monitor` skill proposes threshold changes from the report and a replay;
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

The gate needs a useful/noise ratio per rule and the tuning skill needs it per rule and per source. There is no
rating command in the CLI yet, so keep a flat file the report and replay can join on `event_id`:

`data/alert_ratings.csv` (create it once with the header):

```
ts,event_id,rule,symbol,rating,note
2026-10-07T13:41:02Z,8d3f...,halts_luld,ABCD,acted,"T1 on held name, sold at reopen"
2026-10-07T14:05:11Z,2a71...,rvol_gate_triggers,WXYZ,noise,"gap was an offering"
```

- `rating` is one of `acted` (you did something because of it), `useful` (right to know, no action),
  `noise` (should not have been sent), `late` (right but too slow to matter).
- The `event_id`, rule and symbol are in the alert text and in `notable`; the Telegram message carries the id
  in its last line.
- Rate P3 and P2 the same day; do not rate P1 digests, they are not alerts.
- Weekly, count `acted`+`useful` vs `noise` per rule. A rule with zero `acted` P2+ in 14 days is demoted to P1
  (digest) by editing its priority constant; a rule above ~50% `noise` gets its threshold raised in
  `config/settings.yaml` and checked with `swing monitor replay --days 14 --rules <name>` before and after.

When a rating CLI lands (`swing monitor rate <event_id> <rating>`), migrate this file; keep the same columns.

## 5. When to recalibrate

Recalibrate thresholds only on evidence, and only one knob at a time:

- **After the first two weeks** of paper monitoring (gate 3): run `swing monitor report --days 14`, apply the
  rating rules above, prune rules that never produced an acted-on P2+.
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

`state/KILL` blocks every order path (`swing paper`, the order manager, any future automation). It does not
stop the monitor or the nightly job; data keeps flowing.

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
uv run swing paper --broker alpaca --approve "<you>" --reconcile   # reconcile before new intents
```

The monitor sends a P3 when it sees the switch trip; it does not send one when it clears.

Related stops that are not the kill switch: `max_daily_loss_pct` (3%) and `max_drawdown_pct` (15%) in
`risk.*` refuse new orders through `LimitState`; the peak equity they compare against is in
`state/limits.json`. Do not edit that file to "unstick" a drawdown halt.

## 7. Backups

What matters, in order: `data/events.sqlite` (the only record of alerts and ratings for gate 3),
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
| equity in the digest differs from the dashboard | `swing paper ... --reconcile` | a fill the engine did not see (account websocket down) |
| disk nearly full | `du -sh data/* data/logs/*` | rotate logs, prune `data/backups`, `data/raw/` (provider JSON cache) can be deleted |
| clock drift warning | `sntp -sS time.apple.com` (Mac, needs sudo) / `chronyc tracking` (VPS) | latency numbers in the report are meaningless until fixed |
| you changed `.env` | restart the monitor (it reads `.env` at start) | `scripts/install-launchd.sh --monitor` re-bootstraps it; `systemctl --user restart swing-monitor` |
