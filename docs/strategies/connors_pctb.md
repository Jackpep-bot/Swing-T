---
slug: connors_pctb
name: Connors %b strategy (ETF)
originators: [Larry Connors, Connors Research (High Probability ETF Trading, 2009, ch. 5)]
category: mean_reversion
decision: implement_disabled_for_comparison
holding_period_days: [3, 10]
timeframe: daily
direction: long (short mirror below the 200-day; engine long-only)
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Connors %b

## One-line summary
For an ETF above its 200-day SMA, after Bollinger %b has closed below 0.2 for three consecutive days, buy the close and exit when
%b closes above 0.8.

## Origin and lineage
This is chapter 5 of Connors' *High Probability ETF Trading* (2009), alongside RSI 25/75, 3-Day High/Low, R3 and TPS. %b is Bollinger's
normalised band position. Restatements: Quantified Strategies (rules public, results paywalled) and EdgeRater Academy.

## Exact rules
- **%b** = (close - lower band)/(upper band - lower band). **Band length and width used by Connors are not confirmed**:
  the restatements read do not state them. Test 20/2 and a short band (5-day, 1-2 SD) side by side and pick one a priori.
- **Setup and trigger:** close > SMA(200) AND %b < 0.2 on each of the last 3 closes. Buy on the close.
- **Aggressive version:** add on further oversold readings (**unverified**).
- **Exit:** %b closes > 0.8. **Stop:** none (Connors: "stops hurt"). **Target:** none.
- Short mirror: close < SMA(200), %b > 0.8 for 3 days, exit %b < 0.2.

## Why it should work
It is the same liquidity-provision mechanism as RSI(2). Three consecutive closes in the bottom of the band select persistent
selling in an uptrending diversified ETF.

## When it works and when it fails
Three days below 0.2 is a demanding condition, so it trades rarely. Quantified Strategies reports good results on SPY and QQQ "but very few
fills". The exit at 0.8 needs a full traverse of the band, so it holds longer than RSI(2) exits, which adds trend-break exposure.

## Parameters and sensitivity
Band settings (the main uncertainty), entry threshold 0.2, days 3, exit 0.8. With 20/2 bands, %b < 0.2 for 3 days is
rarer than with 5-day bands. Expect a large difference in trade count between the two settings. Do not pick the band after seeing results.

## Evidence
Connors tested 20 ETFs from inception to end-2008 (in-sample, figures not read this run). Quantified Strategies
re-test: "very good" on QQQ/SPY with few trades. Its statistics are paywalled and not verified. No independent out-of-sample test was found.

## Common mistakes
Mixing %b settings between scan and exit. Treating a 0.8 exit as a target price (it is a close-based condition).

## Discretionary parts and how to make them mechanical
None apart from choosing the band settings. Register two variants (`band=20/2`, `band=5/x`) as separate trials.

## Implementation spec for swing-engine
- Feature `pct_b_20 = (close - bb_lower_20)/(bb_upper_20 - bb_lower_20)` from existing columns. A short-band variant needs a
  parameterised `bollinger(close, 5, k)` call (constant `PCTB_BAND_WINDOW`).
- Entry: `close > sma_200 and max(pct_b over last 3 bars) < 0.2`. MOC needed for faithfulness (the **close-fill entry mode is missing**);
  interim next open.
- Exit (`should_exit`): `pct_b > 0.8`. Stop: catastrophic `entry - 2*atr_14`. `max_hold_days` 10. `min_reward_risk` 0.
- Universe: index and sector ETFs. Reuses `bb_*_20`, `sma_200`, `atr_14`.

## What the router should know
It is in the same bucket as `rsi2_meanrev` and `connors_3day_high_low`, and their signals overlap. Expect only a few trades a year per ETF.

## Signs of decay to monitor
With so few trades, monitor only aggregated across ETFs: rolling 20-trade mean return <= 0. Hold length drifting
above 8 days.

## Sources
- https://quantifiedstrategies.substack.com/p/larry-connors-b-strategy-bollinger-ab6
- https://academy.edgerater.com/?p=68
- https://www.bollingerbands.com/bollinger-band-rules

## Empirical (replay)
_Pending: filled in from swing replay on real data._
