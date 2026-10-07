---
slug: cci_correction
name: CCI Correction (weekly CCI bias, daily CCI dip and recovery)
originators: [Donald Lambert (CCI, 1980); StockCharts ChartSchool (strategy write-up)]
category: pullback
decision: implement_disabled_for_comparison
holding_period_days: [5, 30]
timeframe: weekly bias + daily signal
direction: long (bearish-bias short mirror; engine long-only)
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# CCI Correction

## One-line summary
Once weekly CCI(26) has pushed above +100 (bullish bias), buy when daily CCI dips below -100 and then crosses back above 0.
It is a trend pullback entry timed by an oscillator.

## Origin and lineage
Donald Lambert introduced the Commodity Channel Index in *Commodities* magazine (1980). StockCharts ChartSchool
(Arthur Hill) wrote up "CCI Correction" as a two-timeframe strategy. ChartSchool notes that by construction about 70-80% of CCI values
fall between +/-100, so extremes occur 20-30% of the time.

## Exact rules
- **CCI:** TP = (H+L+C)/3. CCI_n = (TP - SMA_n(TP)) / (0.015 * mean absolute deviation of TP over n).
- **Bias:** weekly CCI(26) crosses above +100 sets the bias to bullish. It stays bullish until weekly CCI(26) crosses below -100
  (bearish). The daily alternative for the bias is CCI(100).
- **Setup (bullish bias):** daily CCI (26, or 20) closes below -100.
- **Trigger:** daily CCI then closes back above 0. Buy (next open in a daily system).
- **Stops and targets:** left to the trader. ChartSchool says disciplined stops and profit-taking are required but gives none.
- Bearish mirror: in a bearish bias, a daily CCI move above +100 and then back below 0 is a sell or short signal.

## Why it should work
It buys a correction within an established trend, so trend followers re-entering and momentum continuation are on the
buyer's side. Waiting for CCI to recover to 0 means the pullback has already turned, at the cost of a later entry.

## When it works and when it fails
It works in persistent trends with orderly pullbacks. It fails in late-trend tops: the bias is sticky (it needs -100 weekly to flip)
and keeps signalling longs into a top. ChartSchool's 2008-2010 S&P 500 examples were mixed, including a failed Feb 2008 signal.
In chop the daily CCI whipsaws through 0.

## Parameters and sensitivity
- Weekly bias length (26 weeks) or daily CCI(100), signal CCI 20 or 26, thresholds +/-100 and the 0 re-cross.
  Changing the re-cross from 0 to -100 makes the entry earlier and noisier.
- Overfitting trap: two lengths, three thresholds and an unspecified exit. Fix the exit a priori.

## Evidence
Practitioner illustration only. No published statistics (catalog grade D), and no independent or academic test of this rule was found.

## Common mistakes
Leaving the exit unspecified (it turns into a discretionary hold). Recomputing the weekly bias with the
current, incomplete week. Point-in-time rule: use only completed weeks as of `as_of`.

## Discretionary parts and how to make them mechanical
- Exit, as proposed for testing: daily CCI crosses above +100 and then back below +100 (take profit), or a close below the setup's lowest
  low (stop), or 20-day time stop.
- Stop: lowest low between the -100 dip and the trigger, minus 0.1*atr_14.

## Implementation spec for swing-engine
- New features: `cci_20` (catalog item `cci_indicator`, "implement"), `cci_26`, and a weekly `cci_26w` built from
  week-ending Friday bars (completed weeks only, forward-filled to daily rows).
- State: `cci_bias` in {+1, -1, 0} with hysteresis (+100 / -100 crosses on `cci_26w`); daily `cci_dip_seen` = min(cci_26 over the
  last 10 bars) < -100.
- Entry: `cci_bias == 1 and cci_dip_seen and cci_26[t-1] <= 0 < cci_26[t]`, filled at the next open.
- Stop: as above. Target: none (rule exit). `max_hold_days` 20. `min_reward_risk` 0 (rule exit), or 1.5 if a fixed
  2R target variant is tested.
- Reuses `atr_14`, `trend_state` (optional confirm). Missing: CCI features and weekly resampling helper.

## What the router should know
It is a pullback-in-trend setup, the same family as `pullback_trend` and `pullback_holy_grail`. Allow it only when the market trend is up.
Signals cluster after broad pullbacks, so cap them per sector.

## Signs of decay to monitor
A falling share of signals that reach a new 20-day high within 10 bars, and a rising share stopped within 3 bars.

## Sources
- https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/cci-correction

## Empirical (replay)
_Pending: filled in from swing replay on real data._
