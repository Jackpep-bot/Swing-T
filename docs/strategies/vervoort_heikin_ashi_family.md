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
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 136 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 4890 | 32 | 51% | +0.05 | -0.10 | 47% | +0.09 | -0.06 | 44% | +0.19 | +0.04 | 1.37 |
| correction | 555 | 4 | 47% | +0.03 | -0.28 | 50% | +0.19 | -0.12 | 48% | +0.34 | +0.03 | 1.73 |
| healthy_uptrend | 19530 | 102 | 46% | -0.00 | -0.15 | 41% | -0.04 | -0.19 | 34% | -0.04 | -0.19 | 0.94 |
| high_vol_selloff | 4713 | 66 | 56% | +0.11 | -0.07 | 51% | +0.18 | -0.01 | 41% | +0.16 | -0.03 | 1.28 |
| narrow_uptrend | 2250 | 17 | 35% | -0.19 | -0.33 | 33% | -0.22 | -0.36 | 24% | -0.29 | -0.44 | 0.60 |
| **all** | 31938 | 221 | 48% | +0.01 | -0.15 | 43% | +0.01 | -0.15 | 36% | +0.02 | -0.14 | 1.03 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 18123 | 91 | 50% | +0.06 | -0.08 | 49% | +0.13 | -0.00 | 45% | +0.23 | +0.10 | 1.43 |
| correction | 11739 | 42 | 50% | +0.04 | -0.10 | 47% | +0.12 | -0.02 | 41% | +0.16 | +0.03 | 1.29 |
| healthy_uptrend | 62490 | 301 | 46% | -0.00 | -0.15 | 42% | +0.01 | -0.15 | 36% | +0.00 | -0.15 | 1.01 |
| high_vol_selloff | 21790 | 94 | 50% | +0.04 | -0.11 | 48% | +0.06 | -0.08 | 43% | +0.10 | -0.04 | 1.20 |
| narrow_uptrend | 14614 | 46 | 50% | +0.05 | -0.09 | 46% | +0.07 | -0.07 | 42% | +0.14 | -0.00 | 1.26 |
| **all** | 128756 | 574 | 48% | +0.02 | -0.12 | 45% | +0.05 | -0.10 | 39% | +0.08 | -0.06 | 1.14 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
