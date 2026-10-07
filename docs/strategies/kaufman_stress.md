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
_Pending: filled in from swing replay on real data._
