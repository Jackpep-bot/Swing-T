---
slug: gandalf_project_research_system
name: "Gandalf Project Research System (D'Errico & Trombetta)"
originators: ["Domenico D'Errico and Giovanni Trombetta, 'System Development Using Artificial Intelligence', Technical Analysis of Stocks & Commodities (Aug 2017)", "thinkorswim built-in strategy"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [1, 10]   # exit lengths not published; assumption
timeframe: daily
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]   # assumption: dip-buy pattern
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: none
free_data_ok: true
status: not_built
---

# Gandalf Project Research System

## One-line summary
A machine-generated candle-pattern dip-buy: enter long after specific orderings of ohlc4, median price and mid-body
price that indicate short-term weakness; exit after a fixed number of bars or on a weakness pattern while losing.

## Origin and lineage
From D'Errico & Trombetta's S&C article (Aug 2017) on building systems with genetic algorithms and out-of-sample
testing; the pattern was found by search, not designed from a market thesis. thinkorswim ships it as
GandalfProjectResearchSystem. The article and its original instrument/timeframe were not read (traders.com 403).

## Exact rules (thinkorswim documentation)
Definitions: ohlc4 = (O+H+L+C)/4; median = (H+L)/2; mid-body = (O+C)/2 (thinkorswim MidBodyVal; standard definition,
assumed). Index [k] = k bars ago.
- Buy (either set, all conditions within the set):
  - A: ohlc4[1] < median[1]; median[2] <= ohlc4[1]; median[2] <= ohlc4[3].
  - B: ohlc4[1] < median[3]; midbody[0] < median[2]; midbody[1] < midbody[2].
- Sell to close (any):
  - `exit length` bars elapsed since entry;
  - `exit gain length` bars elapsed and close > entry price;
  - close < entry price and either weakness set holds:
    - C: ohlc4[1] < midbody[1]; median[2] == midbody[3]; midbody[1] <= midbody[4];
    - D: ohlc4[2] < midbody[0]; median[4] < ohlc4[3]; midbody[1] < ohlc4[1].
- Input defaults for `exit length` and `exit gain length` are not listed on the doc page. No stop, no sizing.
- Note: condition C requires an exact equality of two prices, which almost never happens on equities (likely an
  artifact of tick-sized futures data).

## Why it should work
No stated mechanism. At best it captures short-term reversal after a weak close in the bar range (Jegadeesh 1990).
Data-mined patterns found by genetic search usually fail out of sample unless the authors' OOS test was strict.

## When it works and when it fails
Unknown. Expect behaviour like other 1-3 day dip-buys: better in uptrends, poor in crashes.

## Parameters and sensitivity
Only the two exit lengths. Use fixed values (engine v1: exit_length = 5, exit_gain_length = 2; arbitrary, logged as
such) and do not tune.

## Evidence
None. Article claims (OOS methodology) not verified; no independent test found.

## Common mistakes
Treating a GA-found pattern as a discovered edge; running it on instruments other than those it was mined on without
noting it.

## Discretionary parts and how to make them mechanical
Fully mechanical. Replace the exact equality in C with |median[2] - midbody[3]| <= 0.001 x close as a variant.

## Implementation spec for swing-engine
- Features: `ohlc4`, `median_price`, `mid_body` per bar plus shifts 1-4 (cheap, no warm-up).
- Long on bar t close if set A or B is true; filter `trend_state >= 0` and universe liquidity as usual. Entry next open.
- Stop: engine needs one for sizing: entry - 1.5 x atr_14 (engine choice, logged).
- Exits: per rules above; also the stop. No target -> `min_reward_risk: 0.0`. max_hold_days: 5 (= exit_length).
- Reuses: `atr_14`, `trend_state`, `prev_close`. Missing: the three price transforms and a bars-since-entry exit hook
  with entry-price awareness (`should_exit(row, bars_held)` lacks entry price today).

## What the router should know
Short dip-buy with zero evidence and likely very high signal frequency (simple candle orderings); cap signals per day and
treat as shadow-only noise benchmark.

## Signs of decay to monitor
Win rate near 50% with average win <= average loss would mean no edge; signal count per day.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/E-K/GandalfProjectResearchSystem
- https://www.traders.com/Documentation/FEEDbk_docs/2017/08/TradersTips.html (Traders' Tips for the article; 403 this run)

## Empirical (replay)
_Pending: filled in from swing replay on real data._
