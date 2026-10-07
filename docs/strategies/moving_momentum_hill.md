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
_Pending: filled in from swing replay on real data._
