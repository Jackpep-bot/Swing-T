---
slug: kaufman_stress
name: "Stress strategy (Perry Kaufman)"
originators: ["Perry Kaufman, 'Timing the Market With Pairs Logic', S&C March 2014", "thinkorswim Stress / StressIndicator"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [3, 30]
timeframe: daily
direction: long (index hedge leg not modelled)
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Kaufman Stress

## One-line summary
Buy a stock when it is oversold relative to its index (a stochastic of the gap between the stock's and the index's
stochastics drops below ~10) while the index trend is up; exit when the relative oversold condition unwinds (> 50).

## Origin and lineage
Perry Kaufman, "Timing The Market With Pairs Logic", *Technical Analysis of Stocks & Commodities*, March 2014
(cited by thinkorswim). Pairs-trading logic applied to stock-vs-index; coded by thinkorswim, TradeStation, others.

## Exact rules
**Stress Indicator** (thinkorswim): stochastic applied three times: (1) stock stochastic over `length`, (2) index
stochastic over `length`, (3) stochastic over `length` of the difference (1) - (2). Levels: oversold 10, overbought 90.

**Strategy** (thinkorswim):
- Initial buy: Stress < `entry level` and index in uptrend.
- Re-entry after an exit only when Stress falls below entry level from above 50.
- Sell when any: Stress > `exit level`; loss from entry > `stop loss` %; price below a minimum level within
  `min price length`.
- Hedge (not modelled): when the index average falls, short index = hedge ratio x position x stock/index volatility
  ratio.
- Defaults per secondary summary of the article: entry Stress < 10, exit > 50, index trend = 60-day moving average of
  the index rising. The stochastic `length` default, stop-loss % and min-price defaults: **unverified** (Traders' Tips
  page returned 403).

## Why it should work
Stocks that fall much more than their index without news tend to revert relative to it (short-term reversal,
Jegadeesh 1990; Lehmann 1990); requiring an index uptrend avoids buying into broad declines. The other side is
liquidity-driven selling in one name.

## When it works and when it fails
Works in rising or range-bound markets with idiosyncratic noise. Fails on stock-specific bad news (relative weakness is
information), and when the index turns down soon after entry (the hedge leg was Kaufman's answer; we have none).

## Parameters and sensitivity
`length` (stochastic window; try 20-60), entry 5-15, exit 50-70, index MA 50-100, stop 5-10%. Trap: optimising
length per symbol.

## Evidence
Kaufman's in-sample article results (not reviewed). No independent test found. Grade D. Academic short-term reversal
is the supporting family (weekly/monthly reversal profits, much weaker after costs in large caps).

## Common mistakes
Buying through earnings (relative weakness from a miss is not noise); ignoring the re-entry "from above 50" rule
(repeated entries in a falling stock).

## Discretionary parts and how to make them mechanical
Already mechanical; add an earnings blackout (no entry within 3 sessions after the stock's earnings) when dates exist.

## Implementation spec for swing-engine
- New features (market frame = SPY, already passed to `build_panel`):
  `stoch(x, n) = 100*(x - min(x,n)) / (max(x,n) - min(x,n))` on close (high/low version also acceptable);
  `s_stock = stoch(close, n)`, `s_index = stoch(spy_close, n)`, `d = s_stock - s_index`, `stress = stoch(d, n)`;
  n default 60 (unverified, param). `index_up = sma(spy_close,60)[t] > sma(spy_close,60)[t-1]`.
- Entry at t: `stress[t] < 10` and `index_up`; re-entry state: require `stress` was > 50 since the last exit
  (track per symbol: `stress[t-1] >= 10` and max(stress since last < 10 episode) > 50).
- Entry next open. Stop `entry * (1 - stop_pct)`, stop_pct 0.08 (engine choice). Target none; `min_reward_risk` 0.
  `should_exit`: `stress > 50`; `max_hold_days` 30.
- Reuses `market` frame plumbing (`market_trend_state` exists but is a different trend definition). Missing: SPY close
  broadcast per row, stochastic helper, re-entry state.

## What the router should know
Relative mean reversion; overlaps `rsi2_meanrev` in timing but conditions on relative weakness. Candidate for
narrow_uptrend and choppy at reduced risk. Long-only without the hedge: it carries full index beta.

## Signs of decay to monitor
Win rate of stress < 10 entries falling under ~55% in index-up periods; average days-to-exit lengthening.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/R-S/Stress
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/R-S/StressIndicator
- https://traders.com/Documentation/FEEDbk_docs/2014/03/TradersTips.html (403 when fetched)
- https://store.traders.com/stcov321tima.html

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 136 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 831 | 5 | 63% | +0.19 | +0.10 | 58% | +0.22 | +0.13 | 54% | +0.39 | +0.31 | 2.09 |
| healthy_uptrend | 7380 | 32 | 49% | -0.03 | -0.12 | 46% | -0.03 | -0.13 | 42% | -0.04 | -0.13 | 0.92 |
| high_vol_selloff | 71 | 0 | 73% | +0.29 | +0.19 | 79% | +0.40 | +0.30 | 59% | +0.24 | +0.14 | 1.72 |
| narrow_uptrend | 874 | 3 | 38% | -0.17 | -0.24 | 33% | -0.22 | -0.30 | 44% | -0.14 | -0.22 | 0.71 |
| **all** | 9156 | 40 | 49% | -0.02 | -0.11 | 47% | -0.02 | -0.11 | 43% | -0.00 | -0.09 | 1.00 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 4019 | 9 | 54% | +0.06 | -0.02 | 53% | +0.11 | +0.03 | 54% | +0.26 | +0.18 | 1.74 |
| correction | 1000 | 2 | 52% | +0.03 | -0.06 | 42% | -0.05 | -0.14 | 35% | -0.11 | -0.21 | 0.79 |
| healthy_uptrend | 20610 | 54 | 49% | -0.01 | -0.09 | 47% | -0.01 | -0.09 | 44% | -0.03 | -0.11 | 0.93 |
| high_vol_selloff | 615 | 4 | 53% | +0.03 | -0.04 | 52% | +0.05 | -0.03 | 43% | -0.07 | -0.14 | 0.85 |
| narrow_uptrend | 5071 | 21 | 51% | +0.03 | -0.06 | 50% | +0.03 | -0.06 | 46% | +0.04 | -0.04 | 1.09 |
| **all** | 31315 | 90 | 50% | +0.00 | -0.07 | 48% | +0.01 | -0.07 | 45% | +0.01 | -0.06 | 1.03 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
