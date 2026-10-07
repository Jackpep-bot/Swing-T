---
slug: connors_3day_high_low
name: Connors 3-Day High/Low (ETF)
originators: [Larry Connors, Connors Research (High Probability ETF Trading, 2009, strategy 1)]
category: mean_reversion
decision: implement_disabled_for_comparison
holding_period_days: [2, 6]
timeframe: daily
direction: long (short mirror below the 200-day; engine long-only)
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: not_built
---

# Connors 3-Day High/Low

## One-line summary
For an ETF above its 200-day SMA and below its 5-day SMA, after three straight days of lower highs and lower lows, buy
the close and exit on the first close above the 5-day SMA.

## Origin and lineage
This is strategy 1 of Connors' *High Probability ETF Trading* (2009), in the same family as RSI(2) and Double 7s (methods/11). It was tested by
the author on 20 liquid ETFs. EdgeRater replicated it. Quantified Strategies has a write-up, but it is paywalled and was not read.

## Exact rules
- **Universe:** liquid ETFs (Connors' 20: SPY, QQQ, IWM, EEM, GLD, sector SPDRs and others).
- **Setup:** close > SMA(200); close < SMA(5).
- **Trigger:** high[t] < high[t-1] < high[t-2] < high[t-3] AND low[t] < low[t-1] < low[t-2] < low[t-3] (three consecutive
  lower highs and lower lows). EdgeRater's text has a typo comparing today's high with the prior low. Use high vs high.
- **Entry:** market-on-close of the signal day.
- **Aggressive version:** add a second unit if the ETF closes below the entry price during the trade (**unverified**).
- **Stop:** none in the original. **Target:** none. **Exit:** first close > SMA(5).
- **Sizing:** not specified beyond the scale-in variant.

## Why it should work
The same as RSI(2): three days of one-way pressure in an uptrending, diversified ETF is usually flow, not news, and the
liquidity provider earns the bounce. ETFs rarely carry single-name event risk.

## When it works and when it fails
It works in bull markets with shallow pullbacks. It fails when the 200-day filter is still "on" at the start of a bear leg, which is the
first leg of a correction, and the no-stop hold rides it down.

## Parameters and sensitivity
Number of lower-high/low days (2-4), exit MA (5), and the trend MA (200). Requiring 4 days cuts signals sharply. Keep 3 as
taught. Do not sweep.

## Evidence
- EdgeRater (Connors' 20 ETFs, 1 Jan 1993 - 31 Dec 2008): mean 4-day forward return after entry **+0.547%** (SD
  2.87%) vs a baseline of all ETF days **+0.094%** (SD 3.48%). The difference is about 45 bp per 4 days (EdgeRater's page
  mis-states it as 480 bp). Costs are not included, there is no equity curve, and the period overlaps the book's own development window.
- No post-2009 out-of-sample test was verified.

## Common mistakes
Using next-open fills (part of the reversal is lost overnight). Applying it to single stocks with earnings gaps. Leaving out the
200-day filter.

## Discretionary parts and how to make them mechanical
None. It is fully mechanical.

## Implementation spec for swing-engine
- Belongs in the `rsi2_meanrev` family as a variant module (`connors_3day_hl`).
- Features: new `sma_5` (add 5 to `SMA_WINDOWS` in `features/indicators.py`; methods/11 already recommends this).
  `lhll_3 = all(high.diff() < 0 and low.diff() < 0 over the last 3 bars)`.
- Reuses `sma_200`, `atr_14`.
- Entry: the faithful version needs an **MOC / close-fill entry mode** (missing; the backtester fills at next open). Interim: next open,
  reported as a known handicap.
- Stop: catastrophic `entry - 2*atr_14` (engine safety, not in the source). Exit via `should_exit`: `close > sma_5`.
  `max_hold_days` 6. `min_reward_risk` 0.
- Universe: index and sector ETFs only (a config list).

## What the router should know
It is highly correlated with `rsi2_meanrev` signals on the same ETFs. Count them as one mean-reversion bucket. Same regime
map as `rsi2_meanrev`.

## Signs of decay to monitor
Rolling 30-trade mean return under +0.2% per trade. Mean hold rising above 5 days.

## Sources
- https://edgerater.com/blog/connors-etf-three-day-highlow-method
- https://quantifiedstrategies.substack.com/p/larry-connors-3-day-highlow-method (paywalled, not read)
- docs/methods/11-rsi2-connors-mean-reversion.md

## Empirical (replay)
_Pending: filled in from swing replay on real data._
