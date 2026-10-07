---
slug: rsi_divergence
name: RSI regular / hidden divergence (TradingView)
originators: [J. Welles Wilder (RSI, 1978); divergence usage is folklore; TradingView built-in indicator]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [3, 20]
timeframe: daily
direction: long   # regular bullish (reversal) and hidden bullish (continuation); bearish types are exits only
regimes_good: [choppy, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# RSI divergence

## One-line summary
Price makes a lower low while RSI(14) makes a higher low (regular bullish), or price makes a higher low while RSI makes
a lower low (hidden bullish); signals confirm only 5 bars after the pivot, and there is no published validation.

## Origin and lineage
RSI is Wilder's (1978). Divergence reading is long-standing chart lore; the catalogued definition is TradingView's
built-in "RSI Divergence Indicator". Formula status "approximation" (the built-in's exact pivot pairing was not
re-checked).

## Exact rules (TradingView built-in)
- RSI(14). Pivots on RSI with left/right lookback 5/5. Two pivots must be 5-60 bars apart.
- Regular bullish: price lower low + RSI higher low. Regular bearish: price higher high + RSI lower high.
- Hidden bullish: price higher low + RSI lower low (continuation). Hidden bearish: price lower high + RSI higher high.
- Signal confirmed only after the 5 right-side bars: a built-in 5-bar lag.
- No entry, stop, target or sizing rules are part of the indicator.

## Why it should work
Momentum fading while price extends suggests the move is running out of participation. The lag means much of any
reversal is already over by confirmation.

## When it works and when it fails
Ranges and pullbacks. Fails in strong trends: divergence can repeat several times while price keeps going.

## Parameters and sensitivity
RSI length, pivot left/right (5/5), pivot spacing (5-60), whether RSI must be below 30 at the low. Every knob is
tunable and the LuxAlgo "out-of-sample optimizer" exists precisely because results swing with them: high overfit risk.

## Evidence
- No published validation for equities.
- Backtrex DAX test (4-hour bars, RSI 14, divergence within last 10 candles, price in lower half of a 100-bar range,
  1.5% stop / 3% target, 0.02% commission per side), Oct 2016 - Oct 2026: 106 trades, 38.7% wins, PF 1.16, +16.5% vs
  +136.4% buy-and-hold; most of the gain came in 2018. Different market and timeframe, but the only concrete test found.

## Common mistakes
Using unconfirmed pivots (repainting / look-ahead); counting divergence in a downtrend as a buy; ignoring the lag.

## Discretionary parts and how to make them mechanical
Use only confirmed pivots (bar i is a pivot low when its value is the min of bars i-5..i+5, known at i+5). Pair the
latest confirmed RSI pivot low with the previous one 5-60 bars earlier; compare the price lows at the same bars.

## Implementation spec for swing-engine
- Reuses: `rsi_14`, OHLC, `atr_14`, `trend_state`; `features/levels.py pivot_lows()` already implements the centred
  pivot with confirmation at `width` bars (width 5 matches), and is the base for the catalog's `swing_point_labeling`.
- New features: `rsi_pivot_low` (pivot of `rsi_14`), `price_at_pivot` (low at that bar), `bull_div_regular`,
  `bull_div_hidden` (0/1 on the confirmation bar i+5), `div_pivot_low` (the price low of the latest pivot).
- Signal at close of confirmation bar t: regular bullish (variant A, require `rsi_14 at pivot < 35`) or hidden bullish
  with `trend_state == 1` (variant B).
- Entry: next open. Stop: `div_pivot_low - 0.5 * atr_14`. Target: comparison variant `resistance_1` with
  `min_reward_risk: 2.0`; else time exit. `max_hold_days: 20`.
- No-look-ahead check: the shift test must show the flag only appears at i+5.

## What the router should know
Regular bullish = mean reversion (choppy only); hidden bullish = trend continuation (uptrend regimes). Treat as two
strategies for routing. Overlaps `sr_bounce` (pivot support).

## Signs of decay to monitor
Win rate on 2R targets below 33% (breakeven); PF < 1.1 over 50+ trades.

## Sources
- https://www.luxalgo.com/library/indicator/RRp1xOWb-rsi-divergence/
- https://www.luxalgo.com/library/indicator/rsi-divergence-out-of-sample-optimizer/
- https://backtrex.com/en/backtests/rsi-divergence-dax

## Empirical (replay)
_Pending: filled in from swing replay on real data._
