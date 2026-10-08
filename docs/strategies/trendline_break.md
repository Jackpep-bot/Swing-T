---
slug: trendline_break
name: Trendline breakout (TradeStation Trendline LE, Finviz TL signals)
originators: [TradeStation built-in, Finviz (vendor detector)]
category: pattern
decision: implement_disabled_for_comparison
holding_period_days: [3, 20]
timeframe: daily
direction: both
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: none
free_data_ok: true
status: not_built
---

# Trendline break

## One-line summary
Fit a falling resistance line through confirmed swing highs and buy when price closes above it (mirror for
support breaks); the mechanical version of a chartist's trendline breakout.

## Origin and lineage
Classic chartist technique. TradeStation Trendline LE/SE enters when the bar's high penetrates a trendline the user
drew by hand (input `TLRef`, default 1); Finviz auto-detects "TL Resistance / TL Support" through local highs/lows
with an unpublished algorithm and strength metric. IBD teaches trendline breaks inside a handle as an early entry
(docs/methods/07).

## Exact rules
- TradeStation: long when bar high > the referenced trendline's value on that bar (the line is user-drawn; the
  order type is not stated in the help page).
- Finviz: signal list only, no entry/exit rules.
- So no complete originator rule exists: entry/stop/target below are ours and must be logged as trials.

## Why it should work
A descending line through lower highs marks where sellers have been stepping in; a break shows that supply has
been absorbed. Counterparty: sellers anchored to the line and shorts with stops just above it.

## When it works and when it fails
Best as a pullback-end trigger inside a larger uptrend (break of the pullback's down-trendline). Weak in choppy
markets and when the line is fitted through only two arbitrary points.

## Parameters and sensitivity
| Knob | Range | Trap |
|---|---|---|
| pivot width | 3-5 (levels.py default 5) | smaller = more, noisier lines |
| min touches | 2-3 | 3 is stricter, far fewer signals |
| lookback | 20-120 bars | |
| max line-to-price violation | 0-0.5 x atr_14 | |
| break confirmation | close > line, or close > line + 0.25 x atr_14 | |

## Evidence
None for trendline breaks specifically (catalog grade "none"). LMW (2000) show some algorithmically detected
patterns carry incremental information; the Finviz detector itself is untested.

## Common mistakes
Redrawing the line after the fact; using unconfirmed pivots (look-ahead); fitting through the breakout bar.

## Discretionary parts and how to make them mechanical
Line = least-squares or two-point line through the last k confirmed pivot highs (k >= 2), descending slope, no
close above the line between the first pivot and t-1 (tolerance as above).

## Implementation spec for swing-engine
- Reuse: `pivot_highs` / `pivot_lows` (features/levels.py; a pivot at i is only known at i + width), `atr_14`,
  `trend_state`, `rvol_day`.
- Missing: `swing_point_labeling` / trendline helper returning `tl_value_t`, `tl_slope`, `tl_touches` per bar
  using only pivots confirmed by t-1.
- Long: `tl_slope < 0`, `tl_touches >= 2`, `close_{t-1} <= tl_value_{t-1}`, `close_t > tl_value_t`, optional
  `trend_state >= 0` and `rvol_day >= 1.2`. Entry next open. Stop = lowest low since the last touch pivot - 0.25 x
  atr_14. Target = most recent pivot high above entry, else entry + 2R. `max_hold_days = 15`. `min_reward_risk = 2.0`.
- Gap: TradeStation enters intrabar on the high penetrating the line; the engine uses a close trigger + next open.

## What the router should know
Treat as a pullback-family trigger when the higher trend is up; disabled for comparison.

## Signs of decay to monitor
Share of breaks that close back below the line within 3 bars.

## Sources
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/trendline_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/trendline_se_signal_.htm
- https://finviz.com/help/technical-analysis/charts-patterns.ashx
- https://www.nber.org/system/files/working_papers/w7613/w7613.pdf

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 113 | 2 | 47% | -0.04 | -0.08 | 44% | +0.02 | -0.02 | 46% | +0.07 | +0.03 | 1.16 |
| correction | 13 | 0 | 38% | -0.19 | -0.24 | 46% | -0.07 | -0.11 | 38% | +0.08 | +0.03 | 1.15 |
| healthy_uptrend | 588 | 1 | 44% | -0.02 | -0.06 | 46% | +0.00 | -0.04 | 44% | +0.08 | +0.04 | 1.18 |
| high_vol_selloff | 84 | 0 | 61% | +0.22 | +0.17 | 54% | +0.25 | +0.21 | 39% | +0.03 | -0.01 | 1.05 |
| narrow_uptrend | 72 | 1 | 38% | -0.13 | -0.17 | 36% | -0.23 | -0.27 | 23% | -0.41 | -0.45 | 0.42 |
| **all** | 870 | 4 | 46% | -0.01 | -0.05 | 46% | +0.01 | -0.03 | 43% | +0.05 | +0.01 | 1.10 |

Portfolio replay (net of costs, slots shared with its run): 1 trades, win 100%, avg +0.60R, PF inf, P&L $471 on $100k, avg hold 15.0 bars.

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 403 | 2 | 52% | +0.10 | +0.06 | 51% | +0.16 | +0.12 | 46% | +0.17 | +0.13 | 1.36 |
| correction | 260 | 2 | 48% | +0.08 | +0.05 | 42% | +0.04 | +0.01 | 45% | +0.15 | +0.11 | 1.30 |
| healthy_uptrend | 1453 | 3 | 46% | -0.03 | -0.06 | 46% | -0.01 | -0.05 | 44% | -0.01 | -0.05 | 0.98 |
| high_vol_selloff | 395 | 3 | 48% | +0.05 | +0.01 | 48% | +0.12 | +0.09 | 49% | +0.24 | +0.21 | 1.57 |
| narrow_uptrend | 342 | 1 | 51% | +0.06 | +0.02 | 48% | +0.06 | +0.02 | 44% | +0.06 | +0.02 | 1.12 |
| **all** | 2853 | 11 | 48% | +0.02 | -0.02 | 47% | +0.04 | +0.01 | 45% | +0.07 | +0.04 | 1.16 |

Portfolio replay (net of costs, slots shared with its run): 27 trades, win 52%, avg +0.18R, PF 1.35, P&L $2,555 on $100k, avg hold 9.6 bars.
