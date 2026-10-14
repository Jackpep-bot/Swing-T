# Project status: BATCH 5 RUNNING, BATCH 6 QUEUED BEHIND IT; small-cap map done, no candidates (2026-10-13 20:00 ET)

Branch `claude/project-thread-fesglg` (PR https://github.com/Jackpep-bot/Swing-T/pull/3) continues from
`claude/project-thread-4wq9xa` (PR 2, still open, ends at 62455ed).

## Small-cap map: DONE 2026-10-13 18:55 ET, nothing found (docs/edge_map_smallcap.md)
Run 20261013-155159, every strategy on the 2,500 stocks after the 1,500 most liquid, 2024-26, 10/10 chunks.
**0 of 870 cells** are positive against SPY in both halves, at t >= 2 or even at t >= 1 (luck alone would give about
22 at t >= 1). Pooled, every liquidity band loses in both halves: net R -0.10 to -0.26, -0.17 to -0.39 against SPY.
Small caps do not rescue these methods; they are worse there than on the liquid 1,500. 2,955 trials logged (9,707 in
all). So there is no probation candidate, no reason to widen the nightly's universe, and nothing for the
`event_avoid_filters` card to be applied to. The lane stores data/live/research_20261013-155159_l0..l3.duckdb
(4 copies of the store) hold the ledgers; delete them with the other old copies when the owner says so.

## Running
Owner 19:23 ET: "push all tasks forward and increase a thread of research into new swing strategies constantly
scraping and comparing data internally". The coordinator runs a cloud research thread (daily routine) that cards new
strategies; each batch arrives as branch `claude/batchN-cards`. For each: merge the cards, code them (add-strategy
skill; a card that is not a stock strategy gets a research module, as research/vrp_overlay.py), commit a
pre-registration BEFORE any run, harness-check signal counts, then queue
`scripts/run_prereg_batch.sh <tag> <date> <slugs>` behind whatever is running (see its header).
While a replay batch runs, anything new under swing_engine/strategies/ must import cleanly from the first save:
every replay that starts imports the whole package (develop a module as `_wip_<slug>.py`, rename when its tests pass).

`scripts/on_power.sh scripts/run_batch5.sh` (PID 72028, log data/logs/research/batch5.log). Started 18:56 ET at 3
replays at a time; restarted 19:25 ET at 7 at a time (`--job-gb 2024=6`: a replay held 3.4 GB) without losing the
three that were running. The script now skips any replay that is finished or still running (`todo`), so starting
it again is safe. It replays the 15 batch-5 cards on 2024-26 (logs data/logs/research/pr_prereg-b5-*.log, empty
until a replay ends), then 2017-24 (one at a time, 30 GB budget, not measured yet: raise it once the first one
shows its real size) for the cards that meet the rule in 2024-26 plus the three once-a-year cards, grades
(docs/preregistration/2026-10-13-batch5-results.md, `-iwm.md`), refreshes docs/income_view.md and Telegrams the
verdicts. Pre-registered: docs/preregistration/2026-10-13-batch5.md (commit 1991e13).
Do not run `swing ingest` on the live store while batch 5 runs: every replay starts by copying it.
`scripts/on_power.sh` (owner: "start them I will plug in soon") starts a job on AC or on a battery at or above 25%
(`BATT_FLOOR`), pauses it in place (SIGSTOP, Telegram notice) under that, and continues it on AC.
If it is gone after a restart, start it again with nohup (see the script's header).

**Batch 6** (5 cards, docs/proposals/swing-methods-2026-10/batch6/, merged from claude/batch6-cards @ 8e794f1):
coded, tested (2,737 tests pass), pre-registered (docs/preregistration/2026-10-13-batch6.md, commit 7504dbe) and
QUEUED: `scripts/on_power.sh scripts/run_prereg_batch.sh b6 2026-10-13 ...` (PID 74305, log
data/logs/research/batch6.log) waits for run_batch5.sh to end, then runs the SVXY volatility-premium book
(research/vrp_overlay.py -> ...-batch6-vrp-results.md), replays the four stock cards on 2024-26 and on 2017-24 for
those that meet the rule, grades (...-batch6-results.md, -iwm.md) and Telegrams. Store: data/live/replay_b6.duckdb
(scripts/build_b6_store.py: live store copy + 2016-24 bars for SVXY, IWD, IWF, BIL + table `sic` from EDGAR);
`data/b6.py` joins `sic2` and the ETF factor returns only on that store. Harness finding, in the pre-registration:
`within_industry_reversal_no_news` had only 36 scored names on 2025-10-31 (few large caps go 21 sessions without
news), so that book holds nearly every eligible name.
Speed-up to do when batch 5 reaches 2017-24: its replays run one at a time on an unmeasured 30 GB budget. Read a
running replay's memory (`ps -o rss`), then restart the runner with a real figure (edit `--job-gb` in
scripts/run_batch5.sh, kill the wrapper, the script and prereg_run but NOT the replay, start the script again:
`todo` skips what is finished or running). For batch 6 the same knob is the GB17 variable.

When it is done: commit the results files and docs/income_view.md. A card that passes goes to a forward test only:
`shadow_only` in config/live.yaml, and `probation: true` (paper, quarter risk; owner said yes) for ordinary swing
signals the live sizer can trade.

Fixed 2026-10-13 (commit c28625e): a limit entry could take a target its fill bar reached before the fill
(`backtest._check_exit` sold at that bar's open; `shadow.grade_one` counted its high). On the fill bar of a limit
filled away from the open, only the close now counts as after the fill. One registered strategy is affected,
`elder_ma_penetration_channel`; its rows on the older boards are flattered and were not regraded. Batch 5's two
limit-entry cards carry no Signal target (their pre-registered workaround), so they do not change.

Other paper venues (owner: "begin other sandbox or paper trading sites as able"). Checked 2026-10-13, web only:
- Second Alpaca paper account: the one worth having. Same adapter, no new code: real environment variables win over
  .env, so a second book is a settings file that `extends: live.yaml` with its own `state/` paths, launched with
  ALPACA_API_KEY / ALPACA_SECRET_KEY set from a second pair of keys. Alpaca's forum says 3 paper accounts per login
  (undated post; the dashboard decides). Use: the probation book (quarter risk, small-cap universe via
  `universe.skip_top`) apart from the three rsi2 positions. NOT NEEDED YET: the small-cap map left no candidate.
  The owner asked Claude to set it up by controlling the laptop (19:21 ET); Claude does not create accounts or
  handle keys, so when a card earns paper he creates the account and puts its keys in .env as ALPACA2_API_KEY /
  ALPACA2_SECRET_KEY.
- Tradier sandbox: free with an account, fills on 15-minute delayed quotes, OTOCO brackets in the API. Needs a new
  adapter and adds nothing over Alpaca paper. Not built.
- IBKR paper: needs an open IBKR Pro account and a desktop gateway that is logged in by hand every day. No.
- tastytrade sandbox: positions are wiped every 24 hours. Useless for swing holds.
- No account needed: the shadow ledger already forward-tests every `shadow_only` strategy at next-open prices.

Batch 5 (owner 12:54 ET: "scrape as many possible online traders ... integrate as many more methodologies as
possible"): the research thread checked 49 ideas, kept 15 strategies and one filter
(docs/proposals/swing-methods-2026-10/batch5/). All 15 are coded (`swing_engine/strategies/`, joins
`data/b5_events.py`, `data/b5_fundamentals.py`, shared `strategies/_b5.py`), registered disabled, tested on
synthetic panels (2,705 tests pass), and checked to run on real bars (signal counts only).

Owner, 13:14 ET: "keep running". Done since:
- **Income view** (docs/income_view.md, `research/income_view.py`): the 11 portfolios already replayed, read the way
  he defined winning. Steadiest: dividend_month_premium (7.9% and 6.2% a year, 63% and 68% of months up, deepest
  drops 12% and 9%, about half invested), volatility_managed_spy, large_cap_gross_profitability,
  large_cap_net_repurchasers. All are long stock in rising markets and none beat SPY; a selection made after the fact.
- **Forward tracking, no orders**: dividend_month_premium, large_cap_net_repurchasers and
  large_cap_gross_profitability are `shadow_only` in config/live.yaml. The nightly now joins their inputs
  (`join_share_issuance`, `join_dividends`; a failed join is logged, never fatal) and refetches the current month
  of dividends in its ingest step. First signals: the October month end. Checked read-only on real data for
  2026-09-30 (40, 25 and 46 signals).
- NOT built: paper trading of a 50-name monthly book. The live sizer has one set of limits (8 positions, 5 new
  orders a day); a book needs per-strategy limits there and in the autopilot's daily cap. Build it when a book
  earns it in the shadow ledger, or on the owner's word.

Owner's answers, 2026-10-13 12:53 ET (his words are in the thread; summary):
- **Paper probation: yes**, about a quarter of normal risk. Built: `strategies.<name>: {enabled: false, probation: true}`
  is scanned and sized at `risk.probation_risk_mult` (0.25) in every regime, and `execution.autopilot` drops such
  intents on anything but a paper broker. Nothing is on probation yet: no candidate exists until the small-cap map.
  A small-cap candidate also needs the live scan to cover that universe (the nightly screens the top 1,500).
- **Winning** = consistent revenue he can scale, not "beat SPY" as such. Report money made and size of drops first,
  the SPY comparison beside it. About a $10k account; small or thin stocks are fine.
- **Weekly one-page report: yes.** The nightly already writes and Telegrams it on the week's last session
  (`agent/weekly.py`); it now also lists the week's research verdicts, probation strategies and the
  "waiting for the owner" lines of this file.
- **Method sweep**: "scrape as many possible online traders ... integrate as many more methodologies as possible".
  Handed to a cloud research thread through the coordinator (13:00 ET); cards are to arrive on branch
  `claude/batch5-cards` under docs/proposals/swing-methods-2026-10/batch5/ with index.json. Then: pre-register the
  batch as a map (as the small-cap one), implement with the add-strategy skill, replay on both universes.

Owner, 2026-10-13 12:48 ET: "double down on testing ... high priority to winning trade methods ... don't aim for
perfection". Done since:
- **Edge map** (docs/edge_map.md, `research/edge_map.py`): all strategies split by the stock's dollar volume, graded
  against SPY. 0 of 711 cells are positive in both windows at t >= 1 (luck alone would give about 18): on the 1,500
  most liquid stocks these methods are worse than nothing. 2,637 cells logged (6,742 trials).
- Found: every replay so far used only the 1,500 most liquid names (`universe.max_symbols`). The small-cap run above
  is the first look anywhere else. `universe.skip_top`, `research run --no-rebuild`, `edge_map --windows/--tag`.
- `execution.reuse_exiting_slots` (replay only, default off) fixes half-invested monthly books for future cards.

## Fourth session (2026-10-13, branch claude/project-thread-4wq9xa, PR https://github.com/Jackpep-bot/Swing-T/pull/2; includes PR 1's commits)
No jobs running. Nothing enabled on paper (config/live.yaml enables no strategy). 2,574 tests pass. No strategy has
passed anything: every pre-registered card to date is FAIL and the leaderboard has no survivors.

Owner said yes to both questions on 2026-10-13 11:48 ET ("1 and 2 yes to both"):
- **Live store repaired** 11:49 ET: `repair.merge_duplicates` on data/live/market.duckdb, run id
  `20261013T154911779985Z` (373 merged, 315,230 duplicate bars deleted, 19,923 moved, 693 bars of earlier ticker
  holders dropped; bars 15,842,907 -> 15,546,907). Copy from just before: data/live/market_premerge_20261013.duckdb.
  Undo: `swing --settings config/live.yaml repair-store --undo 20261013T154911779985Z`. Unresolved, left alone:
  EEQ~20181219 / EE~20181219.
- **Dividends**: `swing ingest-dividends` -> `dividends` table in the live store (367,989 rows, 2016-01 on; rerun
  to refresh). `data/dividends.py` maps a row to the store's series on its ex-date, split-adjusts rates, builds the
  `div_season` flag and `total_return_adjust` (research copies only). data/live/replay_tr.duckdb is the
  total-return copy (config/prereg_div.yaml).
- **Dividend-month card**: pre-registered (docs/preregistration/2026-10-13-dividend-month.md, commit 433c292).
  Run once 2026-10-13 (results file beside it): **FAIL**. Alpha vs total-return SPY +0.3% a year (t 0.11) in
  2017-24, -1.5% (t -0.34) in 2024-26. The book ran about half invested (`no_free_slot`: a month's outgoing names
  hold their slots when the next month's are sized); noted in the results, not re-run.

Still waiting for the owner:
1. Always-on free host (Oracle Always Free VM) for the nightly and forward tests: yes or no? He quoted the question
   on 2026-10-13 without answering it. Not started.
2. Delete old lane store copies in data/live (replay*.duckdb except replay_p3 and replay_tr, market_prerepair.duckdb,
   regrade_1r.duckdb: about 25 GB)? Keep research_20261010-033614_l0/l1 (the current board reads them).

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
- Monthly books under-invest in replay: names sold at a month's first open still hold their slots when that
  month's buys are sized (`no_free_slot`), so a full rotation fills about half the book (dividend card: 48% exposure;
  batch 2 and 3 were less affected because they hold for months). An engine change; any re-test is a new trial.
- Rename merge does not touch `panel` (nightly rebuilds it) or the event tables keyed by the old ticker.

Next: a `swing research run` on the repaired store only if a new candidate needs it (the read-time dedupe already
gives the corrected board; lane stores of run 20261010-033614 predate the repair). Refresh dividends with
`swing ingest-dividends` before any further dividend work; a bad row in the feed has ex_date 3026-03-31 (harmless).

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
