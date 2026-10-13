---
slug: lizards_cooper
name: Lizards (new 10-day low with long lower tail; Jeff Cooper)
originators: [Jeff Cooper]
category: pattern
decision: implement_disabled_for_comparison
holding_period_days: [1, 5]
timeframe: daily
direction: long   # bearish mirror on 10-day highs; engine is long-only
regimes_good: [choppy, narrow_uptrend, healthy_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Lizards

## One-line summary
A new 10-day low that opens and closes in the top quarter of its range (a long lower tail, like a hammer) shows the
low was rejected; buy above its high the next day.

## Origin and lineage
Jeff Cooper, *Hit and Run Trading* (ch. 14). Close cousin of the hammer candle and of Turtle Soup (undercut and reject).

## Exact rules (long)
- Lizard bar: `low_t` is the lowest low of the last 10 bars (including t), and both open and close are in the top 25%
  of the bar's range.
- Entry: next day, buy stop above the lizard high (aggressive: buy the open).
- Stop: below the lizard low. Exit: 1-5 days (no fixed rule beyond author examples).

## Why it should work
Sellers pushed to a fresh short-term low and were fully absorbed within the session; the next-day break of the high
confirms buyers kept control.

## When it works and when it fails
Pullbacks and ranges in liquid names. Fails in steady downtrends where every bounce is sold, and on illiquid names
where tails are noise.

## Parameters and sensitivity
Lookback 10, the 25% thresholds, entry style (stop vs open). Few knobs; test only the two entry styles.

## Evidence
Author examples only; no independent test located (catalog C23, single secondary source).

## Common mistakes
Counting a bar with a tiny range (ratios are meaningless); ignoring the higher-timeframe trend.

## Discretionary parts and how to make them mechanical
Minimum range: `(high_t - low_t) >= 0.75 * atr_14_{t-1}` (engine choice, labelled).

## Implementation spec for swing-engine
- Reuses: OHLC, `close_pos`, `atr_14`, `trend_state`.
- New features: `open_pos = (open - low) / (high - low)`; `is_low_10 = low_t == min(low[t-9..t])`.
- Setup at close t: `is_low_10` and `open_pos >= 0.75` and `close_pos >= 0.75`.
- Entry (book): buy stop `high_t + 0.01` on t+1 only (needs stop-entry hook). Aggressive variant: next open (works with
  the current backtester as-is).
- Stop: `low_t - 0.01`. Target: none; `min_reward_risk: 0.0`; `max_hold_days: 5`.

## What the router should know
Mean-reversion bar pattern; overlaps `turtle_soup`, `key_reversal_day`, `sr_bounce`. Avoid correction regimes.

## Signs of decay to monitor
Lizard lows broken within 2 bars > 50% of fills; average 5-day R <= 0.

## Sources
- https://www.money.it/Il-segnale-di-trading-lizard-di

## Empirical (replay)
_Generated 2026-10-13 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. `vs SPY` is the net R minus what SPY returned over the same days on the same dollars (beta 1, dividends ignored): the leaderboard's yardstick. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 491 | 121 | 44% | -0.06 | -0.26 | -0.43 | 40% | +0.08 | -0.13 | -0.36 | 31% | +0.17 | -0.03 | -0.39 | 1.22 |
| correction | 30 | 6 | 58% | +0.03 | -0.18 | -0.11 | 62% | +0.30 | +0.09 | -0.38 | 50% | +0.33 | +0.12 | -1.17 | 1.61 |
| healthy_uptrend | 1197 | 317 | 48% | +0.19 | +0.00 | -0.18 | 39% | +0.21 | +0.02 | -0.22 | 32% | +0.36 | +0.17 | -0.11 | 1.48 |
| high_vol_selloff | 350 | 116 | 49% | +0.10 | -0.05 | -0.13 | 47% | +0.20 | +0.04 | -0.16 | 34% | +0.21 | +0.05 | -0.10 | 1.27 |
| narrow_uptrend | 260 | 67 | 31% | -0.45 | -0.69 | -0.49 | 19% | -0.72 | -0.97 | -0.44 | 20% | -0.53 | -0.78 | -0.52 | 0.50 |
| **all** | 2328 | 627 | 46% | +0.06 | -0.13 | -0.26 | 39% | +0.10 | -0.09 | -0.26 | 31% | +0.22 | +0.02 | -0.22 | 1.28 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1545 | 371 | 46% | +0.03 | -0.14 | -0.26 | 43% | +0.12 | -0.05 | -0.26 | 35% | +0.17 | +0.00 | -0.29 | 1.24 |
| correction | 1015 | 207 | 54% | +0.21 | +0.05 | -0.28 | 45% | +0.20 | +0.04 | -0.26 | 36% | +0.24 | +0.08 | -0.29 | 1.32 |
| healthy_uptrend | 4793 | 1440 | 41% | -0.08 | -0.27 | -0.29 | 36% | -0.06 | -0.25 | -0.29 | 29% | -0.09 | -0.28 | -0.38 | 0.88 |
| high_vol_selloff | 2862 | 965 | 47% | +0.04 | -0.11 | -0.13 | 40% | +0.04 | -0.12 | -0.09 | 31% | -0.06 | -0.21 | -0.08 | 0.92 |
| narrow_uptrend | 1686 | 390 | 56% | +0.30 | +0.12 | -0.02 | 51% | +0.32 | +0.14 | -0.10 | 36% | +0.21 | +0.03 | -0.27 | 1.30 |
| **all** | 11901 | 3373 | 47% | +0.05 | -0.13 | -0.21 | 41% | +0.07 | -0.10 | -0.21 | 32% | +0.03 | -0.15 | -0.28 | 1.04 |

Portfolio replay (net of costs, slots shared with its run): 2 trades, win 50%, avg -0.44R, PF 0.14, P&L $-295 on $100k, avg hold 3.0 bars.
