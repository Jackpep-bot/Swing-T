---
slug: tko_landry
name: Trend Knockout (TKO, Dave Landry)
originators: [Dave Landry]
category: pattern
decision: implement_disabled_for_comparison
holding_period_days: [3, 20]
timeframe: daily
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Trend Knockout (TKO, Landry)

## One-line summary
In a strong uptrend, a single wide-range down bar flushes late buyers below recent lows; buy when price trades
back above that bar's high, stop under its low.

## Origin and lineage
Dave Landry (Sentive Trading), StockCharts TV "Trading Simplified", episode of 6 Nov 2019. Part of his pullback
toolkit (Proper Order 10 SMA > 20 EMA > 30 EMA, pullbacks of >= 2 lower lows, "2-for-1" exits; docs/methods/01).
The episode page contains no written rules; rules are in the video only. The catalog rule set is a restatement.

## Exact rules (restated, catalog)
- Trend: established strong uptrend (Landry's Proper Order or equivalent).
- Knockout bar: a wide-range bar against the trend that shakes out late buyers, often undercutting recent lows.
- Entry: buy stop above the knockout bar's high (trend resumption traps the new shorts). If the trend has truly
  ended, the trigger usually never fires.
- Stop: below the knockout bar's low.
- Exit: trail as a pullback trade (Landry's "2-for-1": half off at +1R, stop to breakeven, trail the rest - per
  docs/methods/01, itself unverified online).
- Undefined in the source read: the wide-range threshold, how "strong" the trend must be, how many days the
  trigger stays valid. All three must be logged as trial parameters.

## Why it should work
Stops of recent buyers sit just under recent lows and obvious MAs; a flush runs them, and fresh shorts enter on the
breakdown. When buyers reclaim the bar high the shorts are trapped and the stopped-out longs re-enter, fuelling the
resumption. Counterparty: breakdown shorts and weak-hand longs.

## When it works and when it fails
Works in leaders within a healthy market. Fails when the flush is the start of a regime change (market correction,
bad news): then the trigger often never fires, which is the built-in protection; the risk is the fills that do.

## Parameters and sensitivity
| Knob | Suggested | Range | Trap |
|---|---|---|---|
| wide range | range >= 1.5 x atr_14 (prior) | 1.25-2.0 | |
| down bar | close < open and close_pos <= 0.35 | | |
| undercut | low < min(low over prior 5 bars) | 3-10 | |
| trigger window | 3 bars | 1-5 | longer = generic pullback |
| trend | Proper Order or trend_state == 1 | | |

## Evidence
None published (catalog grade D, evidence text "None"). No independent test found.

## Common mistakes
Buying the knockout bar itself; widening the stop instead of waiting for the re-entry above the bar high.

## Discretionary parts and how to make them mechanical
As in the parameter table; Proper Order needs `ema_20` (exists in patterns2) and `ema_30` (missing).

## Implementation spec for swing-engine
- Reuse: `atr_14`, `trend_state`, `sma_10`, `ema_20` (features/patterns2.py), `close_pos`, `range_pct`.
- Missing: `ema_30` for Proper Order (`sma_10 > ema_20 > ema_30`); `prior_min_low_5` via `RollingSpec("low",
  "min", 5, prior=True)`.
- Setup bar k in [t-3, t-1]: `high_k - low_k >= 1.5 x atr_14[k-1]`, `close_k < open_k`, `close_pos_k <= 0.35`,
  `low_k < prior_min_low_5[k]`, and trend qualifies at k-1. Trigger: `close_t > high_k` (first time).
  Entry next open. Stop = `low_k - 0.1 x atr_14`. Target = highest high of 20 bars before k (prior swing high) or
  entry + 2R if higher. Exit: `max_hold_days = 15`; optional half at 1R (needs partial-exit support). 
  `min_reward_risk = 1.5`.
- Gap: taught entry is an intraday buy stop above the bar high; engine uses close trigger + next open, which
  enters later and with larger risk.

## What the router should know
Pullback family; only with an up market trend. Disabled for comparison.

## Signs of decay to monitor
Trigger-to-stop rate rising; knockout bars in leaders increasingly followed by lower lows.

## Sources
- https://articles.stockcharts.com/article/articles-landry-2019-11-trading-the-trend-knockout-582/
- https://proactiveadvisormagazine.com/market-trend-knockout-trend-knocked/
- https://help.stockcharts.com/charts-and-tools/stockchartsacp/stockchartsacp-plug-ins/trading-simplified-by-dave-landry

## Empirical (replay)
_Pending: filled in from swing replay on real data._
