---
slug: weinstein_stage2_breakout
name: Weinstein Stage 2 breakout (weekly 30-week MA, Mansfield RS)
originators: [Stan Weinstein]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [20, 180]
timeframe: weekly (daily panel for stops and execution)
direction: long (the book also teaches Stage 4 shorts; the engine is long-only)
regimes_good: [healthy_uptrend]
regimes_bad: [correction, high_vol_selloff, choppy]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Weinstein Stage 2 breakout

## One-line summary
Buy the weekly close that lifts a stock out of a flat Stage 1 base above a 30-week moving average that has stopped
falling, on breakout-week volume at least 2x the prior 4-week average and with Mansfield relative strength above
zero; trail the stop under correction lows or the rising 30-week MA.

## Origin and lineage
Stan Weinstein, *Secrets for Profiting in Bull and Bear Markets* (1988). Stage analysis divides a stock's cycle into
Stage 1 base, Stage 2 advance, Stage 3 top and Stage 4 decline. It underlies Minervini's Trend Template (30-week =
150-day line) and Stine's 30-week breakout (see `stine_insider_superstock_weekly`). It is still taught today by
stageanalysis.net (a community forum and blog) with a numeric "breakout quality checklist".

## Exact rules
- **Universe/screen:** weekly charts. Rank sectors and groups first, then stocks. Avoid heavy overhead resistance
  close above the breakout.
- **Setup (Stage 1):** the decline stops. Price moves sideways around a 30-week SMA that flattens.
- **Trigger, trader method:** a weekly close above the top of the Stage 1 base (resistance) and above a 30-week MA
  that is flat or turning up.
  - Breakout-week volume must be at least 2x the average of the prior 4 weeks. stageanalysis.net also accepts at
    least 3x average daily volume on the breakout day.
  - Mansfield RS must be above its zero line or crossing above it.
- **stageanalysis.net checklist (fetched 2026-10-07):** 30-week MA flattening or rising; 10-week MA rising; daily
  50-day above the 150-day and rising; monthly close above the 30-month MA; relative performance above its zero
  line, which it defines as a 52-week MA.
- **Investor method:** buy the first pullback toward the breakout level or the 30-week MA after a Stage 2A
  breakout. Continuation buys use later Stage 2 bases with the same checks.
- **Entry order:** Weinstein places buy-stops just above resistance. The daily-bar version enters at the next
  session's open after the qualifying Friday close.
- **Initial stop:** below the base low or the last correction low under the breakout. The book's exact stop
  offsets were not re-read in this run (unverified).
- **Trailing:** raise the stop under each new correction low. Investors trail under the rising 30-week MA.
- **Exit:** Stage 3 signs (MA flattens, price chops across it) or a Stage 4 break below support and the MA. There
  is no profit target.
- **Sizing:** not quantified in the sources read.

## Why it should work
A Stage 1 base absorbs sellers who are trapped from Stage 4. The 2x-volume breakout shows demand taking over, and
the 30-week trend filter keeps you on the side of time-series momentum. The traders on the other side are
base-sellers and short-sellers who expect mean reversion. The mechanism is the same 52-week-high and momentum
underreaction effect behind the Trend Template.

## When it works and when it fails
- **Works:** broad advances after a basing market, such as an early bull leg with rising breadth. Group rotation
  helps because weekly breakouts cluster by sector.
- **Fails:**
  - Choppy, range-bound tapes: the 30-week MA whipsaws.
  - V-shaped recoveries: the MA lags, so entries come late.
  - Narrow markets, where few bases resolve upward.
- Stage 2 breakouts during a market-wide Stage 4 are the classic failure.

## Parameters and sensitivity
- `ma_weeks` = 30. Do not tune this: it is the definition of the method.
- `vol_mult_4w` = 2.0 (range 1.5 to 3).
- `base_min_weeks`: the source gives no number. Try 8 to 26.
- `base_max_depth`: unverified. Try 0.25 to 0.35.
- `rs_zero_ma_weeks` = 52.
- `ma_slope_lookback_weeks` = 4.
- **Overfitting traps:** the base definition (length, depth, flatness) has many free knobs and only a few weekly
  signals per stock per decade. Log every variant in `research/trials.py`.

## Evidence
- No independent test of the full method was found (`docs/methods.md` 1b rates it D; catalog C28).
- Only the trend filter has support. The 10-month / 30-week SMA filter is rated B for drawdown control in
  `docs/methods.md` row 1 (SSRN 2677212; CXO long-run MA timing). It lags in choppy rising markets.
- No post-publication decay study exists.

## Common mistakes
- Buying a breakout while the 30-week MA is still falling (that is a Stage 4 rally).
- Ignoring the breakout-week volume test.
- Buying late Stage 2 or Stage 3 extensions.
- Using the daily 150-day SMA without checking its slope.
- Calling a weekly signal before Friday's close.

## Discretionary parts and how to make them mechanical
- **"Top of base"** = max weekly high over the last `base_min_weeks` to `base_max_weeks` weeks before the trigger
  week, with (max high - min low) / max high <= `base_max_depth`.
- **"Little overhead resistance"** = no weekly high within the last 104 weeks between the entry and entry x 1.15
  (param).
- **Stage 3 / 4** = `wk_sma_30` slope <= 0 and a weekly close below it.
- **Group strength** = sector RS rank. The engine has no sector data in the panel today.

## Implementation spec for swing-engine
Build a new `features/weekly.py`, shared with Stine. Resample each symbol to weeks ending Friday:
`wk_close` = last close, `wk_high` = max, `wk_low` = min, `wk_volume` = sum.

Features:
- `wk_sma_30 = mean(wk_close, 30)`; `wk_sma_10 = mean(wk_close, 10)`.
- `wk_sma_30_slope = wk_sma_30 / wk_sma_30.shift(4) - 1`.
- `wk_vol_ratio_4 = wk_volume / mean(wk_volume.shift(1), 4)`.
- Mansfield RS (common definition; Weinstein's own scaling was not verified):
  `rp = wk_close / spy_wk_close`, `mansfield_rs = (rp / mean(rp, 52) - 1) * 100`.
- `wk_base_top = max(wk_high.shift(1), base_weeks)`; `wk_base_low = min(wk_low.shift(1), base_weeks)`.

Point-in-time rule: a week's values may be joined to daily rows only after that week's last session. Forward-fill
completed weeks and never use a partial week. Add a shift test.

Daily alternatives: `sma_150` (missing: add it to the indicator windows), plus `sma_50` and `sma_200` (both exist).

Signal (evaluate on the last session of a week):
- `wk_close > wk_base_top`
- `wk_sma_30_slope >= 0`
- `wk_close > wk_sma_30`
- `wk_vol_ratio_4 >= 2.0`
- `mansfield_rs > 0`
- base depth <= `base_max_depth`

Orders and exits:
- **Entry:** next open, or a limit at `wk_close * 1.01` (param).
- **Stop:** `wk_base_low` (or the last weekly swing low), capped at `max_stop_pct` = 0.15 (param, not from source).
- **Target:** none. Set `min_reward_risk: 0.0` in settings, like `rsi2_meanrev`.
- **`should_exit`:** weekly close < `wk_sma_30`, or the weekly trailing stop under the last correction low.
  The trailing stop needs a weekly swing-low trail hook; `execution.trail_after_r` is the daily 10-bar low.
- **`max_hold_days`:** 180.
- **Reuse:** `trend_state`, `high_52w`, `dist_52w_high`, `market_trend_state`.
- **Missing:** weekly resampler, `sma_150`, the SPY weekly join for Mansfield RS, a per-strategy override of
  `earnings_exit_days`, and a stop-entry order type (execution intents only carry `entry_limit`).

## What the router should know
- This is a slow, weekly strategy. Allow it in `healthy_uptrend` only. It overlaps with `breakout_52w`,
  `base_breakout` and Stine, so log it in the breakout family.
- Weekly signals arrive on Fridays only. Do not count it toward daily signal caps.
- `earnings_exit_days` = 1 will cut positions meant to last months. Decide per strategy.

## Signs of decay to monitor
- Share of breakouts that close back below `wk_base_top` within 4 weeks.
- Median MFE in R at 13 weeks.
- Count of weekly qualifiers versus breadth (% above the 200-day).
- Stop-outs in the first 2 weeks above 50%.

## Sources
- Stan Weinstein, *Secrets for Profiting in Bull and Bear Markets* (1988). Not re-read in this run.
- https://stageanalysis.net/blog/4372/stage-analysis-breakout-quality-checklist (fetched 2026-10-07)
- https://www.stageanalysis.net/forum/printthread.php?tid=14
- https://traderlion.com/trading-strategies/stage-analysis/
- https://www.mql5.com/en/articles/22746 (catalog source; not read in this run)
- https://papers.ssrn.com/abstract=2677212 (trend-filter evidence cited by `docs/methods.md`)
- `docs/methods.md` 1b and 2c; `docs/methods/14-insider-buy-superstocks-stine.md` (weekly feature spec)

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 75 | 0 | 52% | -0.01 | -0.02 | 53% | +0.01 | -0.00 | 51% | +0.05 | +0.03 | 1.24 |
| correction | 5 | 1 | 75% | +0.28 | +0.27 | 100% | +0.51 | +0.49 | 75% | +0.80 | +0.78 | 10.09 |
| healthy_uptrend | 334 | 0 | 55% | +0.03 | +0.01 | 57% | +0.07 | +0.06 | 53% | -0.01 | -0.02 | 0.96 |
| high_vol_selloff | 36 | 0 | 64% | +0.04 | +0.03 | 42% | -0.11 | -0.13 | 31% | -0.28 | -0.29 | 0.27 |
| narrow_uptrend | 31 | 0 | 48% | -0.05 | -0.06 | 36% | -0.25 | -0.26 | 48% | -0.14 | -0.16 | 0.56 |
| **all** | 481 | 1 | 55% | +0.02 | +0.01 | 54% | +0.03 | +0.02 | 51% | -0.02 | -0.04 | 0.92 |

Portfolio replay (net of costs, slots shared with its run): 24 trades, win 46%, avg +0.31R, PF 1.64, P&L $6,873 on $100k, avg hold 79.8 bars.

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 288 | 1 | 49% | +0.01 | -0.00 | 55% | +0.08 | +0.07 | 56% | +0.10 | +0.09 | 1.53 |
| correction | 72 | 0 | 58% | +0.04 | +0.03 | 61% | +0.05 | +0.03 | 61% | +0.08 | +0.06 | 1.46 |
| healthy_uptrend | 1684 | 0 | 47% | -0.01 | -0.03 | 47% | -0.02 | -0.03 | 51% | -0.01 | -0.02 | 0.97 |
| high_vol_selloff | 166 | 0 | 54% | +0.03 | +0.02 | 52% | -0.12 | -0.13 | 56% | -0.07 | -0.08 | 0.79 |
| narrow_uptrend | 203 | 0 | 53% | +0.01 | -0.00 | 53% | +0.02 | +0.00 | 50% | +0.01 | -0.00 | 1.04 |
| **all** | 2413 | 1 | 49% | -0.00 | -0.02 | 49% | -0.01 | -0.02 | 52% | +0.01 | -0.01 | 1.03 |

Portfolio replay (net of costs, slots shared with its run): 106 trades, win 30%, avg -0.20R, PF 0.72, P&L $-14,814 on $100k, avg hold 76.4 bars.
