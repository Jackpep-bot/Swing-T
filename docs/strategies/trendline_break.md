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
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 113 | 2 | 47% | -0.04 | -0.23 | 44% | +0.02 | -0.17 | 46% | +0.07 | -0.12 | 1.16 |
| correction | 13 | 0 | 38% | -0.19 | -0.46 | 46% | -0.07 | -0.33 | 38% | +0.08 | -0.19 | 1.15 |
| healthy_uptrend | 587 | 1 | 44% | -0.02 | -0.14 | 46% | +0.00 | -0.12 | 44% | +0.08 | -0.04 | 1.18 |
| high_vol_selloff | 84 | 0 | 61% | +0.22 | +0.07 | 54% | +0.25 | +0.11 | 39% | +0.03 | -0.11 | 1.05 |
| narrow_uptrend | 72 | 1 | 38% | -0.13 | -0.27 | 36% | -0.23 | -0.38 | 23% | -0.41 | -0.58 | 0.42 |
| **all** | 869 | 4 | 46% | -0.01 | -0.15 | 46% | +0.01 | -0.13 | 42% | +0.05 | -0.09 | 1.10 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 414 | 2 | 52% | +0.09 | -0.02 | 51% | +0.14 | +0.03 | 47% | +0.18 | +0.07 | 1.39 |
| correction | 259 | 2 | 49% | +0.04 | -0.08 | 42% | -0.02 | -0.14 | 42% | +0.04 | -0.08 | 1.08 |
| healthy_uptrend | 1587 | 4 | 47% | -0.02 | -0.13 | 47% | -0.01 | -0.11 | 44% | -0.00 | -0.11 | 0.99 |
| high_vol_selloff | 434 | 3 | 48% | +0.06 | -0.06 | 49% | +0.12 | -0.01 | 51% | +0.24 | +0.12 | 1.55 |
| narrow_uptrend | 378 | 1 | 52% | +0.08 | -0.04 | 51% | +0.10 | -0.03 | 48% | +0.13 | +0.00 | 1.30 |
| **all** | 3072 | 12 | 49% | +0.03 | -0.09 | 48% | +0.04 | -0.07 | 46% | +0.08 | -0.04 | 1.16 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
