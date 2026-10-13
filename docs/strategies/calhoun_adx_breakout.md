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
_Generated 2026-10-13 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. `vs SPY` is the net R minus what SPY returned over the same days on the same dollars (beta 1, dividends ignored): the leaderboard's yardstick. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 145 | 78 | 49% | +0.07 | -0.04 | -0.08 | 51% | +0.12 | +0.01 | -0.03 | 52% | +0.27 | +0.16 | +0.05 | 1.57 |
| correction | 8 | 4 | 50% | +0.03 | -0.06 | -0.25 | 25% | -0.26 | -0.36 | -0.62 | 25% | -0.26 | -0.36 | -0.62 | 0.66 |
| healthy_uptrend | 747 | 413 | 42% | -0.12 | -0.20 | -0.19 | 44% | -0.04 | -0.13 | -0.14 | 39% | -0.04 | -0.13 | -0.16 | 0.93 |
| high_vol_selloff | 39 | 25 | 21% | -0.31 | -0.38 | -0.43 | 21% | -0.37 | -0.44 | -0.50 | 21% | -0.37 | -0.44 | -0.50 | 0.53 |
| narrow_uptrend | 38 | 23 | 14% | -0.34 | -0.47 | -0.44 | 23% | -0.41 | -0.54 | -0.65 | 25% | -0.59 | -0.71 | -0.85 | 0.23 |
| **all** | 977 | 543 | 42% | -0.10 | -0.19 | -0.19 | 43% | -0.04 | -0.13 | -0.15 | 40% | -0.02 | -0.12 | -0.17 | 0.96 |

Portfolio replay (net of costs, slots shared with its run): 90 trades, win 31%, avg -0.17R, PF 0.72, P&L $-8,134 on $100k, avg hold 9.4 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 308 | 190 | 40% | -0.11 | -0.22 | -0.18 | 51% | +0.03 | -0.08 | -0.10 | 43% | +0.03 | -0.08 | -0.08 | 1.05 |
| correction | 249 | 160 | 44% | -0.05 | -0.16 | -0.22 | 46% | -0.04 | -0.15 | -0.25 | 39% | -0.08 | -0.18 | -0.25 | 0.86 |
| healthy_uptrend | 2313 | 1446 | 46% | -0.05 | -0.14 | -0.15 | 44% | -0.06 | -0.15 | -0.15 | 36% | -0.11 | -0.21 | -0.22 | 0.82 |
| high_vol_selloff | 140 | 87 | 49% | -0.11 | -0.22 | -0.19 | 47% | -0.08 | -0.19 | -0.14 | 42% | -0.05 | -0.16 | -0.21 | 0.90 |
| narrow_uptrend | 279 | 179 | 43% | -0.04 | -0.15 | -0.23 | 46% | +0.04 | -0.06 | -0.22 | 39% | -0.07 | -0.18 | -0.28 | 0.89 |
| **all** | 3289 | 2062 | 45% | -0.06 | -0.16 | -0.16 | 45% | -0.04 | -0.14 | -0.16 | 38% | -0.09 | -0.19 | -0.21 | 0.85 |

Portfolio replay (net of costs, slots shared with its run): 181 trades, win 33%, avg -0.19R, PF 0.67, P&L $-22,562 on $100k, avg hold 9.3 bars.
