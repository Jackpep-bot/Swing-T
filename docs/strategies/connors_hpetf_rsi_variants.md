---
slug: connors_hpetf_rsi_variants
name: Connors HPETF RSI(4) 25/75, Multiple Days Down, RSI 10/6
originators: [Larry Connors, Connors Research (High Probability ETF Trading, 2009)]
category: mean_reversion
decision: implement_disabled_for_comparison
holding_period_days: [2, 6]
timeframe: daily
direction: long (shorts mirror; engine long-only)
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: none
free_data_ok: true
status: not_built
---

# Connors HPETF RSI variants (RSI 25/75, Multiple Days Down, RSI 10/6)

> **Every threshold on this card comes from the catalog's recollection of the book and is unverified.** Verify against
> *High Probability ETF Trading* before any trial is logged.

## One-line summary
These are three more ETF pullback rules from the same book, all filtered by the 200-day SMA, bought at the close and exited on a bounce: RSI(4) < 25,
4 down closes out of 5 below the 5-day SMA, or RSI(2) < 10 (adding if < 6).

## Origin and lineage
*High Probability ETF Trading* (Connors Research, 2009), which also contains 3-Day High/Low, %b, R3 and TPS (separate
cards). EdgeRater Academy lists the book's strategies. The rules below were not confirmed there this run.

## Exact rules (unverified)
| Variant | Setup / trigger (close > SMA(200) in all) | Aggressive add | Exit |
|---|---|---|---|
| RSI 25/75 | RSI(4) closes < 25 | add if RSI(4) < 20 | RSI(4) > 55 |
| Multiple Days Down | close < SMA(5); down closes on 4 of the last 5 days | add on a lower close | close > SMA(5) |
| RSI 10/6 | RSI(2) < 10 | add if RSI(2) < 6 | close > SMA(5) |
Entry is at the close in all three. No stop, no target. Shorts mirror: below the 200-day, RSI(4) > 75, 4 of 5 up, RSI(2) > 90 / 94.

## Why it should work
The same as RSI(2) (methods/11): short-horizon liquidity provision in uptrending diversified ETFs.

## When it works and when it fails
The same profile as the family: a high hit rate and small gains, with losses concentrated in trend breaks the 200-day filter is
slow to catch.

## Parameters and sensitivity
RSI length (2 vs 4) and thresholds. RSI 10/6 is nearly identical to the existing `rsi2_meanrev` entry (< 10); only the
exit (sma_5 vs sma_10/RSI>70) and the add-on differ. Testing all three alongside RSI(2) and Double 7s multiplies trials.
Count them in the deflated Sharpe.

## Evidence
None verified (catalog grade "none"). By analogy, the methods/11 out-of-sample RSI(2) results (+0.27%/trade SPX, +0.43% NDX, 2016-2026,
Backtrex) are the realistic ceiling.

## Common mistakes
Coding from recollection without checking the book. Treating RSI 10/6 as a new strategy when it is a near-duplicate of
`rsi2_meanrev`.

## Discretionary parts and how to make them mechanical
None. They are fully mechanical once the thresholds are verified.

## Implementation spec for swing-engine
- Implement as `rsi2_meanrev` parameter variants plus one new feature each:
  - `rsi_4`: add 4 to `RSI_PERIODS` in `features/indicators.py`.
  - `sma_5`: add 5 to `SMA_WINDOWS`.
  - `down_days_5 = count(close < prev_close over last 5 bars)` (the panel has `up_days_3` only).
- Variant params: `rsi_col`, `rsi_entry`, `exit_rule` in {`rsi_4>55`, `close>sma_5`}. The add-on needs the scale-in hook
  (missing; see `connors_tps_scale_in`). Test without add-ons first.
- Entry: MOC needed (missing); interim next open. Stop: catastrophic `entry - 2*atr_14`. `max_hold_days` 6.
  `min_reward_risk` 0. Universe: index and sector ETFs.

## What the router should know
They duplicate `rsi2_meanrev` exposure. Use them for comparison only and never run them alongside it at full size.

## Signs of decay to monitor
The same as `rsi2_meanrev`: rolling 30-trade expectancy <= 0, and average loss more than 2.5x the average win.

## Sources
- https://academy.edgerater.com/?p=68
- docs/methods/11-rsi2-connors-mean-reversion.md

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts round-trip slippage (10 bp a side) in R of each signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 9766 | 36 | 49% | +0.02 | -0.02 | 46% | -0.01 | -0.05 | 46% | +0.09 | +0.05 | 1.19 |
| correction | 814 | 1 | 49% | -0.00 | -0.04 | 74% | +0.42 | +0.38 | 73% | +0.83 | +0.79 | 5.26 |
| healthy_uptrend | 19754 | 56 | 52% | +0.07 | +0.02 | 48% | +0.07 | +0.02 | 42% | +0.08 | +0.04 | 1.15 |
| high_vol_selloff | 3348 | 21 | 54% | +0.11 | +0.08 | 58% | +0.30 | +0.26 | 44% | +0.18 | +0.15 | 1.35 |
| narrow_uptrend | 4490 | 11 | 47% | -0.05 | -0.10 | 38% | -0.16 | -0.21 | 36% | -0.13 | -0.18 | 0.79 |
| **all** | 38172 | 125 | 51% | +0.04 | +0.00 | 48% | +0.05 | +0.01 | 43% | +0.09 | +0.05 | 1.17 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 23750 | 47 | 59% | +0.15 | +0.12 | 58% | +0.26 | +0.22 | 52% | +0.36 | +0.32 | 1.83 |
| correction | 8477 | 24 | 57% | +0.11 | +0.08 | 54% | +0.15 | +0.12 | 48% | +0.18 | +0.15 | 1.40 |
| healthy_uptrend | 60581 | 185 | 50% | +0.00 | -0.04 | 48% | +0.03 | -0.01 | 43% | +0.07 | +0.03 | 1.13 |
| high_vol_selloff | 17800 | 105 | 46% | -0.08 | -0.11 | 41% | -0.11 | -0.14 | 37% | -0.10 | -0.14 | 0.82 |
| narrow_uptrend | 19015 | 31 | 55% | +0.08 | +0.04 | 51% | +0.09 | +0.05 | 45% | +0.13 | +0.09 | 1.27 |
| **all** | 129623 | 392 | 52% | +0.04 | -0.00 | 50% | +0.07 | +0.03 | 45% | +0.12 | +0.08 | 1.23 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
