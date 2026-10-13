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
_Generated 2026-10-13 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. `vs SPY` is the net R minus what SPY returned over the same days on the same dollars (beta 1, dividends ignored): the leaderboard's yardstick. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 64668 | 60180 | 52% | +0.01 | -0.07 | -0.23 | 50% | +0.01 | -0.07 | -0.26 | 52% | +0.08 | +0.01 | -0.30 | 1.30 |
| correction | 7393 | 6881 | 54% | +0.02 | -0.13 | -0.23 | 53% | +0.02 | -0.13 | -0.43 | 57% | +0.12 | -0.03 | -0.67 | 1.50 |
| healthy_uptrend | 199964 | 183405 | 50% | +0.01 | -0.08 | -0.11 | 49% | +0.00 | -0.08 | -0.11 | 47% | +0.02 | -0.06 | -0.13 | 1.06 |
| high_vol_selloff | 36755 | 34117 | 54% | +0.03 | -0.07 | -0.16 | 51% | +0.05 | -0.05 | -0.22 | 50% | +0.04 | -0.06 | -0.26 | 1.13 |
| narrow_uptrend | 30592 | 29095 | 43% | -0.06 | -0.15 | -0.12 | 39% | -0.10 | -0.19 | -0.13 | 45% | -0.08 | -0.17 | -0.29 | 0.77 |
| **all** | 339372 | 313678 | 50% | +0.01 | -0.08 | -0.14 | 49% | +0.00 | -0.08 | -0.16 | 48% | +0.03 | -0.05 | -0.19 | 1.10 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 211860 | 194073 | 52% | +0.01 | -0.06 | -0.14 | 54% | +0.04 | -0.03 | -0.19 | 54% | +0.06 | -0.01 | -0.26 | 1.26 |
| correction | 112755 | 102044 | 52% | -0.01 | -0.08 | -0.13 | 55% | +0.05 | -0.02 | -0.13 | 51% | +0.04 | -0.04 | -0.15 | 1.14 |
| healthy_uptrend | 660313 | 594783 | 51% | +0.01 | -0.07 | -0.09 | 51% | +0.01 | -0.07 | -0.11 | 50% | +0.01 | -0.06 | -0.15 | 1.05 |
| high_vol_selloff | 199861 | 184487 | 51% | +0.00 | -0.09 | -0.10 | 52% | -0.00 | -0.09 | -0.08 | 51% | -0.00 | -0.09 | -0.14 | 0.99 |
| narrow_uptrend | 162514 | 148606 | 53% | +0.03 | -0.05 | -0.11 | 53% | +0.04 | -0.03 | -0.11 | 52% | +0.07 | -0.01 | -0.11 | 1.27 |
| **all** | 1347303 | 1223993 | 52% | +0.01 | -0.07 | -0.10 | 52% | +0.02 | -0.06 | -0.12 | 51% | +0.03 | -0.05 | -0.16 | 1.10 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
