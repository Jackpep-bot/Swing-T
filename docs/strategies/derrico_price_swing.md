---
slug: derrico_price_swing
name: "Price Swing detector entries (Domenico D'Errico)"
originators: ["Domenico D'Errico (S&C, May 2017)", "thinkorswim PriceSwing"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [1, 20]
timeframe: daily
direction: long (original also shorts downswings; engine long-only)
regimes_good: [choppy, healthy_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Price Swing detector (D'Errico)

## One-line summary
Four interchangeable definitions of an "upswing" (pivot low, close back above the lower Bollinger Band, RSI back
above 40, or higher low while RSI is oversold); buy each upswing and exit after a fixed 20 bars.

## Origin and lineage
Domenico D'Errico, S&C May 2017 (per catalog; article not read); coded by thinkorswim as PriceSwing (catalog B22).
It is a detector library more than a strategy: the fixed time exit is a way to compare detectors.

## Exact rules (thinkorswim)
- Swing type 1, Pivot High-Low: upswing when the low first falls below the previous low and then rises (low[t] >
  low[t-1] after low[t-1] < low[t-2]).
- Type 2, Bollinger crossover: close crosses above the lower band (downswing: below the upper band).
- Type 3, RSI crossover: RSI crosses above oversold 40 (downswing: below overbought 60).
- Type 4, RSI + higher low: low > previous low while RSI below oversold (downswing: lower high while RSI above
  overbought).
- Buy on every upswing; short on every downswing; exit after 20 bars (default). No price stop. RSI length and BB
  length/width defaults: unverified (tos text truncated); this card assumes RSI(14) and BB(20, 2).

## Why it should work
Each detector marks the end of a short down-swing; buying the turn captures short-term reversal. The fixed 20-bar exit
makes it a test of drift after the turn rather than a managed trade.

## When it works and when it fails
Works in ranges and in uptrends with shallow dips. Fails in persistent downtrends: every minor bounce is an "upswing";
type 1 fires very often (most days in a choppy tape), so it is mainly a baseline.

## Parameters and sensitivity
Swing type (4 variants), RSI levels 40/60 (loose; 30/70 is classic), BB length/width, hold bars 5-20. Trap: picking the
best of four detectors in-sample and reporting it as the edge; count all four as trials (deflated Sharpe).

## Evidence
D'Errico's in-sample illustration only; no broker statistics; no independent test found. Grade D.

## Common mistakes
Using type 1 without any trend filter (signal flood); no stop on a 20-bar hold.

## Discretionary parts and how to make them mechanical
Fully mechanical; add `trend_state >= 0` gate and an ATR stop as engine choices.

## Implementation spec for swing-engine
- Variants as `swing_type` param:
  1. `low[t] > low[t-1] and low[t-1] < low[t-2]` (uses `prior_low` from `rows_as_of` plus one more lag).
  2. `close[t] > bb_lower_20[t] and close[t-1] <= bb_lower_20[t-1]`.
  3. `rsi_14[t] > 40 and rsi_14[t-1] <= 40`.
  4. `low[t] > low[t-1] and rsi_14[t] < 40`.
- Entry next open. Stop `entry - 2*atr_14` (engine choice). Target none; `min_reward_risk` 0. `max_hold_days` 20
  (time exit, as original). Optional gate `trend_state >= 0`.
- Reuses `bb_lower_20`, `rsi_14`, `atr_14`, `trend_state`. Nothing missing for the long side.

## What the router should know
Mean-reversion / swing-turn baseline. Type 2 overlaps `bb_bullish_engulfing_kosinski` and `zscore_mean_reversion_garner`;
type 3 overlaps `rsi2_meanrev`. Low priority; use as a benchmark for other turn detectors.

## Signs of decay to monitor
20-bar forward return after signals indistinguishable from unconditional 20-bar return of the universe.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/L-P/PriceSwing

## Empirical (replay)
_Generated 2026-10-13 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. `vs SPY` is the net R minus what SPY returned over the same days on the same dollars (beta 1, dividends ignored): the leaderboard's yardstick. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 2741 | 9 | 49% | -0.02 | -0.12 | -0.18 | 47% | -0.01 | -0.12 | -0.21 | 43% | +0.03 | -0.08 | -0.22 | 1.06 |
| correction | 473 | 1 | 43% | -0.07 | -0.23 | +0.13 | 72% | +0.38 | +0.23 | +0.01 | 70% | +0.80 | +0.65 | -0.42 | 4.57 |
| healthy_uptrend | 7359 | 46 | 50% | +0.03 | -0.08 | -0.13 | 45% | -0.01 | -0.12 | -0.21 | 39% | -0.01 | -0.11 | -0.23 | 0.99 |
| high_vol_selloff | 3022 | 27 | 60% | +0.14 | +0.02 | -0.09 | 62% | +0.28 | +0.16 | -0.18 | 50% | +0.22 | +0.10 | -0.30 | 1.50 |
| narrow_uptrend | 1527 | 7 | 34% | -0.19 | -0.30 | -0.26 | 32% | -0.32 | -0.43 | -0.12 | 27% | -0.35 | -0.47 | -0.61 | 0.48 |
| **all** | 15122 | 90 | 50% | +0.02 | -0.09 | -0.13 | 49% | +0.03 | -0.08 | -0.19 | 42% | +0.05 | -0.06 | -0.28 | 1.10 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 10152 | 90 | 57% | +0.13 | +0.03 | -0.12 | 56% | +0.22 | +0.11 | -0.15 | 52% | +0.33 | +0.23 | -0.18 | 1.77 |
| correction | 3761 | 33 | 62% | +0.21 | +0.12 | -0.05 | 54% | +0.19 | +0.10 | -0.02 | 52% | +0.34 | +0.25 | +0.00 | 1.80 |
| healthy_uptrend | 23918 | 286 | 48% | -0.03 | -0.13 | -0.15 | 45% | -0.04 | -0.15 | -0.19 | 41% | -0.01 | -0.12 | -0.20 | 0.98 |
| high_vol_selloff | 12908 | 174 | 49% | -0.03 | -0.14 | -0.10 | 49% | +0.01 | -0.10 | -0.11 | 44% | -0.00 | -0.11 | -0.13 | 1.00 |
| narrow_uptrend | 8284 | 88 | 51% | +0.02 | -0.08 | -0.14 | 49% | +0.05 | -0.06 | -0.14 | 45% | +0.09 | -0.01 | -0.09 | 1.19 |
| **all** | 59023 | 671 | 51% | +0.02 | -0.08 | -0.13 | 49% | +0.04 | -0.06 | -0.15 | 45% | +0.09 | -0.02 | -0.15 | 1.18 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
