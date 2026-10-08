---
slug: pivot_extension_reversal
name: Pivot Extension reversal (TradeStation, TradingView)
originators: [TradeStation built-in, TradingView built-in]
category: pattern
decision: implement_disabled_for_comparison
holding_period_days: [2, 20]
timeframe: daily
direction: both
regimes_good: [choppy, narrow_uptrend]
regimes_bad: [high_vol_selloff, correction]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: none
free_data_ok: true
status: not_built
---

# Pivot Extension reversal

## One-line summary
Buy the bar after a confirmed swing low (4 higher lows to the left, 2 to the right); a counter-trend demo strategy
kept as a comparison baseline for swing-low entries.

## Origin and lineage
TradeStation "Pivot Extension LE/SE" (and siblings Pivot Reversal LE: buy stop at a confirmed 4/4 pivot high;
New High LE: buy stop above the period high) and TradingView's "Pivot Extension Strategy" (left 4 / right 2,
recalled, not verified). Vendor demonstrations; no originator.

## Exact rules (TradeStation Pivot Extension LE)
- Inputs: Price = Low, LeftStrength = 4, RightStrength = 2.
- Pivot low: a bar whose low is preceded by 4 bars with higher lows and followed by 2 bars with higher lows.
- Entry: long order for the next bar after the pivot is identified (i.e. 2 bars after the pivot bar itself),
  order name "PivLo". SE mirrors on pivot highs.
- No stop, target or time exit in the script; sizing unspecified.

## Why it should work
Weak: a confirmed local low means short-term selling has paused; this is short-term reversal at the swing level.
Counterparty: late sellers. Without a trend filter it buys every local low, including in downtrends.

## When it works and when it fails
Plausible in ranges and in pullbacks inside uptrends; fails in downtrends where each pivot low is followed by a
lower one.

## Parameters and sensitivity
Left 3-5, right 1-3 (right strength = confirmation delay = entry lag). Trap: optimizing left/right per symbol.

## Evidence
None published (catalog grade "none").

## Common mistakes
Using an unconfirmed pivot (look-ahead: the right-side bars must exist before the signal); no trend filter.

## Discretionary parts and how to make them mechanical
Fully mechanical; add a trend filter as a separate, logged variant.

## Implementation spec for swing-engine
- Reuse: `pivot_lows` in features/levels.py, which is symmetric (`width` bars both sides, confirmed after `width`
  bars). The TradeStation rule is asymmetric (4 left, 2 right) and uses strict "higher" lows, so add
  `pivot_lows_asym(low, left=4, right=2)` confirmed at i + right.
- Long on bar t: a pivot low at i = t - 2 is confirmed on t (lows of t-1 and t both > low_i; lows of i-4..i-1 > low_i).
  Entry next open. Stop = low_i - 0.1 x atr_14. Target = entry + 2R, or the most recent confirmed pivot high if
  closer and >= 1.5R. `max_hold_days = 10`. `min_reward_risk = 1.5`.
- Variants: (a) raw (no filter, the vendor rule); (b) `trend_state == 1` only (pullback-low entry).
- Pivot Reversal LE (buy stop at a 4/4 pivot high) needs a stop-entry order hook; approximate with close > pivot
  high, which is close to `sr_breakout`; not built here.

## What the router should know
Counter-trend baseline; allow only the trend-filtered variant if anything. Disabled for comparison.

## Signs of decay to monitor
Stop-out within 3 bars rising; raw variant matching or beating the filtered one (means the filter adds nothing).

## Sources
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/pivot_extension_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/pivot_extension_se_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/pivot_reversal_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/new_high_le_signal_.htm
- https://www.tradingview.com/support/folders/43000587406-built-in-strategies/

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 11976 | 308 | 46% | +0.04 | -0.03 | 43% | +0.05 | -0.02 | 41% | +0.08 | +0.00 | 1.14 |
| correction | 1740 | 40 | 43% | -0.18 | -0.24 | 49% | +0.08 | +0.02 | 48% | +0.14 | +0.08 | 1.25 |
| healthy_uptrend | 40036 | 885 | 44% | -0.01 | -0.09 | 40% | -0.03 | -0.10 | 38% | -0.01 | -0.09 | 0.98 |
| high_vol_selloff | 8142 | 282 | 54% | +0.17 | +0.11 | 54% | +0.25 | +0.19 | 47% | +0.25 | +0.19 | 1.52 |
| narrow_uptrend | 4874 | 117 | 33% | -0.18 | -0.27 | 29% | -0.25 | -0.34 | 28% | -0.21 | -0.30 | 0.70 |
| **all** | 66768 | 1632 | 45% | +0.00 | -0.07 | 42% | +0.01 | -0.07 | 39% | +0.03 | -0.05 | 1.04 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 41037 | 885 | 48% | +0.08 | +0.01 | 46% | +0.12 | +0.06 | 44% | +0.16 | +0.09 | 1.30 |
| correction | 26084 | 511 | 55% | +0.21 | +0.15 | 52% | +0.24 | +0.18 | 49% | +0.26 | +0.21 | 1.51 |
| healthy_uptrend | 111522 | 1948 | 44% | -0.01 | -0.09 | 42% | +0.00 | -0.07 | 39% | +0.01 | -0.07 | 1.02 |
| high_vol_selloff | 44681 | 1225 | 48% | +0.02 | -0.03 | 47% | +0.07 | +0.02 | 44% | +0.10 | +0.04 | 1.18 |
| narrow_uptrend | 30065 | 620 | 49% | +0.09 | +0.01 | 45% | +0.08 | +0.01 | 42% | +0.10 | +0.03 | 1.18 |
| **all** | 253389 | 5189 | 47% | +0.04 | -0.03 | 45% | +0.07 | -0.00 | 42% | +0.09 | +0.02 | 1.15 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
