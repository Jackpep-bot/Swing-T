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
_Pending: filled in from swing replay on real data._
