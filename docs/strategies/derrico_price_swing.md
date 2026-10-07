---
slug: derrico_price_swing
name: "Price Swing detector entries (Domenico D'Errico)"
originators: ["Domenico D'Errico (S&C, May 2017)", "thinkorswim PriceSwing"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [1, 20]
timeframe: daily
direction: long (original also shorts downswings; engine long-only)
regimes_good: [choppy, healthy_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Price Swing detector (D'Errico)

## One-line summary
Four interchangeable definitions of an "upswing" (pivot low, close back above the lower Bollinger Band, RSI back
above 40, or higher low while RSI is oversold); buy each upswing and exit after a fixed 20 bars.

## Origin and lineage
Domenico D'Errico, S&C May 2017 (per catalog; article not read); coded by thinkorswim as PriceSwing (catalog B22).
It is a detector library more than a strategy: the fixed time exit is a way to compare detectors.

## Exact rules (thinkorswim)
- Swing type 1, Pivot High-Low: upswing when the low first falls below the previous low and then rises (low[t] >
  low[t-1] after low[t-1] < low[t-2]).
- Type 2, Bollinger crossover: close crosses above the lower band (downswing: below the upper band).
- Type 3, RSI crossover: RSI crosses above oversold 40 (downswing: below overbought 60).
- Type 4, RSI + higher low: low > previous low while RSI below oversold (downswing: lower high while RSI above
  overbought).
- Buy on every upswing; short on every downswing; exit after 20 bars (default). No price stop. RSI length and BB
  length/width defaults: unverified (tos text truncated); this card assumes RSI(14) and BB(20, 2).

## Why it should work
Each detector marks the end of a short down-swing; buying the turn captures short-term reversal. The fixed 20-bar exit
makes it a test of drift after the turn rather than a managed trade.

## When it works and when it fails
Works in ranges and in uptrends with shallow dips. Fails in persistent downtrends: every minor bounce is an "upswing";
type 1 fires very often (most days in a choppy tape), so it is mainly a baseline.

## Parameters and sensitivity
Swing type (4 variants), RSI levels 40/60 (loose; 30/70 is classic), BB length/width, hold bars 5-20. Trap: picking the
best of four detectors in-sample and reporting it as the edge; count all four as trials (deflated Sharpe).

## Evidence
D'Errico's in-sample illustration only; no broker statistics; no independent test found. Grade D.

## Common mistakes
Using type 1 without any trend filter (signal flood); no stop on a 20-bar hold.

## Discretionary parts and how to make them mechanical
Fully mechanical; add `trend_state >= 0` gate and an ATR stop as engine choices.

## Implementation spec for swing-engine
- Variants as `swing_type` param:
  1. `low[t] > low[t-1] and low[t-1] < low[t-2]` (uses `prior_low` from `rows_as_of` plus one more lag).
  2. `close[t] > bb_lower_20[t] and close[t-1] <= bb_lower_20[t-1]`.
  3. `rsi_14[t] > 40 and rsi_14[t-1] <= 40`.
  4. `low[t] > low[t-1] and rsi_14[t] < 40`.
- Entry next open. Stop `entry - 2*atr_14` (engine choice). Target none; `min_reward_risk` 0. `max_hold_days` 20
  (time exit, as original). Optional gate `trend_state >= 0`.
- Reuses `bb_lower_20`, `rsi_14`, `atr_14`, `trend_state`. Nothing missing for the long side.

## What the router should know
Mean-reversion / swing-turn baseline. Type 2 overlaps `bb_bullish_engulfing_kosinski` and `zscore_mean_reversion_garner`;
type 3 overlaps `rsi2_meanrev`. Low priority; use as a benchmark for other turn detectors.

## Signs of decay to monitor
20-bar forward return after signals indistinguishable from unconditional 20-bar return of the universe.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/L-P/PriceSwing

## Empirical (replay)
_Pending: filled in from swing replay on real data._
