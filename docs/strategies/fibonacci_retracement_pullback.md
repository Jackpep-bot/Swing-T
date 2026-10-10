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
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 136 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 22 | 0 | 55% | +0.09 | +0.03 | 55% | +0.03 | -0.04 | 41% | -0.14 | -0.20 | 0.65 |
| correction | 4 | 0 | 50% | +0.20 | +0.11 | 0% | -0.43 | -0.52 | 0% | -0.96 | -1.06 | 0.00 |
| healthy_uptrend | 106 | 0 | 42% | -0.02 | -0.09 | 49% | -0.01 | -0.08 | 42% | -0.02 | -0.10 | 0.94 |
| high_vol_selloff | 13 | 0 | 54% | -0.05 | -0.11 | 46% | +0.03 | -0.03 | 38% | -0.09 | -0.15 | 0.83 |
| narrow_uptrend | 14 | 0 | 43% | -0.15 | -0.23 | 25% | -0.46 | -0.53 | 18% | -0.39 | -0.46 | 0.32 |
| **all** | 159 | 0 | 45% | -0.01 | -0.08 | 46% | -0.04 | -0.12 | 38% | -0.10 | -0.17 | 0.78 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 51 | 2 | 57% | +0.10 | +0.03 | 51% | +0.12 | +0.04 | 53% | +0.13 | +0.05 | 1.44 |
| correction | 13 | 0 | 62% | +0.11 | +0.05 | 54% | +0.02 | -0.04 | 54% | +0.12 | +0.06 | 1.43 |
| healthy_uptrend | 239 | 0 | 46% | -0.04 | -0.11 | 37% | -0.05 | -0.13 | 40% | -0.07 | -0.15 | 0.82 |
| high_vol_selloff | 22 | 0 | 50% | -0.01 | -0.09 | 55% | +0.21 | +0.13 | 64% | +0.28 | +0.20 | 2.30 |
| narrow_uptrend | 57 | 0 | 44% | -0.13 | -0.20 | 32% | -0.21 | -0.27 | 39% | -0.26 | -0.33 | 0.47 |
| **all** | 382 | 2 | 48% | -0.03 | -0.10 | 40% | -0.04 | -0.11 | 43% | -0.05 | -0.12 | 0.88 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
