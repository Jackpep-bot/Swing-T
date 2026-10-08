---
slug: turtle_soup
name: Turtle Soup and Turtle Soup Plus One (failed 20-day breakout fade)
originators: [Linda Bradford Raschke, Laurence Connors]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [1, 5]
timeframe: daily (Turtle Soup itself needs an intraday stop-entry; Plus One is fully daily)
direction: long   # short mirror (failed 20-day high) documented; engine is long-only
regimes_good: [choppy, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null   # 55-65% appears only in unsourced restatements
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Turtle Soup / Turtle Soup Plus One

## One-line summary
Fade a fresh 20-day low that undercuts an older 20-day low and immediately reclaims it: the Donchian-20 breakout
traders (the "Turtles") are trapped, and the reclaim is the entry.

## Origin and lineage
Raschke and Connors, *Street Smarts* (1995). Named against the Turtle traders' 20-day channel breakout. Later "liquidity
sweep" ideas (ICT) restate the same failed-breakout logic. `docs/methods.md` 1b rates it D: codeable, regime-dependent,
poor in persistent trends.

## Exact rules (long; short mirrors on 20-day highs)
Turtle Soup:
- Setup: today prints a new 20-day low, and the previous 20-day low was set at least 4 sessions earlier.
- Trigger: once price is below that prior 20-day low, buy stop 5-10 ticks above it, valid today only.
- Initial stop: 1 tick under today's low. Management: trail as it becomes profitable. Hold hours to a few days.

Turtle Soup Plus One:
- Day 1: new 20-day low, prior 20-day low at least 3 sessions earlier, and day 1 closes at or below that prior low.
- Day 2: buy stop at the prior 20-day low; cancel if not filled on day 2.
- Stop: under the lower of the day-1 / day-2 lows (common restatement; wording not checked against the book).
- Exit: trailing stop, 1-5 days.
- Sizing: not specified beyond normal risk per trade.

## Why it should work
Breakout sellers and stop-loss sellers cluster just under an obvious 20-day low. When that supply is absorbed and price
reclaims the level the same or next day, the late sellers become forced buyers (stops) while dip buyers re-enter.

## When it works and when it fails
Works in ranges and pullbacks inside a larger uptrend. Fails in persistent downtrends and liquidation (a new low is just
a new low) and in news-driven breakdowns. Short side mirror fails in strong uptrends (a 20-day high in a leader is a
breakout, not a trap).

## Parameters and sensitivity
- Channel length 20 (10-55 tested in futures sensitivity charts by Oxford Capital; no numbers published there).
- Minimum age of prior low: 3-4 bars (lower = more signals, more noise).
- Entry buffer: ticks are a futures concept; for stocks use 0.05-0.10% of price or 1-2 cents.
- Trap: tuning age + buffer + trail per symbol; keep the book defaults fixed.

## Evidence
- No independent, cost-inclusive equity test located.
- Oxford Capital Strategies (oxfordstrat.com) back-tested the Plus One rules on 42 US futures 1980-2011 and graded it D;
  the page shows sensitivity charts but no headline numbers.
- 55-65% win rates circulate in restatements without a traceable test. Intraday FX/index results from "ICT" blogs are a
  different timeframe and not evidence for this setup.

## Common mistakes
Buying the new low before the reclaim; trading it in a correction regime; using a prior low that is only 1-2 bars old;
widening the stop instead of exiting when the low breaks again.

## Discretionary parts and how to make them mechanical
"Trail as profitable" -> engine trail (`execution.breakeven_after_r: 1.0`, `trail_after_r: 2.0`) plus a time stop.
"The lower the better" -> score = (prior20low - low_t) / atr_14, capped at 1.5 (deeper undercut ranks higher).

## Implementation spec for swing-engine
- Reuses: OHLC, `atr_14`, `trend_state`, `sma_200`, `dollar_vol_20d`.
- New features: `prior_low_20 = min(low[t-20 .. t-1])` (a `RollingSpec("low", "min", 20, prior=True)`),
  `prior_low_20_age` = bars between t and the bar that set `prior_low_20`.
- Plus One (fully daily): signal at close of day 1 if `low_1 < prior_low_20_1`, `close_1 <= prior_low_20_1`,
  `prior_low_20_age >= 3`. Level L = `prior_low_20_1`. Day 2: if `open_2 >= L` fill at `open_2`; elif `high_2 >= L`
  fill at L; else cancel.
- Turtle Soup (same day): on day t, armed if `prior_low_20_age >= 4`; fill if `low_t < L` and `high_t >= L + buf`, at
  `L + buf`. Ordering is only certain when `open_t < L`; when `open_t >= L` the bar may have reclaimed before undercutting,
  so mark those fills `ambiguous` and run the test with and without them.
- Initial stop: `low_1 - buf` (Plus One) / `low_t - buf` (Soup). If day-2 low is below the stop on the fill day, count
  a stop-out (conservative same-bar rule).
- Target: none taught. Comparison variant: target = `sma_20` at signal (engine choice, labelled). Otherwise
  `min_reward_risk: 0.0` and exit by trail / time.
- `max_hold_days: 5`.
- Missing: a stop-entry order hook in `research/backtest.py` and `execution` (the backtester fills only at the next
  open). Without it, a "close back above L, buy next open" proxy is a different, later trade and must be labelled.
- Filters to compare: `close > sma_200` vs none.

## What the router should know
Mean-reversion family; overlaps `rsi2_meanrev` and `sr_bounce` (a reclaimed support). Allow in `choppy` and
`narrow_uptrend`; not in `correction` or `high_vol_selloff`.

## Signs of decay to monitor
Share of fills stopped out on the same or next bar > 50%; average MFE before stop < 0.5R; win rate under 45% with
payoff < 1.5 over 50+ trades.

## Sources
- https://www.luxalgo.com/library/concept/turtle-soup/
- https://completetradersedge.com/linda-raschke-turtle-soup-pattern-trader/
- https://www.tradingview.com/script/28gN99Tw-Turtle-Soup-Indicator
- https://www.litefinance.org/blog/for-beginners/turtle-soup-1/
- https://my.tradingview.com/chart/RWC/swV5nnkS-Turtle-soup-plus-1-reversal-of-new-20-day-low
- https://oxfordstrat.com/?p=5513 (futures back-test, grade D, no headline numbers)

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 2957 | 1231 | 22% | -0.36 | -0.56 | 18% | -0.39 | -0.59 | 13% | -0.49 | -0.69 | 0.63 |
| correction | 360 | 184 | 14% | -0.76 | -0.94 | 19% | -0.40 | -0.58 | 19% | +0.06 | -0.12 | 1.05 |
| healthy_uptrend | 6801 | 3099 | 27% | -0.09 | -0.28 | 20% | -0.21 | -0.40 | 15% | -0.14 | -0.33 | 0.89 |
| high_vol_selloff | 2051 | 1055 | 33% | +0.26 | +0.10 | 29% | +0.79 | +0.63 | 20% | +0.63 | +0.48 | 1.62 |
| narrow_uptrend | 1846 | 861 | 26% | -0.05 | -0.25 | 22% | +0.15 | -0.06 | 16% | +0.01 | -0.19 | 1.01 |
| **all** | 14015 | 6430 | 26% | -0.12 | -0.31 | 21% | -0.08 | -0.27 | 15% | -0.09 | -0.28 | 0.92 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 9882 | 4324 | 24% | -0.18 | -0.37 | 20% | -0.07 | -0.26 | 16% | +0.14 | -0.05 | 1.13 |
| correction | 4915 | 2182 | 26% | +0.09 | -0.07 | 21% | +0.21 | +0.05 | 18% | +0.53 | +0.37 | 1.50 |
| healthy_uptrend | 16250 | 7570 | 24% | -0.21 | -0.40 | 19% | -0.24 | -0.44 | 14% | -0.24 | -0.44 | 0.78 |
| high_vol_selloff | 13319 | 6452 | 22% | -0.27 | -0.42 | 19% | -0.20 | -0.34 | 15% | -0.25 | -0.40 | 0.78 |
| narrow_uptrend | 6994 | 3003 | 29% | +0.03 | -0.15 | 24% | +0.06 | -0.12 | 18% | +0.19 | +0.02 | 1.18 |
| **all** | 51360 | 23531 | 25% | -0.15 | -0.33 | 20% | -0.11 | -0.29 | 15% | -0.03 | -0.21 | 0.97 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
