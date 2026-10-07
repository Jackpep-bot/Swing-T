---
slug: harmonic_gartley
name: Harmonic patterns (Gartley only; Carney ratios)
originators: [H.M. Gartley, Scott Carney]
category: pattern
decision: implement_disabled_for_comparison
holding_period_days: [3, 30]
timeframe: daily
direction: both
regimes_good: [narrow_uptrend, choppy]
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: none
free_data_ok: true
status: not_built
---

# Harmonic Gartley

## One-line summary
Five-point XABCD swing pattern whose legs match Fibonacci ratios; buy at the D completion zone with a stop just
beyond D. Only the Gartley is implemented because only its ratios are available from a free source.

## Origin and lineage
H.M. Gartley, *Profits in the Stock Market* (1935) described the swing shape; Scott Carney (*Harmonic Trading*
vols. 1-2) added the Fibonacci ratio tables and the "Pattern Completion/Potential Reversal Zone". The free source
used here is StockCharts ChartSchool. Bat, Butterfly, Crab, Shark and Cypher ratio matrices are in Carney's books
and not reproduced, so they stay out.

## Exact rules (bullish Gartley, ChartSchool restatement)
- Swings: X (low) -> A (high) -> B (low) -> C (high) -> D (low).
- Pattern Completion Zone (PCZ) built from: D near the 0.786 retracement of XA; CD = 1.27-1.618 x BC; AB = CD
  (equal legs). (ChartSchool labels the 0.78 level "B retracement" in one place and the PCZ in another; the catalog
  reads it as D at 0.786 XA, which matches Carney's Gartley.) The B-point retracement of XA commonly taught as 0.618
  is not stated on the ChartSchool page and is unverified here.
- Entry: inside the PCZ at D; ChartSchool prefers confirmation of a reversal (price action + trend change) to a
  blind limit order.
- Stop: below D (bullish).
- Targets: zone 1 = D + 0.618 to 0.786 x XA; zone 2 = D + 1.27 to 1.618 x XA.
- Trailing/time exit and sizing: not specified.

## Why it should work
No established mechanism. Plausible story: D sits at a deep retracement of a prior impulse where value buyers and
short covers meet; confluence of several projections defines a small, cheap-to-risk zone. Fibonacci ratios
themselves have no demonstrated special status (see fibonacci_retracement_pullback).

## When it works and when it fails
Range-bound or gently trending names with clean swings; fails in strong trends (D gets run through) and gap-heavy names.

## Parameters and sensitivity
Ratio tolerance (+/- 3-5% around each ratio), zigzag swing threshold (e.g. 1.5-3 x atr_14 or pivot width 5),
max pattern length (20-120 bars). Trap: tolerance creep - loosen enough and every swing is "harmonic".

## Evidence
No robust independent evidence (catalog grade "none"; ChartSchool itself says targets are probabilistic and
patterns can fail). No peer-reviewed study verified.

## Common mistakes
Selecting X after the fact; drawing patterns with unconfirmed D; ignoring the trend context.

## Discretionary parts and how to make them mechanical
Swing points from a causal zigzag (pivot width w, confirmed after w bars). Ratios tested with fixed tolerance.
"Confirmation" = close above the high of the bar that made D (low within PCZ), within 3 bars.

## Implementation spec for swing-engine
- Reuse: `pivot_highs`/`pivot_lows` (features/levels.py), `atr_14`.
- Missing: `swing_point_labeling` (alternating zigzag sequence) and a harmonic matcher returning X, A, B, C, D prices.
- Bullish Gartley on bar t: last confirmed alternating lows/highs X<A>B<C>D; `(A - D) / (A - X)` in
  [0.786 - tol, 0.786 + tol]; `(C - D) / (C - B)` in [1.27, 1.618]; `|(A - B) - (C - D)| / (A - B) <= tol`;
  D is the lowest low of the last 1-3 bars; trigger `close_t > high(D-bar)`. Entry next open. Stop = D - 0.25 x
  atr_14. Target = D + 0.618 x (A - X). `max_hold_days = 20`. `min_reward_risk = 1.5`. tol = 0.05.
- Note: with D only known after the zigzag confirms it, a causal entry is later than the taught limit entry at D.

## What the router should know
Counter-trend (reversal) entry; do not combine with breakout risk in the same name. Disabled for comparison.

## Signs of decay to monitor
Fraction of trades stopped below D within 3 bars; any edge vanishing when tolerance is tightened.

## Sources
- https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/harmonic-patterns

## Empirical (replay)
_Pending: filled in from swing replay on real data._
