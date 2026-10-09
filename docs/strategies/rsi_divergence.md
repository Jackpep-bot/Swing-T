---
slug: rsi_divergence
name: RSI regular / hidden divergence (TradingView)
originators: [J. Welles Wilder (RSI, 1978); divergence usage is folklore; TradingView built-in indicator]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [3, 20]
timeframe: daily
direction: long   # regular bullish (reversal) and hidden bullish (continuation); bearish types are exits only
regimes_good: [choppy, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# RSI divergence

## One-line summary
Price makes a lower low while RSI(14) makes a higher low (regular bullish), or price makes a higher low while RSI makes
a lower low (hidden bullish); signals confirm only 5 bars after the pivot, and there is no published validation.

## Origin and lineage
RSI is Wilder's (1978). Divergence reading is long-standing chart lore; the catalogued definition is TradingView's
built-in "RSI Divergence Indicator". Formula status "approximation" (the built-in's exact pivot pairing was not
re-checked).

## Exact rules (TradingView built-in)
- RSI(14). Pivots on RSI with left/right lookback 5/5. Two pivots must be 5-60 bars apart.
- Regular bullish: price lower low + RSI higher low. Regular bearish: price higher high + RSI lower high.
- Hidden bullish: price higher low + RSI lower low (continuation). Hidden bearish: price lower high + RSI higher high.
- Signal confirmed only after the 5 right-side bars: a built-in 5-bar lag.
- No entry, stop, target or sizing rules are part of the indicator.

## Why it should work
Momentum fading while price extends suggests the move is running out of participation. The lag means much of any
reversal is already over by confirmation.

## When it works and when it fails
Ranges and pullbacks. Fails in strong trends: divergence can repeat several times while price keeps going.

## Parameters and sensitivity
RSI length, pivot left/right (5/5), pivot spacing (5-60), whether RSI must be below 30 at the low. Every knob is
tunable and the LuxAlgo "out-of-sample optimizer" exists precisely because results swing with them: high overfit risk.

## Evidence
- No published validation for equities.
- Backtrex DAX test (4-hour bars, RSI 14, divergence within last 10 candles, price in lower half of a 100-bar range,
  1.5% stop / 3% target, 0.02% commission per side), Oct 2016 - Oct 2026: 106 trades, 38.7% wins, PF 1.16, +16.5% vs
  +136.4% buy-and-hold; most of the gain came in 2018. Different market and timeframe, but the only concrete test found.

## Common mistakes
Using unconfirmed pivots (repainting / look-ahead); counting divergence in a downtrend as a buy; ignoring the lag.

## Discretionary parts and how to make them mechanical
Use only confirmed pivots (bar i is a pivot low when its value is the min of bars i-5..i+5, known at i+5). Pair the
latest confirmed RSI pivot low with the previous one 5-60 bars earlier; compare the price lows at the same bars.

## Implementation spec for swing-engine
- Reuses: `rsi_14`, OHLC, `atr_14`, `trend_state`; `features/levels.py pivot_lows()` already implements the centred
  pivot with confirmation at `width` bars (width 5 matches), and is the base for the catalog's `swing_point_labeling`.
- New features: `rsi_pivot_low` (pivot of `rsi_14`), `price_at_pivot` (low at that bar), `bull_div_regular`,
  `bull_div_hidden` (0/1 on the confirmation bar i+5), `div_pivot_low` (the price low of the latest pivot).
- Signal at close of confirmation bar t: regular bullish (variant A, require `rsi_14 at pivot < 35`) or hidden bullish
  with `trend_state == 1` (variant B).
- Entry: next open. Stop: `div_pivot_low - 0.5 * atr_14`. Target: comparison variant `resistance_1` with
  `min_reward_risk: 2.0`; else time exit. `max_hold_days: 20`.
- No-look-ahead check: the shift test must show the flag only appears at i+5.

## What the router should know
Regular bullish = mean reversion (choppy only); hidden bullish = trend continuation (uptrend regimes). Treat as two
strategies for routing. Overlaps `sr_bounce` (pivot support).

## Signs of decay to monitor
Win rate on 2R targets below 33% (breakeven); PF < 1.1 over 50+ trades.

## Sources
- https://www.luxalgo.com/library/indicator/RRp1xOWb-rsi-divergence/
- https://www.luxalgo.com/library/indicator/rsi-divergence-out-of-sample-optimizer/
- https://backtrex.com/en/backtests/rsi-divergence-dax

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 266 | 6 | 51% | +0.23 | +0.07 | 47% | +0.11 | -0.05 | 33% | +0.10 | -0.06 | 1.17 |
| correction | 51 | 0 | 35% | -0.27 | -0.58 | 29% | -0.38 | -0.70 | 39% | -0.12 | -0.44 | 0.81 |
| healthy_uptrend | 1025 | 12 | 41% | -0.07 | -0.22 | 39% | -0.10 | -0.25 | 33% | -0.15 | -0.30 | 0.76 |
| high_vol_selloff | 641 | 9 | 62% | +0.29 | +0.10 | 70% | +0.58 | +0.39 | 59% | +0.64 | +0.45 | 2.53 |
| narrow_uptrend | 262 | 4 | 51% | -0.05 | -0.19 | 34% | -0.21 | -0.36 | 32% | -0.15 | -0.30 | 0.73 |
| **all** | 2245 | 31 | 49% | +0.07 | -0.10 | 48% | +0.10 | -0.06 | 41% | +0.11 | -0.05 | 1.20 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1272 | 19 | 45% | +0.04 | -0.12 | 45% | +0.07 | -0.09 | 41% | +0.13 | -0.03 | 1.21 |
| correction | 866 | 9 | 54% | +0.25 | +0.10 | 50% | +0.32 | +0.17 | 49% | +0.65 | +0.49 | 2.27 |
| healthy_uptrend | 3072 | 25 | 47% | +0.06 | -0.09 | 43% | +0.02 | -0.13 | 38% | -0.04 | -0.19 | 0.93 |
| high_vol_selloff | 3578 | 63 | 51% | +0.10 | -0.10 | 51% | +0.14 | -0.07 | 47% | +0.15 | -0.05 | 1.29 |
| narrow_uptrend | 1268 | 16 | 43% | -0.04 | -0.19 | 41% | -0.07 | -0.22 | 39% | +0.03 | -0.13 | 1.04 |
| **all** | 10056 | 132 | 48% | +0.08 | -0.10 | 47% | +0.08 | -0.09 | 43% | +0.12 | -0.05 | 1.21 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
