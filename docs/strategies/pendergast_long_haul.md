---
slug: pendergast_long_haul
name: Long Haul (Donald Pendergast Jr.)
originators: [Donald Pendergast Jr. (S&C 2014 Bonus Issue), thinkorswim built-in strategy + Long Haul Filter]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [5, 40]     # estimate ("weeks" per catalog)
timeframe: daily
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [correction, high_vol_selloff, choppy]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Long Haul (Pendergast)

## One-line summary
Long-only "dip then breakout": after RSI has been oversold without reaching overbought, buy the bar that closes above
several prior highs and above the slow MA; exit on a close below the fast MA or a 3-bar-low trailing stop.

## Origin and lineage
Donald Pendergast Jr., S&C 2014 Bonus Issue. thinkorswim ships the strategy and a Long Haul Filter (Stock Hacker scan)
implementing his stock-selection criteria. The filter's criteria are not documented on the TOS page (unverified).

## Exact rules (TOS documentation; defaults not published)
- Setup: RSI(len) fell below the oversold level and has not since risen above the overbought level.
- Entry: the bar closes above the highest high of the prior `high length` bars and above the slow MA. Next-open fill.
- Exit 1: close below the fast MA. Exit 2 (trailing): price drops below the lowest low of the last 3 bars.
- Inputs: fast length, slow length (slow >> fast), MA type, RSI length, oversold, overbought, RSI average type, high length.
  **No default values are published** (checked TOS page 2026-10-07). Catalog formula status: approximation.

## Why it should work
Buying the resumption of an uptrend after a washout: weak holders have sold at the oversold low, and the breakout above
recent highs shows demand has returned. The other side: sellers who bought the prior high and exit at breakeven.

## When it works and when it fails
Pullbacks within long-term uptrends. Fails when the oversold reading marks the start of a downtrend (slow MA filter only
partly guards against this) and in chop where the 3-bar-low stop is hit within days.

## Parameters and sensitivity
Engine assumptions (not from the source): RSI(14) oversold 30 / overbought 70, high length 5, fast MA SMA(10), slow MA
SMA(50). Each is a guess; replay a small grid (RSI os 25-35, high length 3-10) and report all of it, not the best cell.

## Evidence
In-sample S&C illustration only (grade D). No independent test found.

## Common mistakes
Requiring RSI to still be oversold at entry (it is the history since the last oversold that matters); letting the
setup age indefinitely.

## Discretionary parts and how to make them mechanical
Stock selection -> trend_state = 1 and the universe filter. Setup age -> cap at 30 bars since the oversold reading.

## Implementation spec for swing-engine
- Module `strategies/long_haul.py`, `@register("strategy")`.
- Reuses rsi_14, sma_10, sma_50, atr_14, trend_state. Compute in-module: bars_since_oversold, max RSI since then,
  prior_max_high_n (RollingSpec(high, max, n, prior=True)), lowest_low_3.
- Signal at close t: bars_since(rsi_14 < 30) <= 30, max(rsi_14 since then) < 70, close > prior_max_high_5, close > sma_50.
- Stop: lowest low of last 3 bars (must be < entry; else entry - 1.5 x atr_14). Target: None.
  Trailing: ratchet stop to lowest_low_3 each close. `should_exit`: close < sma_10.
- `max_hold_days`: 40. `min_reward_risk`: not applied.
- settings.yaml: `long_haul: {enabled: false, shadow_only: true}` with the assumed params listed explicitly.

## What the router should know
Close cousin of `pullback_trend` and `rsi2_meanrev` (dip in uptrend) but enters on strength; compare overlap in replay.

## Signs of decay to monitor
Median holding under 5 days (stop too tight for current volatility); win rate below 35%.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/L-P/LongHaul

## Empirical (replay)
_Pending: filled in from swing replay on real data._
