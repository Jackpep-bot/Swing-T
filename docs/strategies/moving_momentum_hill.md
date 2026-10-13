---
slug: moving_momentum_hill
name: Moving Momentum (Arthur Hill)
originators: [Arthur Hill (StockCharts ChartSchool)]
category: setup
decision: implement_disabled_for_comparison
holding_period_days: [5, 30]
timeframe: daily
direction: long (short mirror in source; engine long-only)
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff, choppy]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Moving Momentum (Hill)

## One-line summary
In an uptrend (SMA20 > SMA150), wait for Stochastic(14,3) to drop below 20, then buy when the MACD(12,26,9) histogram turns
positive; stop under recent support.

## Origin and lineage
Arthur Hill, StockCharts ChartSchool "Moving Momentum" strategy article. A three-layer trend / pullback / momentum-turn template;
Hill presents it as a starting point for system development, not a finished system.

## Exact rules (ChartSchool)
- Trend: SMA(close,20) > SMA(close,150) = long-only bias.
- Setup: Stochastic Oscillator (14,3) moves below 20 (pullback).
- Trigger: MACD histogram (12,26,9) turns positive after the setup. Hill notes the histogram is usually negative when the
  stochastic is below 20 and can stay negative for a week or two; no maximum delay is given.
- Initial stop: recent support (drawn by hand in the examples).
- Exits/targets: none formalised. Sizing: none.
- Shorts mirror: SMA20 < SMA150, stochastic above 80, histogram turns negative.

## Why it should work
Classic buy-the-dip-in-trend: the long-term filter keeps you with the intermediate trend, the stochastic finds an oversold
pullback, and the histogram turn waits for short-term momentum to resume, so you do not catch a falling knife. Counterparty:
short-term sellers exhausting into an intact uptrend.

## When it works and when it fails
Works in trending markets with orderly pullbacks. Fails when the pullback becomes a trend change (SMA20/150 is slow to flip),
and in chop where stochastic <20 and histogram turns happen constantly. Hill himself calls one of his examples "not the most
ideal".

## Parameters and sensitivity
SMA 20/150, stochastic 14/3 and level 20, MACD 12/26/9, plus the unstated setup-to-trigger window (use 10 bars, param). Keep the
published values; vary only the window (5-15) and the stochastic level (20 vs 30).

## Evidence
Author examples only; no published statistics. No independent test found. Grade D. MACD/stochastic rule evidence in general is
weak for single US stocks after costs.

## Common mistakes
Triggering on the histogram turn without a prior stochastic setup; letting the setup stay "armed" indefinitely; using the
%K line vs %D inconsistently (ChartSchool's Stochastic(14,3) = %K 14 smoothed by 3, i.e. slow %K).

## Discretionary parts and how to make them mechanical
- Stochastic: slow %K = SMA3 of 100*(close - min(L,14))/(max(H,14) - min(L,14)).
- Setup armed if slow %K < 20 on any bar in [t-10, t].
- Trigger: macd_hist_{t-1} <= 0 and macd_hist_t > 0.
- Support stop: min(low) over the setup window (from the first bar with %K < 20 to t), minus 0.1*atr_14; cross-check with
  `support_1` and use the higher of the two if it is below entry.
- Target: prior 20-bar swing high, fallback 2R.

## Implementation spec for swing-engine
- Module `strategies/moving_momentum.py`, registered `moving_momentum`, disabled.
- Features: add `sma_150`, `stoch_k_14_3`, `bars_since_stoch_below_20`, `macd_hist_prev`; reuse `sma_20`, `macd_hist`,
  `atr_14`, `support_1`.
- Signal on close t: sma_20 > sma_150; bars_since_stoch_below_20 <= 10; macd_hist_prev <= 0 < macd_hist.
- Entry next open. Stop per above. Target: max(prior 20-bar high, entry + 2R); min_reward_risk 1.5.
- Exit: engine breakeven at +1R and lowest-low trail from +2R; optional `should_exit` when sma_20 < sma_150.
- max_hold_days: 25.
- Missing: sma_150, stochastic, bars-since helper (patterns.bars_since exists and can be reused).

## What the router should know
Pullback family, overlapping pullback_trend and ichimoku_cloud_pullback. healthy_uptrend 1.0, narrow_uptrend 0.5 for the
comparison run. The 20/150 trend filter is looser than trend_state (close > sma50 > sma200), so it fires earlier and more often.

## Signs of decay to monitor
Many triggers more than 7 bars after setup (late entries); win rate below 40% with payoff below 1.5.

## Sources
- https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/moving-momentum

## Empirical (replay)
_Generated 2026-10-10 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 757 | 20 | 47% | -0.04 | -0.20 | 39% | -0.12 | -0.28 | 35% | -0.16 | -0.32 | 0.73 |
| correction | 113 | 7 | 36% | -0.17 | -0.39 | 48% | +0.12 | -0.10 | 45% | +0.34 | +0.12 | 1.74 |
| healthy_uptrend | 4489 | 162 | 45% | -0.03 | -0.19 | 42% | -0.03 | -0.19 | 40% | -0.01 | -0.17 | 0.98 |
| high_vol_selloff | 876 | 45 | 61% | +0.40 | +0.21 | 52% | +0.40 | +0.21 | 40% | +0.24 | +0.05 | 1.40 |
| narrow_uptrend | 520 | 11 | 34% | -0.16 | -0.32 | 40% | -0.04 | -0.21 | 33% | -0.08 | -0.26 | 0.88 |
| **all** | 6755 | 245 | 46% | +0.01 | -0.15 | 43% | +0.02 | -0.15 | 39% | +0.01 | -0.16 | 1.01 |

Portfolio replay (net of costs, slots shared with its run): 1 trades, win 100%, avg +1.45R, PF inf, P&L $1,002 on $100k, avg hold 25.0 bars.

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 4117 | 231 | 50% | +0.07 | -0.09 | 51% | +0.17 | +0.01 | 47% | +0.19 | +0.04 | 1.37 |
| correction | 1112 | 36 | 52% | +0.14 | -0.00 | 47% | +0.12 | -0.01 | 44% | +0.20 | +0.06 | 1.37 |
| healthy_uptrend | 13779 | 774 | 46% | -0.02 | -0.17 | 43% | -0.02 | -0.18 | 40% | -0.00 | -0.16 | 1.00 |
| high_vol_selloff | 2343 | 150 | 50% | +0.10 | -0.10 | 47% | +0.12 | -0.08 | 43% | +0.10 | -0.10 | 1.17 |
| narrow_uptrend | 3381 | 150 | 44% | -0.03 | -0.19 | 45% | +0.03 | -0.13 | 40% | +0.02 | -0.14 | 1.03 |
| **all** | 24732 | 1341 | 47% | +0.01 | -0.15 | 45% | +0.03 | -0.12 | 42% | +0.05 | -0.11 | 1.09 |

Portfolio replay (net of costs, slots shared with its run): 2 trades, win 0%, avg -0.58R, PF 0.00, P&L $-591 on $100k, avg hold 3.0 bars.
