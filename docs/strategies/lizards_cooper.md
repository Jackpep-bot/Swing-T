---
slug: lizards_cooper
name: Lizards (new 10-day low with long lower tail; Jeff Cooper)
originators: [Jeff Cooper]
category: pattern
decision: implement_disabled_for_comparison
holding_period_days: [1, 5]
timeframe: daily
direction: long   # bearish mirror on 10-day highs; engine is long-only
regimes_good: [choppy, narrow_uptrend, healthy_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Lizards

## One-line summary
A new 10-day low that opens and closes in the top quarter of its range (a long lower tail, like a hammer) shows the
low was rejected; buy above its high the next day.

## Origin and lineage
Jeff Cooper, *Hit and Run Trading* (ch. 14). Close cousin of the hammer candle and of Turtle Soup (undercut and reject).

## Exact rules (long)
- Lizard bar: `low_t` is the lowest low of the last 10 bars (including t), and both open and close are in the top 25%
  of the bar's range.
- Entry: next day, buy stop above the lizard high (aggressive: buy the open).
- Stop: below the lizard low. Exit: 1-5 days (no fixed rule beyond author examples).

## Why it should work
Sellers pushed to a fresh short-term low and were fully absorbed within the session; the next-day break of the high
confirms buyers kept control.

## When it works and when it fails
Pullbacks and ranges in liquid names. Fails in steady downtrends where every bounce is sold, and on illiquid names
where tails are noise.

## Parameters and sensitivity
Lookback 10, the 25% thresholds, entry style (stop vs open). Few knobs; test only the two entry styles.

## Evidence
Author examples only; no independent test located (catalog C23, single secondary source).

## Common mistakes
Counting a bar with a tiny range (ratios are meaningless); ignoring the higher-timeframe trend.

## Discretionary parts and how to make them mechanical
Minimum range: `(high_t - low_t) >= 0.75 * atr_14_{t-1}` (engine choice, labelled).

## Implementation spec for swing-engine
- Reuses: OHLC, `close_pos`, `atr_14`, `trend_state`.
- New features: `open_pos = (open - low) / (high - low)`; `is_low_10 = low_t == min(low[t-9..t])`.
- Setup at close t: `is_low_10` and `open_pos >= 0.75` and `close_pos >= 0.75`.
- Entry (book): buy stop `high_t + 0.01` on t+1 only (needs stop-entry hook). Aggressive variant: next open (works with
  the current backtester as-is).
- Stop: `low_t - 0.01`. Target: none; `min_reward_risk: 0.0`; `max_hold_days: 5`.

## What the router should know
Mean-reversion bar pattern; overlaps `turtle_soup`, `key_reversal_day`, `sr_bounce`. Avoid correction regimes.

## Signs of decay to monitor
Lizard lows broken within 2 bars > 50% of fills; average 5-day R <= 0.

## Sources
- https://www.money.it/Il-segnale-di-trading-lizard-di

## Empirical (replay)
_Pending: filled in from swing replay on real data._
