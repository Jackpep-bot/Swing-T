---
slug: calhoun_adx_breakout
name: ADX Breakouts (Ken Calhoun)
originators: [Ken Calhoun]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [2, 20]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# ADX Breakouts (Calhoun)

## One-line summary
When ADX crosses above 40 while price is at its 15-day high, record that bar's high and buy on a stop a fixed offset
above it.

## Origin and lineage
Ken Calhoun, "ADX Breakouts", *Technical Analysis of Stocks & Commodities*, March 2016. thinkorswim ships
`ADXBreakoutsFilter` (scan) and `ADXBreakoutsLE` (entry only; e.g. pair with `TrailingStopLX` for exits).

## Exact rules (thinkorswim description)
- Universe filter: price between $20 and $70, and 15-day high-low range >= $5 (catalog; 2016 dollar rules).
- Trigger bar: ADX(`adx length`) crosses above `adx level` (40) and the high is the `highest length` (15) bar high.
  ADX length default is not stated on the reference page (Wilder's 14 is assumed; unverified).
- Entry: buy stop at the trigger bar's high + `offset` ($0.50).
- Exits: not part of the entry strategy.

## Why it should work
ADX above 40 marks an established, strong directional move; a new 15-day high confirms the direction is up. Buyers
are momentum followers; sellers are early profit-takers. Caveat: ADX lags and is non-directional; readings of 40+
often occur late in a move, near exhaustion.

## When it works and when it fails
Works in persistent trends. Fails when ADX > 40 marks a climax (ADX turning down soon after) and in sharp
V-reversals where ADX is high from the prior downtrend; requiring `plus_di_14 > minus_di_14` fixes the latter.

## Parameters and sensitivity
- `adx_level` 30-45; `highest_len` 10-20; offset as 0.1-0.25 x `atr_14`.
- Price filter: replace $20-$70 with the engine universe (`min_price` 5, liquidity floors). Range filter: 15-day
  (max high - min low)/close >= 10% instead of $5 (on a $50 stock, $5 = 10%).

## Evidence
Practitioner in-sample illustration (grade D); no broker statistics; no independent test located.

## Common mistakes
Reading ADX as bullish without checking DI direction; using dollar filters on today's price levels.

## Discretionary parts
Exit unspecified; use the engine's stop/trail defaults.

## Implementation spec for swing-engine
- Features: `adx_14`, `plus_di_14`, `minus_di_14` exist in `features/patterns2.py`. New: `adx_cross_40` =
  `adx_14 >= 40` and prior `adx_14 < 40`; `at_high_15` = high >= rolling max(high, 15); `range_15_pct` =
  (max high 15 - min low 15) / close.
- Signal: `adx_cross_40` and `at_high_15` and `plus_di_14 > minus_di_14` and `range_15_pct >= 0.10`.
- Entry: buy stop at trigger high + 0.15 x `atr_14`, valid up to 3 sessions (the tos order stays live until filled;
  3 is an engine choice). Stop = entry - 2 x `atr_14`. Target 2R or trail (engine `trail_after_r`).
  `max_hold_days: 15`; `min_reward_risk: 2.0`.
- Reuses: `adx_14`, DI columns, `atr_14`, `trend_state`.
- Missing: stop-entry order hook with multi-session validity.

## What the router should know
Breakout family; healthy_uptrend only. Comparison control for `breakout_52w` (does an ADX gate add anything?).

## Signs of decay to monitor
Win rate and mean R of fills where ADX turned down within 3 bars vs not.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/A-D/ADXBreakoutsLE
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/A-B/ADXBreakoutsFilter

## Empirical (replay)
_Pending: filled in from swing replay on real data._
