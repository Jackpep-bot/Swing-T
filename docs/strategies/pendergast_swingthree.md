---
slug: pendergast_swingthree
name: SwingThree (Donald Pendergast)
originators: [Donald Pendergast (S&C Dec 2013), thinkorswim built-in implementation]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [2, 20]     # estimate: exit on first close-range low below SMA(low); not published
timeframe: daily
direction: long_only_in_engine (original is long and short)
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# SwingThree (Pendergast)

## One-line summary
Trend-aligned channel breakout: in an uptrend (prior close above EMA50), buy when price clears the SMA-of-highs band by a
small offset; exit when the low no longer holds above the SMA-of-lows band.

## Origin and lineage
Donald Pendergast, Technical Analysis of Stocks & Commodities, Dec 2013; carried as a thinkorswim built-in strategy.
Intended for volatile, high-volume stocks and ETFs with smooth, regular swings.

## Exact rules (thinkorswim documentation)
- Trend filter: EMA(close, 50) (input `ema length`, default 50). Long only when the **previous** bar closed above it.
- Signal lines: SMA(high, n) and SMA(low, n); `sma length` n default **not published in the TOS docs** (unverified).
- Long entry: price exceeds SMA(high, n) + k ticks, k = 5 by default (emulates a stop order above the band).
- Long exit: when the low fails to stay above SMA(low, n).
- Short (not used in engine): price < SMA(low, n) - k ticks with prior close below EMA50; cover when high > SMA(high, n).
- No initial stop, target or sizing rule in the TOS version.

## Why it should work
Short-term continuation inside an established trend: a push above the recent average high in an uptrend tends to attract
breakout buyers; the SMA(low) exit is a volatility-scaled trailing stop. The other side is short-term mean-reversion sellers.

## When it works and when it fails
Smooth trending names (low noise relative to the band width). Fails in ranges, where the band breakout reverses within a
bar or two and the exit triggers immediately (many small losses).

## Parameters and sensitivity
n (unknown default; try 3-10 with 5 as the engine default, flagged as an assumption), EMA 30-100, offset 0-0.5% of price.
Short n plus a 5-tick offset makes trade count very sensitive to price level; convert ticks to % of price.

## Evidence
Only the in-sample S&C illustration (grade D). No independent test found. Broker publishes no statistics.

## Common mistakes
Applying 5 cents equally to a $10 and a $500 stock; ignoring the prior-bar EMA condition; using intraday high touches for
entry while the backtester only fills at the open.

## Discretionary parts and how to make them mechanical
Candidate selection ("volatile, liquid, smooth swings") -> universe filter (settings) plus adr_pct_20 >= 2% and
trend_state = 1.

## Implementation spec for swing-engine
- Module `strategies/swingthree.py`, `@register("strategy")`.
- Features: compute `sma_high_n`, `sma_low_n`, `ema_50` in-module (only sma/ema of close exist in the panel; ema_50 missing).
  Reuses adr_pct_20, atr_14, trend_state.
- Signal at close t: `close[t-1] > ema_50[t-1]` and `close[t] > sma_high_n[t] * (1 + offset_pct)`, offset_pct default 0.1%
  (stands in for 5 ticks). The original fires intrabar; the engine fires on the close and enters next open.
  A **stop-entry order hook** would allow the faithful version (buy stop at sma_high_n + offset).
- Stop: max(sma_low_n[t], entry - 2 x atr_14) below entry. Target: None.
  `should_exit`: `low[t] <= sma_low_n[t]` (exit on the close; original exits intrabar).
- `max_hold_days`: 20. `min_reward_risk`: not applied (no target).
- settings.yaml: `swingthree: {enabled: false, shadow_only: true, sma_length: 5, ema_length: 50, offset_pct: 0.1}`.

## What the router should know
Comparison-only S&C system. Overlaps with `pullback_trend` and `sr_breakout` (trend + short breakout); use replay to see
whether it adds anything over them.

## Signs of decay to monitor
Average holding period shrinking toward 1-2 days and win rate below 35% in replay mean the band is inside noise.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/R-S/SwingThree

## Empirical (replay)
_Pending: filled in from swing replay on real data._
