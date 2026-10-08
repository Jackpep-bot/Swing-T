---
slug: bollinger_band_mean_reversion
name: Bollinger band mean reversion (re-entry above the lower band)
originators: [John Bollinger (bands); broker built-ins - TradeStation BollingerBands LE/SE, thinkorswim BollingerBandsLE/SE, TradingView "Bollinger Bands Strategy", Webull Learn]
category: mean_reversion
decision: implement_disabled_for_comparison
holding_period_days: [2, 20]
timeframe: daily
direction: long (short mirror exists in the built-ins; engine is long-only)
regimes_good: [choppy, narrow_uptrend]
regimes_bad: [high_vol_selloff, correction]
typical_win_rate: null   # no published statistics from any of the platform sources
typical_payoff_ratio: null
evidence_grade: D
free_data_ok: true
status: not_built
---

# Bollinger band mean reversion

## One-line summary
After a close below the lower 20-day, 2-SD Bollinger band, buy when price crosses back above that band and
sell near the middle or upper band. It is a broker demonstration strategy with no published edge.

## Origin and lineage
John Bollinger published the bands in the 1980s. His own rules say a tag of a band is not a signal and a close outside
the bands is a continuation signal (bollingerbands.com, "Bollinger Band Rules"). The "re-entry" long and short entries
are platform demonstration strategies: TradeStation `Bollinger Bands LE/SE`, thinkorswim `BollingerBandsLE/SE`, and
TradingView's built-in "Bollinger Bands Strategy" and "...Directed". Webull's swing course teaches the range-market use.
So this card covers the generic broker rule. Bollinger's own reversal method is covered in `bollinger_w_bottom_ii_reversal.md`.

## Exact rules
- **Bands:** mid = SMA(close, 20); sd = std of close over 20 bars; lower = mid - 2*sd, upper = mid + 2*sd. Webull
  mentions 1.5 SD for very short trades.
- **Setup:** some recent bar closed (TradeStation: traded) below the lower band.
- **Trigger (TradeStation/TradingView):** the close crosses back above the lower band. A **buy stop** for the next bar is
  then placed at the lower band value. thinkorswim signals on the crossover itself.
- **Confirmation (Webull, discretionary):** a bullish engulfing bar or a double bottom at the lower band.
- **Initial stop:** none in the built-ins. They are stop-and-reverse or signal-only, and the opposite signal is the exit.
- **Target:** the mid band (conservative) or the upper band (Webull).
- **Time exit:** none in the source.
- **Sizing:** not taught.

## Why it should work
This is short-horizon liquidity provision: forced or impatient sellers push price two standard deviations below its 20-day
mean, and the buyer is paid for absorbing that flow (Nagel 2012 frames reversal returns this way). Waiting for the
re-cross is meant to avoid buying while the selling is still under way.

## When it works and when it fails
- Works in range-bound tapes and in pullbacks within uptrends when volatility is stable.
- Fails in trending declines. Bollinger's own rule says closes below the band are continuation signals, so a long that re-enters
  the band can be the start of a "walk down the band".
- Lento, Gradojevic and Wright (2007) found classic band rules did not beat buy-and-hold after costs. Contrarian
  versions did better, which is consistent with this rule being contrarian.

## Parameters and sensitivity
- Length 10-50 (default 20) and width 1.5-2.5 SD (default 2). A shorter length or narrower width gives more, noisier signals.
- The exit choice (mid or upper band) changes the payoff ratio a lot. Fix it before testing.
- Overfitting trap: tuning length, width and exit together on one index gives a 3-D grid. Log every combination in the trial log.

## Evidence
- Platform sources (TradeStation, thinkorswim, TradingView, Webull) publish no statistics. They are documentation or illustration only.
- Lento, Gradojevic & Wright, "Investment information content in Bollinger Bands?", Applied Financial Economics
  Letters 3(4):263-267, 2007 (DOI 10.1080/17446540701206576). After costs, BB rules failed to beat buy-and-hold, while the
  contrarian approach improved profitability. The markets and periods tested were not re-read in this run.
- No post-publication decay study was found.

## Common mistakes
- Treating a tag of the lower band as a buy. Bollinger explicitly says it is not one.
- Running the rule in downtrends without a trend filter.
- Using the band value at signal time as a fill price when the next open has already gapped above it.

## Discretionary parts and how to make them mechanical
- Webull's "bullish engulfing / double bottom" confirmation can be coded as: today's close is above the prior open, today's open is below the prior close,
  and the body engulfs the prior body. Or use the W-bottom rule from `bollinger_w_bottom_ii_reversal`.
- Ranging vs trending market: use `trend_state == 0` (flat) or `bb_width_20` below its 1-year median.

## Implementation spec for swing-engine
- Reuses `bb_lower_20`, `bb_upper_20`, `sma_20` (= mid), `sma_200`, `atr_14` and `trend_state`.
- Feature: `bb_reentry = close > bb_lower_20 and min(close - bb_lower_20 over the prior 1..N bars) < 0`, with N = 3
  (versioned constant `BB_REENTRY_LOOKBACK`).
- Entry: the backtester fills at the next open. The faithful version needs a **buy-stop-entry hook** (fill only if
  the next bar's high is at or above `bb_lower_20`, at max(open, level)). That hook does not exist yet (`research/backtest.py` `_fill_entry` uses the open).
  Interim: next open.
- Stop: no source stop, so use a catastrophic `entry - 2*atr_14`. Alternatively, the lowest low since the setup.
- Target: `sma_20` (mid band) as a close-based exit via `should_exit`, with the upper band as a variant. Set `max_hold_days` to 10.
- Set `min_reward_risk` to 0 (rule exit). Optional filter: `close > sma_200` (as in Connors' %b).
- Missing: the stop-entry order hook.

## What the router should know
Run it only in choppy or narrow-uptrend regimes, at reduced size. It overlaps heavily with `rsi2_meanrev` and
`connors_pctb`, so cap concurrent mean-reversion positions together.

## Signs of decay to monitor
Win rate under 55% over a rolling 40 trades. Average loss more than 2x the average win. Re-entries followed by new lows within 3 bars (falling-knife rate).

## Sources
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/bollinger_bands_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/bollinger_bands_se_signal_.htm
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/A-D/BollingerBandsLE
- https://www.tradingview.com/support/folders/43000587406-built-in-strategies/
- https://www.webullapp.com/learn/courseware/l5VtDs/Swing-Trade-with-Bollinger-Bands?courseId=553Fb2
- https://www.bollingerbands.com/bollinger-band-rules
- https://ideas.repec.org/a/taf/raflxx/v3y2007i4p263-267.html

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 4156 | 5 | 47% | -0.03 | -0.13 | 47% | -0.01 | -0.12 | 48% | +0.11 | +0.00 | 1.23 |
| correction | 429 | 0 | 48% | -0.04 | -0.18 | 59% | +0.18 | +0.04 | 56% | +0.34 | +0.20 | 2.08 |
| healthy_uptrend | 8755 | 20 | 53% | +0.07 | -0.04 | 48% | +0.03 | -0.08 | 43% | +0.05 | -0.06 | 1.09 |
| high_vol_selloff | 2860 | 3 | 54% | +0.07 | -0.03 | 65% | +0.31 | +0.22 | 49% | +0.20 | +0.10 | 1.44 |
| narrow_uptrend | 2072 | 3 | 33% | -0.25 | -0.36 | 25% | -0.43 | -0.54 | 23% | -0.44 | -0.55 | 0.39 |
| **all** | 18272 | 31 | 49% | +0.01 | -0.10 | 49% | +0.03 | -0.08 | 44% | +0.05 | -0.06 | 1.10 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 13342 | 35 | 57% | +0.14 | +0.04 | 58% | +0.26 | +0.16 | 54% | +0.44 | +0.34 | 2.09 |
| correction | 7258 | 24 | 61% | +0.19 | +0.10 | 54% | +0.13 | +0.05 | 51% | +0.31 | +0.23 | 1.72 |
| healthy_uptrend | 23632 | 55 | 49% | -0.01 | -0.12 | 46% | -0.02 | -0.12 | 41% | -0.02 | -0.13 | 0.96 |
| high_vol_selloff | 19969 | 340 | 48% | -0.04 | -0.14 | 46% | -0.04 | -0.13 | 42% | +0.00 | -0.09 | 1.00 |
| narrow_uptrend | 8950 | 12 | 53% | +0.05 | -0.05 | 51% | +0.07 | -0.04 | 48% | +0.12 | +0.02 | 1.26 |
| **all** | 73151 | 466 | 52% | +0.03 | -0.06 | 50% | +0.06 | -0.04 | 46% | +0.12 | +0.02 | 1.25 |

Portfolio replay (net of costs, slots shared with its run): 1 trades, win 100%, avg +0.05R, PF inf, P&L $46 on $100k, avg hold 1.0 bars.
