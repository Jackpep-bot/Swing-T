---
slug: bb_bullish_engulfing_kosinski
name: "Bollinger Bands with bullish engulfing (Pawel Kosinski)"
originators: ["Pawel Kosinski, 'Combining Bollinger Bands With Candlesticks', S&C October 2019", "thinkorswim BollingerBandsWithEngulfing"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [2, 15]
timeframe: daily
direction: long
regimes_good: [choppy, healthy_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Bollinger Bands + bullish engulfing (Kosinski)

## One-line summary
Buy a bullish engulfing candle that closes above the lower Bollinger Band, with an ATR stop, only if the distance to
the upper band is at least the minimum reward:risk; exit at the upper band or the stop.

## Origin and lineage
Pawel Kosinski, S&C October 2019 (article not read); coded by thinkorswim (catalog B25). Combines a band
mean-reversion location with a candlestick reversal trigger, and is unusual among S&C systems in having an explicit
reward:risk entry filter.

## Exact rules (thinkorswim reference, verified 2026-10-07)
- Buy when a bullish engulfing pattern closes above the lower Bollinger Band and reward:risk >= `reward risk ratio`.
- Stop price = current close - ATR x `atr factor`.
- Reward:risk = (upper band - high) / (high - stop), measured from the signal bar's high.
- Sell when the high reaches the upper band, or the low falls below the stop.
- Inputs: `length`, `num dev`, `atr factor`, `reward risk ratio`. Defaults: not stated on the reference page (one
  fetch summary suggested 1.0 for reward:risk; unverified). ATR length unverified.
- Engulfing definition used by thinkorswim (body-only vs body+shadow, prior bar bearish) not stated; this card uses
  the common body definition below.

## Why it should work
Near the lower band, sellers have pushed price to a statistical extreme; an engulfing bar shows buyers absorbed
them within one session. The R:R gate rejects trades where the band is too close to pay for the stop.

## When it works and when it fails
Works in ranges and orderly uptrends with band-to-band swings. Fails in trending declines (bands slide down, the
upper band target keeps falling) and when bands are narrow (R:R filter rejects most signals).

## Parameters and sensitivity
BB length 20 / 2 std (assumed defaults), ATR factor 1-3, min R:R 1-2. Candlestick definitions vary a lot between
sources; fix one. Trap: tuning the ATR factor together with R:R (they trade off directly).

## Evidence
Kosinski's article is an in-sample illustration; no broker statistics; no independent test found. Grade D. Academic
tests of candlestick patterns on US stocks are generally negative (e.g. Marshall, Young and Rose 2006 on DJIA stocks,
cited from memory; verify before relying on it).

## Common mistakes
Measuring reward to the band at entry time but letting the band move (the target is dynamic); counting tiny-bodied
engulfings; trading through earnings.

## Discretionary parts and how to make them mechanical
Engulfing definition: `close[t-1] < open[t-1]`, `close[t] > open[t]`, `open[t] <= close[t-1]`,
`close[t] >= open[t-1]`; optionally body[t] >= 0.5*atr_14 to drop tiny bars.

## Implementation spec for swing-engine
- Features: `prior_open`, `prior_close` (from `rows_as_of`), `open`, `close`, `high`, `bb_upper_20`, `bb_lower_20`,
  `atr_14`. Location: `close[t] > bb_lower_20[t]` and (engine reading of "at/through") `low[t] <= bb_lower_20[t]` or
  `low[t-1] <= bb_lower_20[t-1]`.
- Stop = `close[t] - atr_factor * atr_14` (atr_factor default 2.0, engine choice).
- Target = `bb_upper_20[t]` at signal time (reference). R:R as original:
  `(bb_upper_20 - high) / (high - stop) >= min_rr` (min_rr 1.0). Entry next open; `build_signal` recomputes R:R from
  entry, so also set `min_reward_risk` 1.0 there.
- Exit: stop intrabar; `should_exit` when `high >= bb_upper_20` on the current bar (dynamic band, rule exit);
  `max_hold_days` 15 (engine choice).
- Nothing missing; all columns exist.

## What the router should know
Mean-reversion family with a built-in R:R gate; overlaps `zscore_mean_reversion_garner` and `derrico_price_swing` type 2.
Allow where `rsi2_meanrev` is allowed; off in correction.

## Signs of decay to monitor
Share of signals hitting the upper band before the stop below ~45% at R:R >= 1; average bars to target lengthening.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/A-D/BollingerBandsWithEngulfing
- https://www.traders.com/Documentation/FEEDbk_docs/2019/10/TradersTips.html

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 463 | 2 | 43% | -0.06 | -0.16 | 43% | -0.08 | -0.18 | 46% | +0.05 | -0.05 | 1.10 |
| correction | 24 | 0 | 71% | +0.20 | +0.11 | 83% | +0.48 | +0.39 | 71% | +0.59 | +0.50 | 4.61 |
| healthy_uptrend | 841 | 7 | 53% | +0.05 | -0.05 | 48% | -0.00 | -0.10 | 44% | +0.03 | -0.06 | 1.06 |
| high_vol_selloff | 765 | 3 | 41% | -0.07 | -0.15 | 67% | +0.20 | +0.12 | 62% | +0.32 | +0.24 | 2.07 |
| narrow_uptrend | 245 | 1 | 40% | -0.19 | -0.29 | 34% | -0.33 | -0.44 | 36% | -0.26 | -0.36 | 0.59 |
| **all** | 2338 | 13 | 46% | -0.03 | -0.13 | 53% | +0.03 | -0.06 | 50% | +0.12 | +0.03 | 1.27 |

Portfolio replay (net of costs, slots shared with its run): 3 trades, win 33%, avg -0.57R, PF 0.17, P&L $-905 on $100k, avg hold 10.3 bars.

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1711 | 7 | 52% | +0.06 | -0.02 | 57% | +0.23 | +0.14 | 54% | +0.28 | +0.20 | 1.70 |
| correction | 1097 | 2 | 61% | +0.13 | +0.06 | 50% | +0.05 | -0.03 | 47% | +0.12 | +0.05 | 1.27 |
| healthy_uptrend | 2641 | 5 | 50% | +0.01 | -0.09 | 49% | +0.04 | -0.05 | 45% | +0.03 | -0.07 | 1.05 |
| high_vol_selloff | 2121 | 10 | 49% | -0.05 | -0.14 | 45% | -0.09 | -0.18 | 44% | -0.02 | -0.11 | 0.95 |
| narrow_uptrend | 1025 | 2 | 57% | +0.10 | +0.01 | 54% | +0.11 | +0.02 | 50% | +0.13 | +0.04 | 1.28 |
| **all** | 8595 | 26 | 52% | +0.03 | -0.06 | 50% | +0.06 | -0.03 | 47% | +0.09 | +0.00 | 1.19 |

Portfolio replay (net of costs, slots shared with its run): 39 trades, win 44%, avg +0.10R, PF 1.26, P&L $5,759 on $100k, avg hold 10.4 bars.
