---
slug: vervoort_heikin_ashi_family
name: Vervoort Heikin-Ashi family (HACOLT, SVEHaTypCross, SVESC, SVEZLRBPercB, VolatilityBand)
originators: [Sylvain Vervoort (S&C articles 2008-2013), thinkorswim built-in strategies]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [2, 30]
timeframe: daily
direction: long (sources include shorts; engine long-only)
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Vervoort Heikin-Ashi family

## One-line summary
Five Sylvain Vervoort trend-following systems built on Heikin-Ashi (HA) smoothing and custom averages; one module with a
`variant` parameter so the comparison counts as one family of trials.

## Origin and lineage
Sylvain Vervoort, a series of Technical Analysis of Stocks & Commodities articles: "Trading with the Heikin-Ashi Candlestick
Oscillator" (Dec 2008), "Long-Term Trading Using Exchange Traded Funds" (Jul 2012), "Within the Volatility Band" (Aug 2013),
"Oscillators, Smoothed" (Sep 2013), "An Expert of a System" (Oct 2013), and an "Exploring Charting Techniques" piece (SVESC; issue
not given on the thinkorswim page). HA candles themselves are a Japanese charting technique popularised in the West by Dan Valcu
(see heikin_ashi_trend_ride).

## Exact rules (as described by thinkorswim; formulas partly approximated)
HA definitions: haClose = (O+H+L+C)/4; haOpen = (haOpen_{t-1} + haClose_{t-1})/2; haHigh = max(H, haOpen, haClose);
haLow = min(L, haOpen, haClose). Bullish bar = close > open (thinkorswim wording does not say whether real or HA bar; assume real).
1. HACOLT (Heikin-Ashi Candle Oscillator Long Term): oscillator takes values 0/50/100 from a set of HA and TEMA conditions
   (inputs: TEMA length, EMA length, candle size factor ~1.1). Long entry when it reaches 100, long exit when it leaves 100,
   short at 0. The internal condition set is not given on the thinkorswim page: unverified, must come from the 2008/2012 articles.
2. SVEHaTypCross: A = EMA(typical price hlc3, typical_length); B = EMA(haOHLC4, ha_length). Buy when A crosses above B on a
   bullish bar; sell when A crosses below B on a bearish bar. Defaults not stated on the page.
3. SVESC: A = avg(hlc3, length); B = avg(HA ohlc4, length); X = avg(close, exit_length). Buy when A rises above B on a bullish bar;
   long exit when A crosses below B on a bearish bar, or close < X and close < open.
4. SVEZLRBPercB: zero-lag %B of a Rainbow MA (smoothed with DEMA/TEMA) plus a stochastic; buy when both lines turn up from the
   prior bar, sell when both turn down. Exact smoothing chain unverified.
5. VolatilityBand: middle = SMA(EMA-smoothed hlc3, average_length); band offsets from a typical-minus-low deviation measure, with
   a smaller multiplier on the lower band. Buy when close > upper band; sell when close < lower band. Deviation formula unverified.
- Entry next bar open (thinkorswim simulated orders). No stops, targets or sizing taught.

## Why it should work
All five are smoothed trend-following crossovers: they buy after the trend has turned and hold until a smoothed reversal.
The counterparty is the late or anchored seller; the edge, if any, is generic time-series momentum. Nothing here is a distinct
mechanism.

## When it works and when it fails
Works in long, smooth trends (Vervoort's ETF examples). Fails in sideways markets (crossover whipsaw) and after gaps (HA lags by
construction; fills are at real prices, which can be far from HA levels).

## Parameters and sensitivity
Each variant has 2-6 lengths/factors. Five variants x their params is a large trial count; register the family as five trials
at platform defaults only and apply the deflated Sharpe with n_trials = 5.

## Evidence
Author's in-sample article examples only; broker publishes nothing; no independent test found. Grade D.

## Common mistakes
Filling at HA prices (HA open/close are synthetic); mixing HA and real bar direction; optimising each variant separately.

## Discretionary parts and how to make them mechanical
Rules are mechanical, but three formulas (HACOLT conditions, ZLRB smoothing chain, volatility-band deviation) are not fully
documented in the sources read. Implement SVEHaTypCross and SVESC first (fully specified up to defaults); leave the other three
`not_built` until the article formulas are verified.

## Implementation spec for swing-engine
- Module `strategies/vervoort_ha.py`, registered `vervoort_ha`, param `variant` in {ha_typ_cross, svesc, hacolt, zlrb_pctb,
  vol_band}; disabled.
- Features: `ha_open`, `ha_close`, `ha_high`, `ha_low` (recursive per symbol, seeded haOpen_0 = (O_0+C_0)/2), `hlc3`,
  `ema_hlc3_n`, `ema_ha4_n`, prev-value copies for crosses.
- Entry: signal on close t, next-open fill at real price. Stop (engine-chosen): min(haLow over last 3 bars) - 0.1*atr_14.
- Target: reference `target_r` = 4.0; exit by rule via `should_exit` (opposite cross on bearish bar / SVESC exit rule).
- max_hold_days: 40; min_reward_risk param 1.0.
- Reuses `ema`, `atr_14`, `sma`. Missing: HA columns (shared with heikin_ashi_trend_ride), TEMA/DEMA helpers.

## What the router should know
Trend-following, healthy_uptrend only. Expect high overlap with supertrend_flip_strategy and heikin_ashi_trend_ride.

## Signs of decay to monitor
Median hold < 3 bars; more than half of exits within 1R of entry.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/E-K/HACOLTStrat
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/R-S/SVEHaTypCross
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/R-S/SVESC
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/R-S/SVEZLRBPercBStrat
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/T-Z/VolatilityBand

## Empirical (replay)
_Pending: filled in from swing replay on real data._
