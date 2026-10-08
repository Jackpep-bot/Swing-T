---
slug: rich_simple_trend_channel
name: Simple Trend Channel system (James & John Rich)
originators: [James E. Rich, John B. Rich (S&C Nov 2015), thinkorswim strategy + Stock Hacker filter]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [3, 30]     # estimate; exit on close below SMA(low,8) or before earnings
timeframe: daily
direction: long_only_in_engine (original long and short)
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Simple Trend Channel (Rich & Rich)

## One-line summary
Market and stock both in an uptrend (S&P 500 and stock above their 50-day SMA), buy when the close crosses above the 8-day
SMA of highs, exit on a close below the 8-day SMA of lows, and never hold through earnings.

## Origin and lineage
James E. and John B. Rich, S&C Nov 2015. thinkorswim ships it as two parts: the SimpleTrendChannelFilter (market/stock
trend check) and the SimpleTrendChannel strategy.

## Exact rules
- Market filter: S&P 500 close vs its 50-day SMA.
- Stock trend check (input `trend check`): Min = close vs SMA(50); Normal adds SMA(20); Max is stricter and also uses the
  200-day SMA and requires the stock to trend with the market. The exact Normal/Max inequalities are in the filter study;
  the TOS page text is truncated in our catalog, so they are **not verified here**.
- Long entry: filter says uptrend, close crosses above SMA(high, 8), and no earnings report in the next 2 sessions.
- Long exit: close < SMA(low, 8), or the session before earnings.
- Shorts mirror (not used). Entry next open; no initial stop, target or sizing in the original.

## Why it should work
Trend continuation when market and stock agree; the 8-day high/low channel is a volatility-scaled breakout and trailing exit.
Earnings avoidance removes the largest single-day gap risk.

## When it works and when it fails
Broad uptrends where most stocks sit above their 50-day. Fails in choppy markets around the S&P 50-day (filter flips) and
in sharp selloffs where the SMA(low,8) exit fills far below via gaps.

## Parameters and sensitivity
Channel 5-13 (default 8), filter MA 50, earnings buffer 1-3 days. Trade count is sensitive to the channel length.

## Evidence
In-sample S&C illustration only (grade D); broker publishes no statistics. No independent test found.

## Common mistakes
Using a forward-looking earnings calendar in backtests (must be the calendar as known on `as_of`); ignoring that the exit
is a close-based rule, not an intraday stop.

## Discretionary parts and how to make them mechanical
Fully mechanical given a point-in-time earnings calendar.

## Implementation spec for swing-engine
- Module `strategies/simple_trend_channel.py`, `@register("strategy")`.
- Reuses sma_20, sma_50, sma_200, market_trend_state (approximation: the original only needs SPX close > SMA50, so add
  `market_close_above_sma50` or compute from the `market` frame), atr_14.
- Missing: SMA(high,8), SMA(low,8) (compute in-module); **earnings_dates_point_in_time** feed (catalog maps_to). Until it
  exists, run with `earnings_filter: off` and flag results.
- Signal at close t: market filter true, `close[t] > sma(high,8)[t]` and `close[t-1] <= sma(high,8)[t-1]`, trend check Min
  (`close > sma_50`) by default. Entry next open.
- Stop: max(sma(low,8)[t], entry - 2.5 x atr_14) below entry. Target: None.
  `should_exit`: close < sma(low,8) or next session is an earnings date.
- `max_hold_days`: 30. `min_reward_risk`: not applied.
- settings.yaml: `simple_trend_channel: {enabled: false, shadow_only: true, channel: 8, trend_check: min}`.

## What the router should know
Comparison system and a template for earnings avoidance; the earnings exit logic is reusable by other trend strategies.

## Signs of decay to monitor
Rising share of exits by gap through the channel; filter flipping more than ~4 times per quarter.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/R-S/SimpleTrendChannel
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/R-S/SimpleTrendChannelFilter

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 6689 | 53 | 47% | +0.05 | -0.14 | 41% | +0.08 | -0.11 | 36% | +0.20 | +0.01 | 1.30 |
| correction | 706 | 16 | 51% | +0.22 | -0.23 | 46% | +0.15 | -0.30 | 41% | +0.28 | -0.17 | 1.46 |
| healthy_uptrend | 27478 | 264 | 43% | -0.00 | -0.20 | 36% | -0.05 | -0.25 | 29% | -0.01 | -0.21 | 0.98 |
| high_vol_selloff | 2124 | 58 | 46% | +0.02 | -0.18 | 39% | -0.02 | -0.22 | 25% | -0.20 | -0.40 | 0.75 |
| narrow_uptrend | 2200 | 47 | 33% | -0.21 | -0.42 | 28% | -0.27 | -0.48 | 17% | -0.40 | -0.61 | 0.52 |
| **all** | 39197 | 438 | 44% | +0.00 | -0.20 | 37% | -0.03 | -0.24 | 30% | +0.00 | -0.20 | 1.00 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 21934 | 151 | 47% | +0.07 | -0.10 | 42% | +0.09 | -0.09 | 35% | +0.17 | -0.00 | 1.26 |
| correction | 16043 | 114 | 48% | +0.05 | -0.15 | 44% | +0.15 | -0.05 | 35% | +0.10 | -0.10 | 1.15 |
| healthy_uptrend | 90028 | 806 | 44% | +0.00 | -0.19 | 38% | +0.01 | -0.18 | 30% | +0.00 | -0.19 | 1.01 |
| high_vol_selloff | 9936 | 79 | 45% | -0.00 | -0.19 | 40% | -0.03 | -0.21 | 32% | -0.09 | -0.28 | 0.87 |
| narrow_uptrend | 16746 | 98 | 49% | +0.09 | -0.10 | 43% | +0.13 | -0.06 | 35% | +0.18 | -0.01 | 1.28 |
| **all** | 154687 | 1248 | 45% | +0.03 | -0.16 | 40% | +0.05 | -0.14 | 32% | +0.05 | -0.14 | 1.07 |

Portfolio replay (net of costs, slots shared with its run): 1 trades, win 100%, avg +0.14R, PF inf, P&L $124 on $100k, avg hold 16.0 bars.
