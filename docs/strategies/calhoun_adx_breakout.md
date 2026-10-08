---
slug: calhoun_adx_breakout
name: ADX Breakouts (Ken Calhoun)
originators: [Ken Calhoun]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [2, 20]
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

# ADX Breakouts (Calhoun)

## One-line summary
When ADX crosses above 40 while price is at its 15-day high, record that bar's high and buy on a stop a fixed offset
above it.

## Origin and lineage
Ken Calhoun, "ADX Breakouts", *Technical Analysis of Stocks & Commodities*, March 2016. thinkorswim ships
`ADXBreakoutsFilter` (scan) and `ADXBreakoutsLE` (entry only; e.g. pair with `TrailingStopLX` for exits).

## Exact rules (thinkorswim description)
- Universe filter: price between $20 and $70, and 15-day high-low range >= $5 (catalog; 2016 dollar rules).
- Trigger bar: ADX(`adx length`) crosses above `adx level` (40) and the high is the `highest length` (15) bar high.
  ADX length default is not stated on the reference page (Wilder's 14 is assumed; unverified).
- Entry: buy stop at the trigger bar's high + `offset` ($0.50).
- Exits: not part of the entry strategy.

## Why it should work
ADX above 40 marks an established, strong directional move; a new 15-day high confirms the direction is up. Buyers
are momentum followers; sellers are early profit-takers. Caveat: ADX lags and is non-directional; readings of 40+
often occur late in a move, near exhaustion.

## When it works and when it fails
Works in persistent trends. Fails when ADX > 40 marks a climax (ADX turning down soon after) and in sharp
V-reversals where ADX is high from the prior downtrend; requiring `plus_di_14 > minus_di_14` fixes the latter.

## Parameters and sensitivity
- `adx_level` 30-45; `highest_len` 10-20; offset as 0.1-0.25 x `atr_14`.
- Price filter: replace $20-$70 with the engine universe (`min_price` 5, liquidity floors). Range filter: 15-day
  (max high - min low)/close >= 10% instead of $5 (on a $50 stock, $5 = 10%).

## Evidence
Practitioner in-sample illustration (grade D); no broker statistics; no independent test located.

## Common mistakes
Reading ADX as bullish without checking DI direction; using dollar filters on today's price levels.

## Discretionary parts
Exit unspecified; use the engine's stop/trail defaults.

## Implementation spec for swing-engine
- Features: `adx_14`, `plus_di_14`, `minus_di_14` exist in `features/patterns2.py`. New: `adx_cross_40` =
  `adx_14 >= 40` and prior `adx_14 < 40`; `at_high_15` = high >= rolling max(high, 15); `range_15_pct` =
  (max high 15 - min low 15) / close.
- Signal: `adx_cross_40` and `at_high_15` and `plus_di_14 > minus_di_14` and `range_15_pct >= 0.10`.
- Entry: buy stop at trigger high + 0.15 x `atr_14`, valid up to 3 sessions (the tos order stays live until filled;
  3 is an engine choice). Stop = entry - 2 x `atr_14`. Target 2R or trail (engine `trail_after_r`).
  `max_hold_days: 15`; `min_reward_risk: 2.0`.
- Reuses: `adx_14`, DI columns, `atr_14`, `trend_state`.
- Missing: stop-entry order hook with multi-session validity.

## What the router should know
Breakout family; healthy_uptrend only. Comparison control for `breakout_52w` (does an ADX gate add anything?).

## Signs of decay to monitor
Win rate and mean R of fills where ADX turned down within 3 bars vs not.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/A-D/ADXBreakoutsLE
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/A-B/ADXBreakoutsFilter

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 144 | 78 | 48% | +0.06 | -0.04 | 50% | +0.12 | +0.02 | 53% | +0.27 | +0.17 | 1.58 |
| correction | 8 | 4 | 50% | +0.03 | -0.06 | 25% | -0.26 | -0.36 | 25% | -0.26 | -0.36 | 0.66 |
| healthy_uptrend | 752 | 410 | 42% | -0.12 | -0.21 | 43% | -0.05 | -0.13 | 38% | -0.05 | -0.14 | 0.93 |
| high_vol_selloff | 38 | 22 | 19% | -0.39 | -0.47 | 19% | -0.46 | -0.54 | 19% | -0.46 | -0.54 | 0.45 |
| narrow_uptrend | 39 | 24 | 14% | -0.34 | -0.47 | 23% | -0.41 | -0.54 | 25% | -0.59 | -0.71 | 0.23 |
| **all** | 981 | 538 | 41% | -0.11 | -0.20 | 43% | -0.05 | -0.14 | 39% | -0.03 | -0.13 | 0.95 |

Portfolio replay (net of costs, slots shared with its run): 83 trades, win 30%, avg -0.20R, PF 0.67, P&L $-9,468 on $100k, avg hold 9.2 bars.

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 297 | 182 | 41% | -0.12 | -0.23 | 50% | -0.01 | -0.12 | 41% | -0.03 | -0.15 | 0.95 |
| correction | 234 | 146 | 44% | -0.05 | -0.16 | 45% | -0.00 | -0.11 | 39% | -0.01 | -0.11 | 0.99 |
| healthy_uptrend | 2225 | 1340 | 46% | -0.05 | -0.15 | 44% | -0.07 | -0.17 | 36% | -0.13 | -0.22 | 0.80 |
| high_vol_selloff | 121 | 67 | 46% | -0.15 | -0.25 | 41% | -0.16 | -0.27 | 37% | -0.08 | -0.19 | 0.86 |
| narrow_uptrend | 258 | 164 | 48% | -0.02 | -0.13 | 51% | +0.12 | +0.01 | 40% | +0.00 | -0.11 | 1.01 |
| **all** | 3135 | 1899 | 46% | -0.06 | -0.16 | 45% | -0.05 | -0.15 | 37% | -0.10 | -0.20 | 0.85 |

Portfolio replay (net of costs, slots shared with its run): 231 trades, win 35%, avg -0.19R, PF 0.68, P&L $-20,676 on $100k, avg hold 9.8 bars.
