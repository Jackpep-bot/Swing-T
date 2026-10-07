---
slug: price_zone_oscillator
name: Price Zone Oscillator strategies (Khalil & Steckler)
originators: [Walid Khalil, David Steckler ("Entering The Price Zone", S&C Jun 2011), thinkorswim PriceZoneOscillatorLE/LX/SE/SX]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [3, 30]     # estimate
timeframe: daily
direction: long_only_in_engine (original long and short)
regimes_good: [healthy_uptrend, choppy]
regimes_bad: [high_vol_selloff, correction]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Price Zone Oscillator (Khalil & Steckler)

## One-line summary
A signed-close oscillator with ADX/EMA regime switching: in uptrends buy recoveries from -40 or pushes through +15 after
crossing zero; exit on a +60 peak rollover or a break below the EMA with negative PZO.

## Origin and lineage
Khalil & Steckler, S&C Jun 2011, price-based companion of their Volume Zone Oscillator. thinkorswim implements four
strategies (LE, LX, SE, SX).

## Exact rules
- PZO = 100 x EMA(signed close, n) / EMA(close, n); signed close = +close if close > prior close else -close; n = 14
  (thinkorswim `length` also sets ADX(14)). Formula per LuxAlgo/traders.com summaries.
- Regime: ADX(14) > 18 = trending; direction from EMA(close, 60).
- Long entry, uptrend (ADX > 18 and close > EMA60): PZO crosses above -40, or crosses above +15 after having crossed zero upward.
- Long entry, non-trend (ADX < 18): PZO crosses above -40 or above +15.
- Long exit, trend: PZO above +60 then turns down; or close < EMA60 and PZO < 0.
- Long exit, non-trend: after dropping through +40, PZO rises above +60 and turns down; or after dropping through +40 it
  falls below 0 with close < EMA60; or after crossing +15 upward it fails to reach +40 and falls below -5.
- Shorts mirror (not used). No stops/targets/sizing. Entry next open.

## Why it should work
PZO measures how consistently closes are up; recoveries from deep negative readings in an uptrend are buy-the-dip
entries, and +15 crosses after a zero cross are early momentum entries. The ADX switch tries to choose between the two.

## When it works and when it fails
Trend-with-pullback markets. Non-trend mode buys every -40 recovery and suffers in persistent downtrends where ADX lags
below 18 while price grinds lower.

## Parameters and sensitivity
n 10-21, ADX threshold 15-25, EMA 40-100, levels +-40/+-60/+15/-5. Many levels and path conditions ("after crossing")
make state handling the main source of implementation error.

## Evidence
In-sample S&C illustration only (grade D). No independent test found.

## Common mistakes
Forgetting the "after crossing" state memory (it needs a small per-symbol state machine); treating "turns down" as a
2-bar drop (it is a 1-bar decline after the peak above +60).

## Discretionary parts and how to make them mechanical
"Turns down" -> PZO[t] < PZO[t-1] with max(PZO since last +60 cross) > 60. "After crossing zero" -> zero cross within
the last 10 bars (engine assumption).

## Implementation spec for swing-engine
- Module `strategies/price_zone.py`, `@register("strategy")`; new feature `pzo_14` and `ema_60` (neither exists).
- Reuses adx_14 (Wilder, 14, matches), atr_14, trend_state.
- Signal at close t from a vectorised state machine per symbol (flags: crossed_zero_up_recent, above_60_seen,
  dropped_through_40); entry next open.
- Stop: entry - 2 x atr_14. Target: None. `should_exit`: regime-appropriate LX rule above. `max_hold_days`: 30.
  `min_reward_risk`: not applied. Long only (uptrend and non-trend modes; skip ADX > 18 with close < EMA60).
- settings.yaml: `price_zone: {enabled: false, shadow_only: true, length: 14, adx_trend: 18, ema_length: 60}`.

## What the router should know
Comparison system with an internal regime switch; its trend/non-trend split is a useful second opinion on the router's
own regime labels.

## Signs of decay to monitor
Non-trend-mode trades with negative expectancy dominating the count; ADX regime flipping more than weekly.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/L-P/PriceZoneOscillatorLE
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/L-P/PriceZoneOscillatorLX
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/L-P/PriceZoneOscillatorSE
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/L-P/PriceZoneOscillatorSX
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/O-Q/PriceZoneOscillator
- https://www.traders.com/Documentation/FEEDbk_docs/2011/06/Khalil.html
- https://www.luxalgo.com/library/concept/price-zone-oscillator/

## Empirical (replay)
_Pending: filled in from swing replay on real data._
