---
slug: macd_zero_line_swing_points
name: MACD zero-line crosses confirmed by swing structure (ChartSchool)
originators: [Gerald Appel (MACD, late 1970s), StockCharts ChartSchool]
category: setup
decision: implement_disabled_for_comparison
holding_period_days: [5, 40]
timeframe: daily
direction: long (short mirror in source; engine long-only)
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, correction]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# MACD zero-line cross with swing-point confirmation

## One-line summary
Take a MACD zero-line up-cross only when price also breaks above its prior swing high (higher-high / higher-low structure), outside
congestion; trail the stop under each new swing low instead of exiting on the opposite cross.

## Origin and lineage
MACD = EMA12 - EMA26 (Gerald Appel). The zero-line cross is equivalent to the 12/26 EMA crossover. ChartSchool's article adds a
price-structure filter because, in its words, the zero cross produces "as much noise as signal".

## Exact rules (ChartSchool, description only)
- MACD settings not stated in the article; 12/26/9 assumed (catalog).
- Long: MACD crosses above zero and price confirms with a break above the previous swing high (higher highs and higher lows).
- Avoid entries inside a congestion zone between support and resistance.
- Do not exit on the opposite zero-line cross (it can give back the gain).
- Targets: measured moves (e.g., 100% projection of the congestion range) or S/R levels.
- Trail the stop a little below each new swing low.
- Sizing: none.

## Why it should work
Two independent confirmations of a trend change: a medium-term average crossover and a price-structure break. The counterparty
is supply overhead at the prior swing high; once absorbed, trend followers and breakout buyers enter. Edge is generic
momentum/breakout.

## When it works and when it fails
Works at the start of new uptrends after a base. Fails in ranges (MACD hugs zero; swing breaks are false) and in V-shaped
reversals where the confirming swing high is far above.

## Parameters and sensitivity
MACD lengths (12/26 standard), swing-point pivot width (3-5 bars each side), max bars between zero cross and swing break (0-10),
congestion definition. Pivot width matters most: wider pivots = fewer, later signals.

## Evidence
- ChartSchool: discretionary framework, no statistics.
- Chong and Ng, "Technical analysis and the London stock exchange: testing the MACD and RSI rules using the FT30", Applied
  Economics Letters 15(14), 2008: on 60 years of FT30 index data, MACD (and RSI) rules beat buy-and-hold in most cases. That tests
  plain MACD rules on an index, not this filtered swing setup.
- MACD crossover rules on individual US stocks after costs have generally weak published evidence; no independent test of this
  combined setup found. Grade D.

## Common mistakes
Using unconfirmed swing points (a pivot needs `width` bars after it; using it earlier is look-ahead); exiting on the opposite
zero cross; trading crosses inside congestion.

## Discretionary parts and how to make them mechanical
- Swing high/low: the existing `features/levels.py` pivot logic (pivot width 5), confirmed only `width` bars after the pivot bar.
- Confirmation: close_t > most recent confirmed swing high, and the most recent confirmed swing low > the one before it.
- Window: MACD zero up-cross within the last 10 bars (inclusive of t).
- Congestion: require `level_break` == 1 (close above the prior nearest pivot resistance), i.e. price has left the zone
  between support_1 and resistance_1.
- Measured-move target: entry + (swing high - swing low of the base).

## Implementation spec for swing-engine
- Module `strategies/macd_zero_swing.py`, registered `macd_zero_swing`, disabled.
- Features: reuse `macd`, `level_break`, `support_1`, `resistance_1`; add `macd_prev`, `bars_since_macd_zero_up`,
  `last_swing_high`, `last_swing_low`, `prev_swing_low` (confirmed pivots from levels.pivot_highs/lows shifted by width).
- Signal on close t: bars_since_macd_zero_up <= 10; close_t > last_swing_high; last_swing_low > prev_swing_low;
  level_break == 1.
- Entry next open. Stop: last_swing_low - 0.1*atr_14.
- Target: measured move entry + (last_swing_high - last_swing_low); reject if reward_risk < min_reward_risk (default 2.0).
- Trailing: stop to each new confirmed swing low; engine lacks a "stop follows column" hook, so approximate with the global
  lowest-low trail (`trail_lookback_days` 10) or add the hook.
- max_hold_days: 40.
- Missing: confirmed swing-point columns, column-following stop hook.

## What the router should know
Breakout-like trend initiation. Treat with the breakout family: healthy_uptrend only, needs breadth confirmation.

## Signs of decay to monitor
False-break rate (stopped within 3 bars) above 50%; MACD crosses clustering inside congestion.

## Sources
- https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/macd-zero-line-crosses-with-swing-points
- https://ideas.repec.org/a/taf/apeclt/v15y2008i14p1111-1114.html

## Empirical (replay)
_Pending: filled in from swing replay on real data._
