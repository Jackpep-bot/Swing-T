---
slug: kaufman_three_period_divergence
name: "Three Period Divergence (Perry Kaufman)"
originators: ["Perry Kaufman (S&C, 2014 per catalog)", "thinkorswim ThreePeriodDivergence"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [3, 20]
timeframe: daily
direction: long (thinkorswim also shorts; engine long-only)
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Three Period Divergence (Kaufman)

## One-line summary
Measure price-vs-stochastic divergence with linear-regression slopes over three lookbacks; thinkorswim's version buys
when price slopes are up but momentum slopes are down on enough of the three periods, and exits when they agree again.

## Origin and lineage
Perry Kaufman (author of *Trading Systems and Methods*), S&C article dated June 2014 in the catalog (not verified
here); coded by thinkorswim. It tries to make "divergence", usually eyeballed, objective.

## Exact rules (thinkorswim reference, verified 2026-10-07)
- Momentum: stochastic FastK (or FastD) with `momentum length` 5-40.
- Slopes: linear-regression slope of price and of momentum over three periods: `dvg length1` ~5,
  `dvg length2` 6-12, `dvg length3` 7-15.
- Divergence on a period = slope signs opposite. Bearish = price slope up, momentum slope down.
- **Buy** when bearish divergence occurs on `entry number` of the three periods; **sell (short)** on bullish divergence.
  This is the opposite of the textbook reading (bearish divergence = sell); it is what the tos reference states.
  Whether Kaufman's article intended this (divergence as continuation) is unverified.
- **Exit** when all three price slopes have the same sign as momentum slopes (`max divergences` input).
- `long only` input disables shorts. Defaults for `entry number` and exact lengths: unverified.

## Why it should work
As coded it is a trend-continuation entry: price still rising while the oscillator cools is a pause, not exhaustion,
in persistent trends (time-series momentum). The other side: traders selling "bearish divergence".

## When it works and when it fails
Works in steady trends where oscillators roll over during sideways drift. Fails at genuine tops (where divergence is
a real warning) and in choppy ranges where slope signs flip constantly.

## Parameters and sensitivity
Six lookback knobs plus FastK/FastD and entry count: large search space for a grade-D idea. Pre-register one set:
momentum 14, periods 5/10/15, FastK, entry number 3.

## Evidence
Only Kaufman's in-sample S&C illustration (not reviewed); no broker statistics. Grade D. No independent test found.

## Common mistakes
Reading the signal direction as textbook divergence; using slopes on raw price for different-priced stocks without
normalising (sign-only use avoids this).

## Discretionary parts and how to make them mechanical
Already mechanical. Test both directions (tos "bearish buy" and textbook "bullish buy") as two pre-registered variants.

## Implementation spec for swing-engine
- New features: `stoch_k_14 = 100*(close - min(low,14)) / (max(high,14) - min(low,14))`;
  `slope(x, n)` = OLS slope of x on 0..n-1 over the last n bars (vectorised via rolling covariance:
  `cov(x, idx, n) / var(idx, n)`), for close and stoch_k at n = 5, 10, 15.
- `div_i = sign(slope_close_n_i) > 0 and sign(slope_k_n_i) < 0`; entry when `sum(div_i) >= entry_number` and
  it was not true on t-1. Variant B: textbook bullish (price slope < 0, momentum slope > 0).
- Entry next open. Stop `entry - 2*atr_14` (engine choice; none in original). Target none; `min_reward_risk` 0.
  `should_exit`: all three slope pairs same sign; `max_hold_days` 20.
- Reuses `atr_14`, `trend_state` (optional gate >= 0). Missing: stochastic and rolling-slope helpers.

## What the router should know
Behaves like a trend-continuation pullback (variant A) or a reversal (variant B). Route variant A with pullback family
in up regimes only.

## Signs of decay to monitor
Variant A vs B performance converging to zero; slope-sign flip rate (signals per symbol per month) rising.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/T-Z/ThreePeriodDivergence

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1269 | 8 | 53% | +0.04 | -0.06 | 51% | +0.09 | -0.01 | 52% | +0.28 | +0.18 | 1.67 |
| correction | 85 | 1 | 50% | +0.02 | -0.18 | 48% | -0.00 | -0.20 | 37% | +0.01 | -0.19 | 1.02 |
| healthy_uptrend | 4459 | 34 | 51% | +0.04 | -0.07 | 47% | +0.08 | -0.02 | 43% | +0.16 | +0.06 | 1.28 |
| high_vol_selloff | 232 | 4 | 33% | -0.23 | -0.33 | 29% | -0.34 | -0.44 | 21% | -0.45 | -0.56 | 0.33 |
| narrow_uptrend | 296 | 2 | 40% | -0.04 | -0.16 | 46% | +0.02 | -0.10 | 36% | +0.08 | -0.04 | 1.12 |
| **all** | 6341 | 49 | 50% | +0.03 | -0.08 | 47% | +0.07 | -0.04 | 44% | +0.16 | +0.05 | 1.29 |

Portfolio replay (net of costs, slots shared with its run): 98 trades, win 34%, avg -0.16R, PF 0.68, P&L $-8,975 on $100k, avg hold 6.1 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 3508 | 13 | 49% | +0.01 | -0.10 | 48% | +0.03 | -0.08 | 40% | +0.04 | -0.07 | 1.07 |
| correction | 3532 | 12 | 59% | +0.05 | -0.07 | 54% | +0.03 | -0.09 | 47% | +0.02 | -0.10 | 1.04 |
| healthy_uptrend | 17700 | 60 | 49% | +0.00 | -0.11 | 46% | +0.01 | -0.10 | 39% | -0.04 | -0.15 | 0.93 |
| high_vol_selloff | 1657 | 6 | 52% | -0.01 | -0.14 | 45% | -0.22 | -0.35 | 40% | -0.19 | -0.32 | 0.73 |
| narrow_uptrend | 2401 | 7 | 53% | +0.05 | -0.06 | 51% | +0.09 | -0.03 | 45% | +0.07 | -0.05 | 1.14 |
| **all** | 28798 | 98 | 51% | +0.01 | -0.10 | 48% | +0.01 | -0.10 | 41% | -0.02 | -0.14 | 0.96 |

Portfolio replay (net of costs, slots shared with its run): 327 trades, win 42%, avg -0.67R, PF 0.40, P&L $-12,780 on $100k, avg hold 6.4 bars.
