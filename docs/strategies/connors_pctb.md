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
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 6867 | 4 | 45% | -0.04 | -0.13 | 44% | -0.06 | -0.16 | 46% | +0.07 | -0.02 | 1.15 |
| correction | 794 | 1 | 56% | +0.07 | -0.03 | 81% | +0.56 | +0.46 | 78% | +0.86 | +0.76 | 6.10 |
| healthy_uptrend | 11119 | 29 | 51% | +0.05 | -0.05 | 48% | +0.05 | -0.05 | 42% | +0.09 | -0.01 | 1.17 |
| high_vol_selloff | 2492 | 4 | 58% | +0.13 | +0.04 | 65% | +0.36 | +0.27 | 40% | +0.08 | -0.01 | 1.14 |
| narrow_uptrend | 3436 | 8 | 37% | -0.18 | -0.28 | 30% | -0.34 | -0.44 | 31% | -0.28 | -0.38 | 0.57 |
| **all** | 24708 | 46 | 49% | +0.00 | -0.09 | 47% | +0.02 | -0.07 | 43% | +0.07 | -0.03 | 1.13 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 16424 | 33 | 60% | +0.17 | +0.07 | 60% | +0.28 | +0.18 | 55% | +0.43 | +0.33 | 2.05 |
| correction | 4938 | 17 | 59% | +0.13 | +0.04 | 56% | +0.19 | +0.11 | 50% | +0.23 | +0.15 | 1.54 |
| healthy_uptrend | 35272 | 72 | 50% | -0.00 | -0.11 | 47% | +0.00 | -0.10 | 43% | +0.05 | -0.05 | 1.09 |
| high_vol_selloff | 11920 | 42 | 51% | -0.03 | -0.11 | 46% | -0.04 | -0.13 | 41% | -0.06 | -0.14 | 0.90 |
| narrow_uptrend | 12005 | 12 | 54% | +0.05 | -0.04 | 50% | +0.06 | -0.03 | 46% | +0.13 | +0.03 | 1.26 |
| **all** | 80559 | 176 | 53% | +0.04 | -0.05 | 51% | +0.07 | -0.02 | 46% | +0.13 | +0.04 | 1.27 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
