---
slug: ehlers_dsp_family
name: Ehlers DSP indicators and strategies (roofing filter, super smoother, onset trend, universal/elegant oscillator, reverse EMA)
originators: [John F. Ehlers (S&C articles 2014-2015; books incl. Cycle Analytics for Traders, 2013), thinkorswim built-ins]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [2, 15]
timeframe: daily
direction: long (sources include shorts; engine long-only)
regimes_good: [healthy_uptrend, choppy]
regimes_bad: [high_vol_selloff, correction]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Ehlers DSP family

## One-line summary
Signal-processing filters (high-pass, super smoother, roofing) turned into oscillators, traded on zero-line or threshold crosses
in either trend or "predictive" (reversal) mode. One module, `variant` parameter; the filters also serve as features.

## Origin and lineage
John F. Ehlers, an engineer who applied aerospace filter design to price series (Rocket Science for Traders 2001, Cybernetic
Analysis 2004, Cycle Analytics for Traders 2013, and many S&C articles). The thinkorswim strategies cite: "Predictive Indicators
for Effective Trading Strategies" (S&C Jan 2014, EhlersStoch), "Whiter is Brighter" (S&C Jan 2015, Universal Oscillator), and a
quotient-transform article (Onset Trend; full citation truncated in the catalog). IFT-Stoch in the same thinkorswim list is a
Vervoort article (Dec 2011), not Ehlers.

## Exact rules (thinkorswim descriptions)
Core filters (matches Ehlers' published EasyLanguage; verified 2026-10-07 against https://www.linnsoft.com/topic/super-smoother-and-roofing-filter):
- Super smoother(x, P): a = exp(-1.414*pi/P); b = 2a*cos(1.414*pi/P); c2 = b; c3 = -a^2; c1 = 1 - c2 - c3;
  f_t = c1*(x_t + x_{t-1})/2 + c2*f_{t-1} + c3*f_{t-2}.
- 2-pole high-pass(x, P): alpha = (cos(0.707*2pi/P) + sin(0.707*2pi/P) - 1) / cos(0.707*2pi/P);
  hp_t = (1-alpha/2)^2*(x_t - 2x_{t-1} + x_{t-2}) + 2(1-alpha)hp_{t-1} - (1-alpha)^2 hp_{t-2}.
- Roofing filter = super smoother(high-pass(close, 48), 10) (typical defaults 48 / 10).
Strategies:
1. EhlersStoch: stochastic of the roofing-filtered series over `length`; conventional mode buys on cross above oversold, sells on
   cross below overbought; predictive mode inverts the crosses.
2. OnsetTrend: roofing + super smoother, automatic gain control, then quotient transform with K; two copies K1 = 0.8 and K2 = 0.4.
   Buy when the K1 line crosses above 0; sell to close when the K2 line crosses below 0.
3. UniversalOscillator: super-smoothed "whitened" (two-bar difference) price with AGC; trend mode buys zero-line up-crosses,
   reversal mode buys down-crosses.
4. ReverseEMA: two Z-transform "reverse EMA" lines (trend length, cycle length); buy when the short line crosses above 0 while the
   long line > 0; sell when either goes below 0.
5. SimpleROC: zero-cross of an averaged 2-bar momentum ROC (optionally via FM demodulator).
6. ElegantOscillator: inverse-Fisher of RMS-normalised, super-smoothed price; buy at a valley below -threshold, sell at a peak
   above +threshold.
- Entry next bar open. No stops, targets or sizing taught.

## Why it should work
Claimed: less lag and less noise than conventional averages, so turns are caught earlier. Mechanically these are band-pass
oscillators: in trend mode they are short-horizon momentum, in predictive/reversal mode short-horizon mean reversion. The
counterparty is the same as for RSI-2 (reversal mode) or breakout (trend mode); the filter itself adds no new source of return.

## When it works and when it fails
Reversal modes do best in range-bound, mean-reverting tapes; trend modes in steady trends. Both fail at regime switches,
because the filters assume a dominant cycle length (10-48 bars) that may not exist in a given stock.

## Parameters and sensitivity
High-pass cutoff (30-60), smoother (8-20), K (0.2-0.9), thresholds, mode. Mode doubles the trial count. Register variants x modes
as separate trials (at least 8) for the deflated Sharpe.

## Evidence
Ehlers' articles show in-sample examples, mostly on index futures; no broker statistics; no independent peer-reviewed test of
these specific strategies found. Grade D.

## Common mistakes
Warm-up: recursive filters need about 2-3x the longest period before values are usable; mixing radian/degree conventions from
EasyLanguage code (Ehlers uses degrees in cos/sin); treating predictive mode as trend following.

## Discretionary parts and how to make them mechanical
None in rules; formulas for AGC, quotient transform and reverse EMA must be ported from the thinkorswim/Ehlers source and unit-
tested against a published reference series.

## Implementation spec for swing-engine
- Feature module `features/dsp.py`: `ehlers_hp_48`, `ehlers_ss_10`, `roof_48_10`, `roof_stoch_20`, `onset_k08`, `onset_k04`,
  `universal_osc`, each with `_prev`. Pure recursive numpy per symbol; drop the first 100 bars (warm-up).
- Strategy `strategies/ehlers_dsp.py`, registered `ehlers_dsp`, params `variant`, `mode` (trend|reversal); disabled.
- Entry on signal close, next-open fill. Stop: trend mode = min(low, 10 bars) - 0.1*atr_14; reversal mode = entry - 2*atr_14.
- Target: trend mode reference `target_r` 3.0; reversal mode `target_r` 1.5. Rule exit via `should_exit` per variant.
- max_hold_days: 15 (reversal 7). min_reward_risk param 1.0.
- Reuses `atr_14`. Missing: all DSP features.

## What the router should know
Reversal-mode variants behave like rsi2_meanrev (choppy/uptrend); trend-mode like trend followers (healthy_uptrend). Route them
separately by mode.

## Signs of decay to monitor
Signal frequency drifting sharply (dominant cycle changed); reversal mode losing in low-vol regimes.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/E-K/EhlersStoch
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/L-P/OnsetTrend
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/T-Z/UniversalOscillatorStrat
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/R-S/ReverseEMAStrat
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/E-K/ElegantOscillatorStrat
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/E-F/EhlersRoofingFilter
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/studies-library/E-F/EhlersSuperSmootherFilter

## Empirical (replay)
_Pending: filled in from swing replay on real data._
