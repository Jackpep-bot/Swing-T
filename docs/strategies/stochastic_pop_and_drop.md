---
slug: stochastic_pop_and_drop
name: Stochastic Pop (Bernstein, modified by Steckler/Hill)
originators: [Jake Bernstein, David Steckler, Arthur Hill (StockCharts ChartSchool)]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [2, 10]
timeframe: daily
direction: long (the "Drop" is the short mirror; long-only engine)
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Stochastic Pop

## One-line summary
In a stock with a bullish longer-term bias (70-period Stochastic above 50) that is consolidating (ADX(14) below
20), buy when the 14-day Stochastic surges above 80 on above-average volume. Stop below consolidation support and
exit when the 14-day Stochastic falls back below 50.

## Origin and lineage
- Jake Bernstein's original "Stochastic Pop" simply bought when the Stochastic surged above 80, treating
  overbought as strength.
- David Steckler added the ADX consolidation filter and the weekly-equivalent (70-day) Stochastic bias.
- ChartSchool (Arthur Hill) publishes the combined version.

## Exact rules
ChartSchool, fetched 2026-10-07.
- **Bias:** 70-period daily Stochastic (about a 14-week weekly) above 50 for longs, below 50 for shorts.
- **Setup:** ADX(14) below 20, meaning a consolidation or weak trend. Steckler preferred below 15. The catalog adds
  below 10 for low-volatility names; that figure was not on the fetched page.
- **Pop (long trigger):** the 14-day Stochastic surges above 80. Volume above its 250-day average. Consolidation
  breakouts are preferred. A big surge is better (e.g. from 35 to 85).
- **Drop (short):** mirror rules. The 14-day Stochastic plunges below 20 on high volume and/or breaks support.
- **Stop:** just below consolidation support or the prior trough.
- **Exit:** the 14-day Stochastic moves below 50, or a trailing stop such as Parabolic SAR.
- The page offers the setup as a starting point to be confirmed with chart patterns.
- The page does not say whether %K is fast or slow. It also gives no entry order type, target or sizing.

## Why it should work
A low ADX means volatility and trend have compressed. A sudden range-high close on heavy volume is a
volatility-expansion breakout, and the longer-term bias filter keeps it with the larger trend. The other side is
range traders selling "overbought" readings.

## When it works and when it fails
- **Works:** when a range resolves into a trend in an established uptrend.
- **Fails:**
  - In choppy tapes where ranges keep holding: the pop reverts and the Stochastic falls back below 50 quickly.
  - In high-volatility selloffs, where ADX is rarely below 20.

## Parameters and sensitivity
| Parameter | Value |
|---|---|
| `stoch_fast_n` | 14 |
| `stoch_bias_n` | 70 |
| `bias_min` | 50 |
| `adx_max` | 20 (15) |
| `pop_level` | 80 |
| `min_prior_k` | e.g. 50, to require a surge (engine choice; the page's 35 -> 85 is an example, not a rule) |
| `vol_avg_n` | 250 |
| `exit_level` | 50 |
| `support_lookback` | 20 bars (engine choice) |

Fast vs slow %K, and %K smoothing, change the signal count materially. Fix one before testing.

## Evidence
- Practitioner description only (catalog P51, grade D). ChartSchool states no performance figures.
- No independent test was found.
- `docs/methods.md` notes a different stochastic pullback strategy on SPY: 195 trades, 74% wins, PF 2.3. That is
  not this setup.

## Common mistakes
- Taking pops while ADX is already high (late-trend chasing).
- Ignoring the 70-day bias.
- Counting volume against a 20-day average instead of 250 days.
- Leaving the stop open when the exit rule (%K < 50) lags a fast reversal.

## Discretionary parts and how to make them mechanical
- **"Consolidation support"** = min(low) over the `support_lookback` bars before the pop, or `support_1` from
  `features/levels.py`.
- **"Prefer consolidation breakouts"** = close > max(high over `support_lookback` prior bars). This could be an
  optional filter.

## Implementation spec for swing-engine
**Features:**
- `stoch_k_14 = 100 x (close - min(low,14)) / (max(high,14) - min(low,14))` (fast %K; new)
- `stoch_k_70` (same formula with n = 70)
- `avg_vol_250_prev = mean(volume.shift(1), 250)`

**Signal:**
- `stoch_k_70 > 50` and `adx_14 < 20` (`adx_14` exists in patterns2)
- `stoch_k_14 >= 80` and `stoch_k_14.shift(1) < 80`
- `volume > avg_vol_250_prev`

**Orders:**
- Entry at the close, or next open.
- Stop = `min(low over prior 20 bars)` x 0.995 (engine choice), at most 3 x `atr_14` below entry.
- `should_exit` when `stoch_k_14 < 50`. No target. `min_reward_risk` 0.
- `max_hold_days` 10. A Parabolic SAR trail is not in the engine; the generic `execution.trail_after_r` stands in.

**Reuse:** `adx_14`, `atr_14`, `support_1`.

**Missing:** stochastic features, the 250-day volume average, and a SAR trail. Note that a 250-day warm-up removes
young listings.

## What the router should know
- It fires in low-ADX names, so it is closest in spirit to `momentum_burst` and `sr_breakout`.
- Allow it in uptrend regimes only, in shadow.
- Exit is rule-based, so treat it like `rsi2_meanrev` for the R:R floor.

## Signs of decay to monitor
- Median bars until %K < 50.
- Share of pops that close below the pop-day low within 3 bars.

## Sources
- https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/stochastic-pop-and-drop (fetched 2026-10-07)
- `docs/catalog/catalog.json` P51

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 228 | 0 | 59% | +0.12 | +0.03 | 62% | +0.23 | +0.13 | 60% | +0.28 | +0.19 | 2.01 |
| correction | 19 | 0 | 37% | -0.14 | -0.31 | 74% | +0.31 | +0.14 | 68% | +0.46 | +0.28 | 3.07 |
| healthy_uptrend | 912 | 4 | 51% | +0.03 | -0.06 | 48% | -0.01 | -0.10 | 49% | +0.08 | -0.01 | 1.19 |
| high_vol_selloff | 83 | 0 | 60% | +0.03 | -0.05 | 58% | +0.10 | +0.01 | 45% | -0.03 | -0.12 | 0.93 |
| narrow_uptrend | 75 | 0 | 51% | -0.07 | -0.17 | 52% | -0.01 | -0.11 | 25% | -0.35 | -0.46 | 0.41 |
| **all** | 1317 | 4 | 53% | +0.04 | -0.05 | 52% | +0.05 | -0.05 | 50% | +0.10 | +0.00 | 1.24 |

Portfolio replay (net of costs, slots shared with its run): 220 trades, win 38%, avg -0.08R, PF 0.74, P&L $-5,750 on $100k, avg hold 6.7 bars.

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 617 | 3 | 50% | +0.02 | -0.06 | 56% | +0.11 | +0.02 | 55% | +0.22 | +0.13 | 1.68 |
| correction | 397 | 1 | 62% | +0.10 | +0.01 | 60% | +0.16 | +0.07 | 57% | +0.21 | +0.12 | 1.69 |
| healthy_uptrend | 2373 | 3 | 52% | +0.03 | -0.06 | 51% | +0.06 | -0.03 | 49% | +0.09 | -0.00 | 1.21 |
| high_vol_selloff | 352 | 1 | 53% | +0.01 | -0.08 | 48% | -0.05 | -0.14 | 46% | -0.00 | -0.10 | 0.99 |
| narrow_uptrend | 500 | 2 | 55% | +0.07 | -0.01 | 56% | +0.09 | +0.00 | 55% | +0.19 | +0.10 | 1.56 |
| **all** | 4239 | 10 | 53% | +0.04 | -0.05 | 53% | +0.07 | -0.02 | 51% | +0.12 | +0.03 | 1.32 |

Portfolio replay (net of costs, slots shared with its run): 738 trades, win 43%, avg +0.03R, PF 1.12, P&L $22,011 on $100k, avg hold 7.2 bars.
