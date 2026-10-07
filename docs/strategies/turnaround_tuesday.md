---
slug: turnaround_tuesday
name: Turnaround Tuesday
originators: [Market folklore; tested by Quantified Strategies (practitioner)]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [1, 1]
timeframe: daily (close-to-close)
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [high_vol_selloff]
typical_win_rate: 0.56
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Turnaround Tuesday

## One-line summary
If SPY closes Monday at least 1% below Friday's close, buy at Monday's close and sell at Tuesday's close.

## Origin and lineage
Old trader saying that weak Mondays reverse on Tuesday (weekend/Monday effect literature, e.g. French 1980, is the
academic backdrop). Current rules and numbers come from Quantified Strategies' SPY backtest; their full rule
details for variants are paywalled (WebFetch 2026-10-07).

## Exact rules
- Instrument: SPY only (index ETF).
- Setup: Monday close <= 0.99 * prior Friday close (if Monday is a holiday, the source is silent; engine: first session of the week).
- Entry: market-on-close Monday. Exit: Tuesday close. No stop, no target.
- Sizing: not specified (full equity in the test).

## Why it should work
Short-horizon index mean reversion: liquidity-driven Monday selling (weekend news digestion, de-risking) is partly
reversed when liquidity providers are paid. Same family as RSI-2 / IBS index reversion.

## When it works and when it fails
Works when the broader trend is up (dip-buying regime). Fails in crashes (2008, Mar 2020) where -1% Mondays cluster
and follow-through continues.

## Parameters and sensitivity
Threshold (-1%), holding period (1 day vs until close > prior high), extra IBS filter. Variants improve stats but are
selected in-sample.

## Evidence
Quantified Strategies (SPY, period on paywalled page, no data-snooping correction):
- Base: 212 trades, +0.3%/trade, 56% winners, CAGR 1.8%, 2.5% time in market.
- With IBS filter: +0.33%/trade, 57%, CAGR 2.7%. Longer hold: +0.45%, 60%, CAGR 6.5%. Filters + flexible exit:
  +0.46%, 69%, CAGR 7%.
No academic replication located. Drawdown not reported in the free text.

## Common mistakes
Applying it to single stocks (untested); ignoring that the engine fills at next open (Tuesday open differs from Monday close).

## Implementation spec for swing-engine
- Features: `ret_monday = close_monday / close_prev_friday - 1` (per SPY; use the prior session close and the
  weekday of `ts`). Reuses `ret_1d` (equals it when Monday follows Friday).
- Signal: SPY, weekday == first session of the week, `ret_1d <= -0.01`.
- Entry: **MOC on Monday** (needs a market-on-close entry hook; current backtest fills at next open, which would test a
  different trade: Tuesday open to Tuesday close). Stop: catastrophic `entry - 3 * atr_14` (engine choice). Exit: Tuesday close, `max_hold_days = 1`.
- `min_reward_risk = 0.0`. Overlay sizing: at most the rsi2_meanrev index allocation.
- Missing: MOC entry/exit hook, SPY-as-tradable in the strategy universe.

## What the router should know
Low-exposure overlay at most. Disable in `high_vol_selloff` and `correction` (consistent with the engine's no-new-longs rule).

## Signs of decay to monitor
Rolling 40-trade average return <= 0; win rate < 50%.

## Sources
- https://quantifiedstrategies.substack.com/p/turnaround-tuesday-strategy-backtest

## Empirical (replay)
_Pending: filled in from swing replay on real data._
