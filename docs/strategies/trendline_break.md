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
_Pending: filled in from swing replay on real data._
