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
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1 | 0 | 0% | -1.44 | -1.46 | 0% | -1.44 | -1.46 | 0% | -1.44 | -1.46 | 0.00 |
| healthy_uptrend | 1 | 0 | 100% | +0.17 | +0.13 | 0% | -0.92 | -0.96 | 0% | -0.92 | -0.96 | 0.00 |
| high_vol_selloff | 1 | 0 | 0% | -0.01 | -0.19 | 100% | +0.71 | +0.52 | 100% | +1.72 | +1.54 | inf |
| narrow_uptrend | 1 | 0 | 0% | -0.83 | -0.85 | 0% | -0.83 | -0.85 | 0% | -0.83 | -0.85 | 0.00 |
| **all** | 4 | 0 | 25% | -0.53 | -0.59 | 25% | -0.62 | -0.68 | 25% | -0.37 | -0.43 | 0.54 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 7 | 0 | 57% | +0.10 | -0.10 | 43% | +0.23 | +0.04 | 29% | +0.00 | -0.19 | 1.00 |
| correction | 6 | 0 | 83% | +0.18 | +0.07 | 33% | +0.41 | +0.30 | 83% | +1.05 | +0.94 | 10.57 |
| healthy_uptrend | 11 | 0 | 36% | -0.44 | -0.59 | 27% | -0.56 | -0.72 | 18% | -0.76 | -0.92 | 0.22 |
| high_vol_selloff | 4 | 0 | 25% | +0.26 | +0.13 | 75% | +0.88 | +0.75 | 50% | +0.94 | +0.81 | 3.05 |
| narrow_uptrend | 7 | 0 | 14% | -0.59 | -0.75 | 0% | -0.69 | -0.86 | 0% | -0.77 | -0.94 | 0.00 |
| **all** | 35 | 0 | 43% | -0.18 | -0.33 | 31% | -0.10 | -0.25 | 31% | -0.11 | -0.26 | 0.84 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
