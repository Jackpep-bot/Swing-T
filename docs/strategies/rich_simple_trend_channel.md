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
_Pending: filled in from swing replay on real data._
