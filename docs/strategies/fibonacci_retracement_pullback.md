---
slug: fibonacci_retracement_pullback
name: Fibonacci retracement pullback (Webull, ChartSchool, Dow/Hamilton 1/3-2/3)
originators: [Practitioner standard (StockCharts ChartSchool), William P. Hamilton (Dow theory), Webull Learn]
category: pattern
decision: implement_disabled_for_comparison
holding_period_days: [3, 20]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Fibonacci retracement pullback

## One-line summary
In an uptrend, buy a confirmed reversal inside the 38.2-61.8% retracement of the last impulse, stop beyond the
61.8-78.6% level or swing low; test against a 50%-only (Dow/Hamilton) control.

## Origin and lineage
Hamilton's Dow-theory observation: secondary moves retrace 1/3 to 2/3 of the primary move, typically about half.
Fibonacci levels (23.6/38.2/50/61.8/78.6%) are the modern practitioner standard (ChartSchool); Webull Learn's swing
course gives a stochastic/MACD-confirmed version.

## Exact rules
- Levels: `L_r = swing_high - r x (swing_high - swing_low)` for r in {0.236, 0.382, 0.5, 0.618, 0.786}.
- ChartSchool: levels are alert zones, not signals. Buy only on confirmation (reversal candle, oscillator turn,
  MA reclaim) inside the 38.2-61.8% zone of a prior impulse in an uptrend; stop beyond 61.8-78.6% or the swing low.
- Webull: enter on a stochastic or MACD bullish crossover as price clears a Fib level (add on the next level);
  stop at the prior low; its example takes profit at the 50% retracement of the preceding decline (that example
  is a bounce in a downswing, not a trend pullback).
- Targets as taught: prior swing high (retest) or level-based; no time exit or sizing given.

## Why it should work
The mechanism, if any, is the pullback-in-trend edge (short-term reversal inside medium-term momentum, see
docs/methods/01), not the ratios. Fibonacci levels may act as self-fulfilling order clusters because many traders
watch them; no evidence was verified that they beat arbitrary levels.

## When it works and when it fails
Works in orderly uptrends with a clear impulse. Fails when the "impulse" is noise (ill-defined swing), and in
corrections where retracements extend past 78.6%.

## Parameters and sensitivity
| Knob | Range | Trap |
|---|---|---|
| impulse definition | swing low -> swing high with move >= 3 x atr_14 (or >= 10%) | biggest source of variance |
| entry zone | 0.382-0.618 | |
| confirmation | close > prior high / RSI(14) turn / close > ema_9 | pick one before replay |
| stop | below 0.786 level or swing low | |
| control | 50%-only zone 0.45-0.55, or random levels | mandatory to show Fib adds anything |

## Evidence
No peer-reviewed evidence that Fibonacci ratios beat arbitrary levels was verified (catalog grade D). Webull and
ChartSchool material is illustrative.

## Common mistakes
Anchoring swings after the fact; buying a level without confirmation; retrofitting whichever level held.

## Discretionary parts and how to make them mechanical
Swing low/high from confirmed pivots (levels.py width 5): impulse = last confirmed pivot low to the highest high
after it, confirmed when a pivot high prints. Confirmation = `close_t > high_{t-1}` with `low` inside the zone in the
last 3 bars.

## Implementation spec for swing-engine
- Reuse: `pivot_highs`/`pivot_lows` (features/levels.py), `trend_state`, `atr_14`, `ema_9`, `rsi_14`.
- Missing: `swing_point_labeling` helper giving `impulse_low`, `impulse_high` as of t-1; `retr_pct =
  (impulse_high - low_t) / (impulse_high - impulse_low)`.
- Long on bar t: `trend_state == 1`; impulse size `>= 3 x atr_14`; `min(low over last 3 bars)` has `retr_pct` in
  [0.382, 0.618]; no close below the 0.786 level since the impulse high; trigger `close_t > high_{t-1}`. Entry next
  open. Stop = min(level_0.786, lowest low since impulse high) - 0.1 x atr_14. Target = impulse_high.
  `max_hold_days = 15`. `min_reward_risk = 1.5`.
- Control variant `fib_control_50`: same with zone [0.45, 0.55]; and an "any pullback" variant with no zone.
- Overlaps `pullback_trend` / `pullback_holy_grail`; correlate signals before allocating.

## What the router should know
Pullback family; same regimes as `pullback_holy_grail`. Only worth enabling if it beats both controls after costs.

## Signs of decay to monitor
Edge vs the 50%-only control shrinking to zero; stop-outs through 0.786 rising.

## Sources
- https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-annotation-tools/fibonacci-retracements
- https://chartschool.stockcharts.com/table-of-contents/market-analysis/dow-theory
- https://www.webullapp.com/learn/courseware/2Upopx/How-to-Apply-Fibonacci-Retracement-in-Trading?courseId=553Fb2

## Empirical (replay)
_Pending: filled in from swing replay on real data._
