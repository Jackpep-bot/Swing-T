---
slug: calhoun_four_day_breakout
name: Four-Day Breakout (Ken Calhoun)
originators: [Ken Calhoun]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [2, 15]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Four-Day Breakout (Calhoun)

## One-line summary
In a stock above its moving average, four consecutive bullish candles followed by a buy stop a fixed offset above the
pattern's highest high.

## Origin and lineage
Ken Calhoun, "Swing Trading Four-Day Breakouts", *Technical Analysis of Stocks & Commodities*, October 2017. Shipped
as the thinkorswim built-in `FourDayBreakoutLE` (entry only; exits come from separate strategies).

## Exact rules (thinkorswim description)
- Filter: close > SMA(close, `average length`). The default length is not stated on the reference page (unverified).
- Setup: the last `pattern length` (default 4) candles are all bullish (close > open).
- Trigger: buy stop at the highest high of those candles + `breakout amount` (default $0.50).
- Stop, target, sizing: not specified in the broker description; Calhoun's article was not available this run.

## Why it should work
Four up-closes show persistent buying; a buy stop above the pattern only fills if demand continues (short-term
continuation). Who is on the other side: short-term mean-reversion sellers and late shorts. Counter-argument: four
up days in a row is also a short-term overbought condition, where the literature favours reversal (e.g. Connors'
RSI(2) work), so this is a contrarian test of the engine's mean-reversion assumption.

## When it works and when it fails
Trending, low-volatility markets with broad participation. Fails in chop (buy stop fills at the top of the range) and
when the four candles are small-bodied drift.

## Parameters and sensitivity
- `pattern_len` 3-5; `sma_len` 20/50 (replay both; the published default is unknown); `offset` as
  0.1-0.25 x `atr_14` instead of $0.50, since a fixed dollar amount means 5% on a $10 stock and 0.1% on a $500 one.
- Trap: tuning the offset to the sample's average breakout follow-through.

## Evidence
Practitioner in-sample illustration only (grade D). The broker publishes no performance data. No independent test
located.

## Common mistakes
Using the $0.50 offset across price levels; counting doji as bullish; entering at the next open instead of the stop
(changes the trade entirely).

## Discretionary parts
Exit is unspecified. Make it mechanical with the engine defaults (initial stop below the pattern low, breakeven at
+1R, trail at +2R) and a time stop.

## Implementation spec for swing-engine
- Features: `bull_k` = close > open; `bull_run_4` = rolling sum of `bull_k` over 4 bars == 4; `pattern_high_4` =
  rolling max(high, 4) on the as-of bar; `pattern_low_4` = rolling min(low, 4).
- Signal at as-of close if `bull_run_4` and close > `sma_50` (replay `sma_20` as well) and `trend_state >= 0`.
- Entry: buy stop at `pattern_high_4 + 0.15 x atr_14`, valid for 1 session. Stop = `pattern_low_4 - 0.1 x atr_14`
  (engine choice). Target = entry + 2R; `max_hold_days: 10`; `min_reward_risk: 2.0`.
- Reuses: `sma_20`, `sma_50`, `atr_14`, `trend_state`, playbook gate.
- Missing: **stop-entry order hook** in the backtester (today `_fill_entry` only fills at the next open, with an
  optional limit). Interim approximation: next-open entry only if next open <= trigger and next high >= trigger,
  filling at max(open, trigger); this needs the hook.

## What the router should know
Breakout family; healthy_uptrend only. Disabled; comparison against `breakout_52w` and `momentum_burst`.

## Signs of decay to monitor
Fill rate of the buy stop vs subsequent 5-day return; share of fills that close below the trigger the same day.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/E-K/FourDayBreakoutLE

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 5435 | 3051 | 51% | +0.03 | -0.05 | 51% | +0.03 | -0.05 | 49% | +0.10 | +0.02 | 1.23 |
| correction | 1055 | 559 | 62% | +0.26 | -0.02 | 60% | +0.26 | -0.02 | 61% | +0.29 | +0.01 | 1.82 |
| healthy_uptrend | 19886 | 10423 | 47% | -0.02 | -0.10 | 46% | -0.03 | -0.11 | 44% | +0.01 | -0.08 | 1.01 |
| high_vol_selloff | 2217 | 1305 | 52% | -0.01 | -0.14 | 48% | -0.02 | -0.15 | 38% | -0.11 | -0.23 | 0.82 |
| narrow_uptrend | 1538 | 997 | 48% | -0.01 | -0.09 | 48% | -0.01 | -0.09 | 46% | +0.04 | -0.05 | 1.09 |
| **all** | 30131 | 16335 | 49% | -0.00 | -0.09 | 48% | -0.00 | -0.10 | 45% | +0.03 | -0.07 | 1.05 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 17314 | 8710 | 49% | -0.03 | -0.10 | 50% | +0.01 | -0.07 | 48% | +0.04 | -0.03 | 1.10 |
| correction | 13639 | 7326 | 51% | -0.02 | -0.11 | 54% | +0.06 | -0.04 | 47% | +0.03 | -0.06 | 1.07 |
| healthy_uptrend | 68668 | 35207 | 50% | +0.01 | -0.07 | 50% | +0.03 | -0.05 | 46% | +0.04 | -0.04 | 1.09 |
| high_vol_selloff | 11003 | 5914 | 48% | -0.04 | -0.13 | 48% | -0.05 | -0.14 | 48% | -0.02 | -0.11 | 0.96 |
| narrow_uptrend | 12024 | 5932 | 50% | +0.01 | -0.08 | 49% | +0.01 | -0.08 | 46% | +0.02 | -0.06 | 1.05 |
| **all** | 122648 | 63089 | 50% | -0.00 | -0.09 | 50% | +0.02 | -0.06 | 47% | +0.03 | -0.05 | 1.08 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
