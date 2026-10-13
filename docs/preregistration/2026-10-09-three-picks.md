# Pre-registration: three picks (2026-10-09)

Written 2026-10-09, before any replay of these strategies was run or any result looked at.
COMMIT: 2a27797

Group: `ath_trend_following_wide_stop`, `composite_cost_aware_rank`, `earnings_seasonality` (cards:
`docs/strategies/<slug>.md`, drafted in `docs/proposals/swing-methods-2026-10/`). Jack chose to test these three as a
separate pre-registered group, graded net of per-stock costs on their own holding periods, with a multiple-testing
haircut that counts only this group of three, reported separately from the 794-trial leaderboard.

**One version of each, no sweeps. Any change to a rule, parameter, filter, window, cost rule or grading rule after a
result has been seen is a new trial, logged as such, and does not replace the result below.**

All three are registered `enabled: false` in `config/settings.yaml` and run only through the replay commands below.

---

## 1. `ath_trend_following_wide_stop` (Wilcox-Crittenden 2005; Zarattini-Pagani-Wilcox 2025)

Module `swing_engine/strategies/ath_trend_following_wide_stop.py`.

| Rule | Value | Source / why |
|---|---|---|
| Universe | the replay's point-in-time universe (`settings.universe`: price >= $5, average dollar volume >= $5M, top 1,500 by dollar volume, as-traded through the splits table), refreshed every 5 sessions | engine; stricter than the card's $1M (42-day, CPI-deflated) floor, so that floor is implied and not coded; no CPI deflation; Russell 3000 membership approximated by the top-1,500 screen |
| Price floor | close >= `min_price` = **10.0** | 2025 version (2005 used $15). Applied to the store's split-adjusted close (no unadjusted close in the panel) |
| All-time high | `ath_close` = highest split-adjusted close of the symbol from its first bar in the store through `as_of` (inclusive) | card rule 2. The store starts 2016-01-04, so "all-time" means "since 2016-01-04 or listing": about 1 year at the start of the 2017 window, 8.8-10.8 years in the 2024-26 window. Bars before the replay panel's warm-up are folded in by `data.market_series.join_pre_panel_high` (`pre_panel_high`, `pre_panel_bars`) |
| History floor | `hist_bars` (bars in the store up to `as_of`) >= `min_history_bars` = **252** | engine choice, not in the card: without it every symbol's first store bar (and every IPO's first days) is an "all-time high"; 252 = one year |
| Entry trigger | close on `as_of` >= `ath_close` (today's close is the all-time high) | card rule 2 |
| Entry timing | signal at the `as_of` close, market buy at the next open (`EntryType.OPEN`) | card |
| ATR | `atr_42`, Wilder, 42 sessions | 2025 version |
| Initial stop | close - `stop_atr_mult` x atr_42, `stop_atr_mult` = **10** | card rule 3 (with ATH = close on the signal day); 2005 paper: 8-12 no material difference, register 10 only. No signal if the stop is <= 0 |
| Trailing stop | `trail_stop(row)` = ath_close x (1 - 10 x atr_42 / close), ratcheted by the engine (never lowered, never through the close), live from the next session | card rule 3. **Deviation:** the engine's stop is a resting stop hit on the daily low (gap-through fills at the open), not "exit next open after a close below the stop" |
| Engine overlay | `engine_trail = False` (no breakeven at +1R, no 10-day-low trail) | the overlay would cut the long winners the method depends on |
| Target | none (`min_reward_risk` 0) | card rule 4 |
| Time stop | none: `max_hold_days` = **10,000** sessions | card rule 4. Finite so `run_backtest`'s 20-bar default (`DEFAULT_MAX_HOLD_BARS`) never applies; replay / position manager read the same param |
| Market regime gate | none | card ("the published version has none") |
| Same-day ranking | `score` = close / atr_42 (lowest volatility first) | card sizes by 1/sigma, so when the replay's slots are scarce the lower-volatility breakout is taken first |
| Columns read | close, `ath_close`, `hist_bars`, `atr_42` (`features.extra`; `ath_close` / `hist_bars` read `pre_panel_high` / `pre_panel_bars` when the panel has them) | |

## 2. `composite_cost_aware_rank` (Novy-Marx-Velikov 2016; DeMiguel et al. 2020; Chen-Velikov 2023)

Module `swing_engine/strategies/composite_cost_aware_rank.py`; score column `ccr_score` in `features/extra.py`.

| Rule | Value | Source / why |
|---|---|---|
| Universe | replay universe (as above), then the card's filters below | |
| Eligibility (per session) | close >= **5.0**; `med_dv_63` (median of close x volume over 63 sessions) >= **$20M**; market cap (EDGAR `shares_outstanding` x close) >= the session's **20th percentile** of market cap over panel rows with a known market cap | card rule 1; "bottom 20% of the store's market cap" taken over every panel row of the session (no NYSE breakpoints) |
| Input a: momentum | `mom_12_1` = close[t-21] / close[t-252] - 1 | card 2a, plain 12-1 (the first option named; residual momentum is not used) |
| Input b: profitability | `gross_prof` = TTM gross profit / latest total assets (EDGAR XBRL, usable the session after the filing date) | card 2b, gross (cash profitability is not built) |
| Input c: 52-week-high proximity | `dist_52w_high` = close / `high_52w` - 1 (`high_52w` = highest high of 252 bars) | card 2c |
| Input d: low volatility | minus the standard deviation of daily log returns over 252 sessions, all 252 required (`features.cross_section.realized_vol`) | card 2d |
| Score | `ccr_score` = equal-weight mean of the four same-session percentile ranks, ranked among eligible rows that have all four inputs; NaN otherwise | card rule 2, fixed equal weights |
| Rank | `ccr_score_rank` = same-session percentile of `ccr_score`; replay re-ranks it among its point-in-time universe (`replay._rerank_extras`) | |
| Rebalance | last NYSE session of each month (`month_end` = 1, published calendar): signals at that close, fills at the next open (the first session of the new month) | card rule 3 ("monthly, first session, next-open fills") |
| Buy zone | `ccr_score_rank` > **0.90** (top 10%) | card rule 3 (Novy-Marx-Velikov 10%/20% band) |
| Hold zone / exit | on a rebalance row, a held name is sold (next open) when `ccr_score_rank` <= **0.80** (left the top 20%) or has no rank | card rule 3. Equivalent to `risk.selection.rank_hysteresis(ranked, held, 0.10, 0.20)`, split into the entry rule and `should_exit` because a strategy has no held set (tested in `tests/test_strategy_three_picks.py`) |
| Stop | catastrophe stop entry - **3 x atr_63**, static | card rule 5 (optional, "for the paper book"); the engine needs a stop to size |
| Engine overlay | `engine_trail = False` | rank exit only |
| Target / time stop | none; `max_hold_days` = **10,000** | the rank is the exit |
| Weighting | the replay's sizing (below), not equal / inverse-vol weight; no 30-50 name book | **deviation** from card rule 4 forced by grading the strategy alone in the replay |
| Same-day ranking | `score` = `ccr_score_rank` | |
| Crash filter | none | card: optional, not registered |
| Columns read | close, volume, `mom_12_1`, `dist_52w_high`, `med_dv_63`, `gross_prof`, `shares_outstanding`, `atr_63`, `month_end`, `ccr_score`, `ccr_score_rank` | `gross_prof` / `shares_outstanding` come from `join_edgar`, which the replay joins before extras. The CLI scan and nightly attach extras before `join_edgar`, so there the score is NaN and the strategy is silent (replay-only strategy) |

## 3. `earnings_seasonality` (Chang, Hartzmark, Solomon & Soltes, RFS 2017)

Module `swing_engine/strategies/earnings_seasonality.py`; panel columns `earn_season`,
`sessions_to_expected_earnings` from `data.fundamentals` (joined by `join_edgar`).

| Rule | Value | Source / why |
|---|---|---|
| EPS series | quarterly diluted EPS from EDGAR XBRL (`quarterly_values`, Q4 = fiscal year minus the three quarters), the latest filing per period known on the filing date, usable the session after it | card spec. **Deviations:** diluted, not basic ex-extraordinary; not split-adjusted (a split inside the 23-quarter window can distort the ranks; not corrected) |
| Seasonality | needs the 23 most recent quarters t-23..t-1 known, consecutive (each quarter end 80-100 days after the previous). Rank t-23..t-4 (20 quarters) from largest EPS (rank 1) to smallest; `earn_season` = mean rank of t-4, t-8, t-12, t-16, t-20. Low = historically strong upcoming quarter | card rules 1-3 |
| Expected announcement E | the earliest 8-K Item 2.02 reaction session in the 364 calendar days up to `as_of`, plus 364 calendar days, rolled forward to an NYSE session; `sessions_to_expected_earnings` = sessions from `as_of` to E | card rule 4 (announcement a year earlier); 364 days keeps the weekday. The card's "+/- 7 days" is not used for entry (the actual date is unknown in advance) |
| Staleness guard | `earn_season` is NaN unless E falls 0-90 days after (latest known quarter end + 91 days), i.e. the ranked quarter is the one E will announce | engine choice so a late 10-Q cannot shift the ranks by a quarter |
| Eligibility | close >= **5.0**; `med_dv_63` >= **$20M** | card engine version |
| Sort population (each session) | eligible rows with finite `earn_season` and E 1-21 sessions ahead (expected announcers of the coming month) | card rule 4 (monthly sort of expected announcers), made point-in-time on the session |
| Top quintile | percentile of -`earn_season` in that population > **0.80** | card: long the top quintile only |
| Entry trigger | `sessions_to_expected_earnings` == **6** on `as_of` (fill next open = 5 sessions before E), in the top quintile, and `days_since_earnings` >= **25** sessions (the coming quarter is not already out) | card engine version (entry 5 sessions before E); the 25-session check is an engine choice |
| Entry timing | next open (`EntryType.OPEN`) | |
| Exit | rule exit when the next 8-K 2.02 has arrived during the hold and `days_since_earnings` >= **2** (fires at the close of the 2nd session after the announcement session, fills the next open) | card: "exit at the close 2 sessions after the actual announcement"; the engine fills rule exits at the next open, so it holds one overnight longer |
| Time stop | `max_hold_days` = **25** sessions (no announcement) | card |
| Stop | entry - **3 x atr_14**, static | engine choice (the paper has none; same as `pead_sue`); the engine needs a stop to size |
| Engine overlay | `engine_trail = False` | hold to the event, as the paper does |
| Target | none | |
| Same-day ranking | `score` = the quintile percentile | |
| Columns read | close, `med_dv_63`, `atr_14`, `earn_season`, `sessions_to_expected_earnings`, `days_since_earnings` | |

Data coverage: XBRL starts about 2009-2011, so 23 quarters exist from about 2015-2017; early 2017-24 window is thin.
Before replaying, rebuild the cached events table on each research store copy so it carries `earn_season`:
`uv run python -c "from swing_engine.data.store import Store; from swing_engine.data.fundamentals import build_fundamental_events as b; print(b(Store('<copy>.duckdb')))"`.
Without the rebuild `join_edgar` logs `edgar_events_cache_stale` and the strategy sees NaN (no trades).

---

## Test windows

| Window | Dates | Store |
|---|---|---|
| A (survivorship-free) | 2024-10-07 .. 2026-10-05 | research copy of the repaired store |
| B (repaired store with delisted names) | 2017-01-01 .. 2024-10-04 | research copy of the repaired store (~2,800 delisted names) |

## How it is graded

1. Portfolio replay of each strategy ALONE, its own exits, no router, one fresh store copy per concurrent run:
   `uv run swing --settings config/prereg3.yaml replay --start 2024-10-07 --end 2026-10-05 --no-router -s <slug> --tag prereg3-<slug>`
   `uv run swing --settings config/prereg3.yaml replay --start 2017-01-01 --end 2024-10-04 --no-router -s <slug> --tag prereg3-<slug>`
   (6 runs, run one after another in one store, data/live/replay_p3.duckdb). Settings: `config/prereg3.yaml` (extends `replay.yaml`), set before any run: risk 0.5% per trade to the stop, max position 5% of equity, max 30 open positions, max 10 new orders per day, sector cap 30%, $100,000 start. These caps are NOT changed after any run. Positions open at a window's end are closed at its last
   close (replay `end`).
2. Costs: the replay's `CostModel` defaults (10 bp per side slippage, SEC fee and FINRA TAF on sales), plus a
   per-stock top-up from `research.costs.cost_table` (Abdi-Ranaldo half-spread, floor 10 / 20 bp) on store bars:
   per trade, extra = max(0, cost_bps(entry signal date) - 10) / 10^4 x entry notional + max(0, cost_bps(exit date)
   - 10) / 10^4 x exit notional (qty x exit price). The 10 bp already charged by the replay is not charged twice.
   The extra cost is booked on the trade's exit date and subtracted from the daily equity curve from that date on.
3. Report per strategy per window: trades; net R per trade = mean of (pnl - extra) / (qty x (entry price - initial
   stop)); t-stat of net trade R (mean / (sd / sqrt(n))); annualised Sharpe of the net daily equity curve
   (`research.metrics.sharpe`, 252); max drawdown of that curve; exposure (mean of the replay's daily
   market value / equity). Also: average holding days, share of net P&L from the top 7% of trades (ATH card).

## Multiple testing

- Harvey-Liu Bonferroni haircut (`research.metrics.haircut_sharpe`) on each window's annualised net Sharpe with
  **n_trials = 3** and years = daily returns / 252.
- Deflated Sharpe (`research.metrics.deflated_sharpe`) with **n_trials = 3**, n_obs = daily returns, the daily
  returns' skew and kurtosis, periods_per_year 252. Reported, not a pass criterion.
- These six replays are also logged to the trial log by `swing replay`; the 794-trial leaderboard is reported
  separately and unchanged by this group's grading.
- What "positive haircut Sharpe" means with n = 3 (my arithmetic from the formula): p_adj = 3p < 1, i.e. t > 0.967,
  i.e. an annual net Sharpe above about 0.69 in window A and about 0.35 in window B.

## Pass criteria (each strategy on its own)

PASS only if ALL of:
1. positive haircut Sharpe (n_trials = 3) in window A AND in window B;
2. net R per trade > 0 in window A AND in window B.

Otherwise FAIL, recorded in the card's `## Empirical (replay)` and in `docs/STATUS.md`. A pass goes to the
walk-forward skill and gates.md; it does not enable anything.

## Known limits (stated before results)

- The replay book holds at most 8 names: ATH (10-ATR stops, ~4% positions at 1% risk) runs at low exposure and
  locks slots for months; the composite holds about 8 of a 30-50 name design. Results describe these books, not the
  papers' portfolios.
- ATH lookback is capped by the store start (2016-01-04).
- Earnings seasonality uses diluted, unadjusted-for-splits XBRL EPS and a 364-day expected date.

## Amendment 1 (2026-10-09, harness only, after a run that produced no trades)
The first six runs (16:00 ET) produced zero trades: every signal was refused by the portfolio's 2:1 reward/risk
floor (`skip_reasons: below_min_reward_risk`) because these strategies exit on their own rules and set no target.
That is a sizing-config omission, not a strategy result. Fix: `min_reward_risk: 0.0` for the three strategies in
`config/settings.yaml` (as every other rule-exit strategy in the engine has). No strategy rule or parameter changed.
The zero-trade runs are discarded; the six runs are repeated once with the same commands.
