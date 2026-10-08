---
slug: pivot_reversal_breakout
name: Pivot Reversal breakout (buy stop at the last confirmed swing high)
originators: [TradeStation, TradingView]
category: swing_high_breakout
decision: implement_disabled_for_comparison
holding_period_days: [2, 20]
timeframe: daily
direction: long            # TradingView version is stop-and-reverse; swing-engine strategies are long-only
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, correction]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: none
free_data_ok: true
status: not_built          # features/levels.py has pivots but a different definition
---

# Pivot Reversal breakout

## One-line summary
Once a swing high is confirmed (lower highs on both sides), rest a buy stop at that high; exit at the last confirmed
swing low. A platform demo of "buy the break of the last swing high".

## Origin and lineage
TradeStation built-ins: Pivot Reversal LE/SE, Pivot Extension LE, New High LE. TradingView "Pivot Reversal Strategy".
Swing-high breaks are the mechanical core of Dow-theory trend definitions and of `sr_breakout` in this repo.

## Exact rules
- TradeStation Pivot Reversal LE: when a pivot high with strength 4 (4 lower highs on each side) is confirmed, place a
  buy stop at that pivot high, good until filled.
- TradingView: pivot highs/lows with left 4, right 2 (recalled, not confirmed); buy stop at last pivot high + 1 tick,
  sell stop at last pivot low - 1 tick; stop-and-reverse.
- Pivot Extension LE (related): a pivot low with 4 higher lows left and 2 right -> buy next bar.
- New High LE (related): buy stop 1 tick above the highest high of the day/week/month/year/chart.
- No targets, filters or sizing.

## Why it should work
A break of the most recent swing high is the textbook definition of an uptrend resuming (higher high). Stops of
shorts and breakout buy orders cluster there. The other side is sellers defending the prior high.

## When it works and when it fails
Works in trends with clean swings. Fails in ranges (repeated false breaks of minor highs) and gap-heavy names.

## Parameters and sensitivity
Left/right strength 2-5; recency limit on the pivot (stale pivots far above price). Trap: strength fitted per symbol.

## Evidence
None; broker documentation only.

## Common mistakes
Look-ahead: a pivot with right strength R is only known R bars later. Using unconfirmed pivots inflates backtests.

## Discretionary parts and how to make them mechanical
Fully mechanical once left/right strength and a max pivot age are fixed.

## Implementation spec for swing-engine
- Existing: `features/levels.py` defines pivots with symmetric width 5 (centre bar is the max of 11 bars), confirmed
  only after 5 bars; `resistance_1` is the nearest confirmed pivot high above the prior close within 60 bars, not the
  most recent one. `sr_breakout` buys a close above `resistance_1`.
- New feature: `last_pivot_high_{L}_{R}` = high of the most recent bar i with `high_i > max(high[i-L..i-1])` and
  `high_i > max(high[i+1..i+R])`, available from bar i+R onward; same for `last_pivot_low`. Defaults L=4, R=4
  (TradeStation); variant R=2 (TradingView).
- Setup at close t: `close_t < last_pivot_high_t`, pivot age <= 30 bars, `trend_state >= 0`.
- Entry: buy stop `last_pivot_high_t + 0.01`. **Missing hook**: resting stop-entry (good-till-filled, cancel after N
  sessions; `cancel_unfilled_entries_after_sessions` is 1 today).
- Stop: `last_pivot_low - 0.01`; exit rule: trail to each new confirmed pivot low (ratchet only).
- Target: none -> `min_reward_risk: 0.0`; `max_hold_days: 20`.
- Reuses: `_pivots` helper in levels.py (generalise to asymmetric L/R), `trend_state`.

## What the router should know
Control/baseline for `sr_breakout`; not for execution.

## Signs of decay to monitor
Replay only; compare against `sr_breakout` on the same dates.

## Sources
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/pivot_reversal_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/pivot_extension_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/new_high_le_signal_.htm
- https://www.tradingview.com/support/folders/43000587406-built-in-strategies/
- https://ru.tradingview.com/support/solutions/43000599890

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 64773 | 61246 | 51% | +0.01 | -0.02 | 50% | +0.01 | -0.02 | 51% | +0.11 | +0.08 | 1.31 |
| correction | 7426 | 6989 | 55% | +0.02 | -0.00 | 54% | +0.02 | -0.00 | 56% | +0.14 | +0.12 | 1.48 |
| healthy_uptrend | 200525 | 186631 | 50% | +0.01 | -0.03 | 48% | -0.00 | -0.04 | 46% | +0.02 | -0.01 | 1.06 |
| high_vol_selloff | 37012 | 35126 | 56% | +0.05 | +0.03 | 53% | +0.08 | +0.05 | 47% | +0.04 | +0.02 | 1.10 |
| narrow_uptrend | 30796 | 29638 | 43% | -0.07 | -0.11 | 39% | -0.13 | -0.16 | 43% | -0.11 | -0.14 | 0.78 |
| **all** | 340532 | 319630 | 50% | +0.01 | -0.02 | 48% | +0.00 | -0.03 | 47% | +0.04 | +0.01 | 1.09 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 206209 | 194858 | 52% | +0.02 | -0.00 | 53% | +0.07 | +0.04 | 50% | +0.11 | +0.08 | 1.31 |
| correction | 111914 | 103819 | 52% | -0.01 | -0.03 | 55% | +0.07 | +0.05 | 50% | +0.06 | +0.03 | 1.16 |
| healthy_uptrend | 621158 | 576630 | 51% | +0.01 | -0.02 | 51% | +0.02 | -0.01 | 48% | +0.04 | +0.01 | 1.09 |
| high_vol_selloff | 190843 | 182766 | 51% | -0.01 | -0.03 | 51% | -0.02 | -0.04 | 48% | -0.01 | -0.04 | 0.96 |
| narrow_uptrend | 162540 | 152727 | 52% | +0.04 | +0.01 | 52% | +0.05 | +0.02 | 49% | +0.08 | +0.05 | 1.21 |
| **all** | 1292664 | 1210800 | 51% | +0.01 | -0.02 | 51% | +0.03 | +0.01 | 49% | +0.05 | +0.02 | 1.13 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
