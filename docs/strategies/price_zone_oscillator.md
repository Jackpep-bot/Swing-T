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
_Generated 2026-10-13 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. `vs SPY` is the net R minus what SPY returned over the same days on the same dollars (beta 1, dividends ignored): the leaderboard's yardstick. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 7847 | 102 | 54% | +0.06 | -0.05 | -0.24 | 51% | +0.09 | -0.02 | -0.32 | 50% | +0.23 | +0.12 | -0.41 | 1.53 |
| correction | 921 | 13 | 57% | +0.10 | -0.14 | -0.51 | 58% | +0.15 | -0.09 | -0.63 | 56% | +0.30 | +0.06 | -0.84 | 1.82 |
| healthy_uptrend | 28824 | 321 | 48% | -0.01 | -0.12 | -0.14 | 44% | -0.03 | -0.15 | -0.16 | 38% | -0.01 | -0.13 | -0.18 | 0.99 |
| high_vol_selloff | 3787 | 91 | 54% | +0.04 | -0.09 | -0.13 | 51% | +0.08 | -0.05 | -0.12 | 39% | +0.02 | -0.11 | -0.14 | 1.03 |
| narrow_uptrend | 2962 | 41 | 36% | -0.19 | -0.31 | -0.20 | 34% | -0.25 | -0.37 | -0.21 | 27% | -0.28 | -0.40 | -0.36 | 0.60 |
| **all** | 44341 | 568 | 49% | +0.00 | -0.12 | -0.17 | 46% | -0.00 | -0.13 | -0.20 | 40% | +0.03 | -0.09 | -0.24 | 1.06 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | vs SPY 5d | win 10d | avg R 10d | net R 10d | vs SPY 10d | win 20d | avg R 20d | net R 20d | vs SPY 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 24945 | 296 | 53% | +0.04 | -0.06 | -0.14 | 52% | +0.09 | -0.01 | -0.17 | 47% | +0.16 | +0.06 | -0.20 | 1.33 |
| correction | 16759 | 133 | 54% | +0.05 | -0.05 | -0.11 | 53% | +0.12 | +0.02 | -0.10 | 48% | +0.15 | +0.05 | -0.10 | 1.33 |
| healthy_uptrend | 89279 | 1239 | 49% | -0.00 | -0.12 | -0.14 | 47% | +0.00 | -0.11 | -0.16 | 41% | +0.00 | -0.11 | -0.20 | 1.01 |
| high_vol_selloff | 19213 | 224 | 52% | +0.01 | -0.11 | -0.10 | 50% | +0.02 | -0.10 | -0.10 | 44% | +0.02 | -0.09 | -0.12 | 1.05 |
| narrow_uptrend | 19044 | 186 | 53% | +0.06 | -0.05 | -0.13 | 51% | +0.09 | -0.02 | -0.13 | 47% | +0.15 | +0.04 | -0.11 | 1.31 |
| **all** | 169240 | 2078 | 51% | +0.02 | -0.09 | -0.13 | 49% | +0.04 | -0.07 | -0.15 | 43% | +0.06 | -0.05 | -0.17 | 1.12 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
