---
slug: consecutive_bars
name: Consecutive up/down closes and BarUpDn (thinkorswim, TradeStation, TradingView)
originators: [thinkorswim/TradeStation/TradingView built-ins]
category: pattern
decision: implement_disabled_for_comparison
holding_period_days: [2, 20]
timeframe: daily
direction: both
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: none
free_data_ok: true
status: not_built
---

# Consecutive bars (ConsBarsUp/Down, Consecutive Up/Down, BarUpDn)

## One-line summary
Buy after N higher closes in a row (short after N lower closes); a naive short-term-momentum demonstration
strategy kept as a null baseline against which real setups are compared.

## Origin and lineage
No individual originator: vendor demonstration strategies. thinkorswim ConsBarsUpLE / ConsBarsDownSE (default 4
bars), TradeStation Consecutive Ups LE / Downs SE (default 3), TradingView "Consecutive Up/Down" (defaults 3 and 3,
recalled, not verified) and "BarUpDn". Its mirror (buy after N down closes) is the Connors mean-reversion idea,
already covered by `rsi2_meanrev`.

## Exact rules
- ConsBarsUpLE: `close[t] > close[t-1]` for each of the last N bars (tos N=4, TradeStation N=3) -> buy next bar.
- ConsBarsDownSE: mirror -> short. Price input configurable (default close).
- BarUpDn (TradingView): long if `close > open and open > prev_close`; short if `close < open and open < prev_close`.
- No stops, targets or time exits in the entry scripts; TradingView versions are stop-and-reverse (always in market).
- Sizing: none.

## Why it should work
Weakly: short-horizon autocorrelation in trending names. Against it: at the 1-week horizon US stocks show
short-term reversal (losers outperform winners), which is why the down-streak mirror is the better-known edge.
Counterparty: mean-reversion traders fading the streak.

## When it works and when it fails
Can ride strong momentum names in healthy uptrends; fails in choppy and down tapes, where streaks exhaust.
Buying after 3-4 up days enters extended, with poor reward:risk to any structural stop.

## Parameters and sensitivity
N in 3-5; price input (close vs typical). Trap: testing N and direction both ways and keeping the winner.

## Evidence
None published by the vendors (catalog grade "none"). No independent test reviewed.

## Common mistakes
Treating it as a setup instead of a baseline; trading the stop-and-reverse version with no risk control.

## Discretionary parts and how to make them mechanical
Fully mechanical; only the exit is unspecified. Fix it before replay (below).

## Implementation spec for swing-engine
- Reuse: `up_days_3` (count of up closes in last 3 bars, features/cross_section.py): `up_days_3 == 3` is the
  TradeStation N=3 rule. For N=4 add `up_streak` (current run of consecutive up closes; already requested in
  docs/methods/10) and `down_streak`.
- Long: `up_streak >= N` (N param, default 3) on bar t -> entry next open; stop = `min(low over the N streak bars)`
  (structural) or entry - 2 x atr_14, whichever is tighter; target = entry + 2R; `max_hold_days = 10`;
  optional `trend_state == 1`.
- BarUpDn variant: `close > open and open > prev_close` -> next open, same exits.
- `min_reward_risk = 2.0`. Long only by default.

## What the router should know
Null baseline: it should never receive risk. Use its replay as the hurdle a "real" pattern must beat.

## Signs of decay to monitor
Not applicable (baseline). If it ever beats a live strategy, suspect the live strategy, not this one.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/A-D/ConsBarsUpLE
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/A-D/ConsBarsDownSE
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/consecutive_ups_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/consecutive_downs_se_signal_.htm
- https://www.tradingview.com/support/folders/43000587406-built-in-strategies/

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 6682 | 63 | 47% | +0.01 | -0.05 | 42% | -0.00 | -0.06 | 39% | +0.04 | -0.02 | 1.07 |
| correction | 1108 | 20 | 54% | +0.20 | +0.14 | 50% | +0.28 | +0.23 | 51% | +0.34 | +0.28 | 1.77 |
| healthy_uptrend | 26953 | 284 | 44% | -0.05 | -0.12 | 40% | -0.05 | -0.12 | 36% | -0.06 | -0.12 | 0.91 |
| high_vol_selloff | 4690 | 179 | 56% | +0.15 | +0.10 | 53% | +0.25 | +0.20 | 45% | +0.22 | +0.17 | 1.43 |
| narrow_uptrend | 2463 | 20 | 37% | -0.13 | -0.19 | 37% | -0.13 | -0.19 | 34% | -0.08 | -0.14 | 0.87 |
| **all** | 41896 | 566 | 46% | -0.02 | -0.08 | 42% | -0.00 | -0.07 | 38% | -0.00 | -0.06 | 1.00 |

Portfolio replay (net of costs, slots shared with its run): 1 trades, win 0%, avg -1.01R, PF 0.00, P&L $-220 on $100k, avg hold 1.0 bars.

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 23429 | 178 | 51% | +0.08 | +0.03 | 47% | +0.10 | +0.05 | 44% | +0.15 | +0.09 | 1.26 |
| correction | 17267 | 149 | 50% | +0.05 | +0.01 | 49% | +0.12 | +0.07 | 45% | +0.16 | +0.11 | 1.29 |
| healthy_uptrend | 88189 | 790 | 46% | -0.00 | -0.07 | 43% | +0.00 | -0.06 | 38% | +0.00 | -0.06 | 1.01 |
| high_vol_selloff | 25104 | 139 | 49% | +0.02 | -0.02 | 46% | +0.03 | -0.02 | 42% | +0.04 | -0.00 | 1.07 |
| narrow_uptrend | 18157 | 114 | 47% | +0.00 | -0.05 | 42% | -0.01 | -0.06 | 40% | +0.03 | -0.03 | 1.05 |
| **all** | 172146 | 1370 | 48% | +0.02 | -0.04 | 44% | +0.03 | -0.03 | 40% | +0.05 | -0.01 | 1.08 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
