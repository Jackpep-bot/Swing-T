---
slug: oscillator_cross_family
name: Classic oscillator cross strategies (RSI 30/70, stochastic 20/80, %R, MACD signal/zero, PMO, DMI osc, momentum rising, Spectrum Bars)
originators: [thinkorswim built-ins, TradeStation built-ins, TradingView built-ins; indicators by Wilder (RSI, DMI), Lane (stochastic), Williams (%R), Appel (MACD), Swenlin (PMO), Kraut (Spectrum Bars)]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [2, 20]
timeframe: daily
direction: long_only_in_engine (originals are long and short, several stop-and-reverse)
regimes_good: [choppy]          # oversold-cross variants; momentum variants prefer healthy_uptrend
regimes_bad: [high_vol_selloff, correction]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: none
free_data_ok: true
status: not_built
---

# Classic oscillator cross family

## One-line summary
Textbook "oscillator crosses a level or its signal line" entries shipped as demo strategies by brokers; implemented only as
**negative-control baselines** for replay.

## Origin and lineage
Demonstration strategies in thinkorswim (MACDStrat, RSIStrat, Stochastic, PMOStrat, MomentumLE, SpectrumBarsLE),
TradeStation (MACD LE, RSI LE, Stochastic Slow LE, PercentR LE, Momentum LE, DMI Oscillator LE) and TradingView
(MACD/Momentum/RSI/Stochastic Slow Strategy). None ships with performance claims.

## Exact rules (long side; shorts mirror)
| Variant | Entry | Exit (vendor) |
|---|---|---|
| `rsi_30_70` | RSI(14) crosses above 30 | RSI crosses below 70 (TS/TV reverse there) |
| `stoch_20_80` | slow %K(14,3) crosses above %D(3) while both < 20 | %K crosses below %D while both > 80 |
| `pct_r` (TS) | Williams %R(14), on 0-100 scale, rises from < 20 to > 62 (setup cancelled if it first exceeds 80) | mirror: from > 80 to < 38 |
| `macd_signal` (TS) | MACD(12,26) crosses above its 9-EMA signal | reverse cross |
| `macd_hist_zero` (TOS/TV) | MACD - signal crosses above 0 (identical to `macd_signal`) | crosses below 0 |
| `pmo` (Swenlin) | PMO crosses above its EMA signal (lengths user-set; Swenlin's usual 35/20/10 not verified here) | reverse cross |
| `momentum_rising` (TS/TV) | mom = close - close[12] > 0 and rising -> buy stop at high + 1 tick next bar | reverse condition |
| `dmi_osc` (TS) | (+DI - -DI)(10) crosses above 0 | crosses below 0 |
| `spectrum_bars` (Kraut) | close > close[n] (entry-only) | none given |
Entry is next open except `momentum_rising` (stop order above the signal bar's high). No stops, targets or sizing are taught.

## Why it should work
Oversold crosses bet on short-term reversal (liquidity provision to forced sellers); signal-line and momentum crosses bet
on continuation. The two halves contradict each other, which is why the family is a control, not a thesis.

## When it works and when it fails
Oversold variants make money in range-bound tape and get run over in persistent declines (2008, 2022). Momentum variants
whipsaw in ranges. Stop-and-reverse versions are always in the market, so drawdowns equal the instrument's.

## Parameters and sensitivity
Lengths 9-21, levels 20/80 or 30/70, smoothing 3. Very sensitive to level choice; do not tune.

## Evidence
- Vendor pages: no performance statistics (grade none).
- Aronson, *Evidence-Based Technical Analysis* (2007): 6,402 rules on the S&P 500 (1980-2005 per the book; not re-verified
  here) and none significant after the data-mining correction (catalog note).
- Short-horizon RSI(2) mean reversion is a different, better-documented setup (see `rsi2_meanrev`, methods doc 11);
  RSI(14) 30/70 is not.

## Common mistakes
Treating overbought as a sell in trends; using the cross without a trend filter; ignoring that MACD-signal and
histogram-zero are the same rule.

## Discretionary parts and how to make them mechanical
None; all rules are mechanical. Tick offsets -> $0.01.

## Implementation spec for swing-engine
- Module `strategies/oscillator_cross.py`, `@register("strategy")`, param `variant`; default `rsi_30_70`.
- Reuses rsi_14, macd, macd_signal, macd_hist, plus_di_14/minus_di_14 (period 14 not 10: flag), atr_14.
  Missing: stochastic, %R, PMO, momentum(12); compute in-module.
- Cross on close of t; entry next open. `momentum_rising` needs a **stop-entry order hook** (not in the backtester,
  which fills only at next open) - approximate as next-open entry if open > high[t], else skip, and flag it.
- Stop: entry - 2 x atr_14 (engine-required). Target: None; `should_exit` on the variant's exit condition.
  `max_hold_days`: 20. `min_reward_risk`: not applied.
- settings.yaml: `oscillator_cross: {enabled: false, shadow_only: true, variant: rsi_30_70}`.

## What the router should know
Noise-floor baseline next to `ma_crossover_family`. Never live.

## Signs of decay to monitor
Not an edge; use its replay statistics as the period's random-entry benchmark.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/L-P/MACDStrat
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/R-S/RSIStrat
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/L-P/PMOStrat
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/macd_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/rsi_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/stochastic_slow_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/percentr_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/momentum_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/dmi_oscillator_le_signal_.htm
- https://www.tradingview.com/support/folders/43000587406-built-in-strategies/

## Empirical (replay)
_Generated 2026-10-10 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 141 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1527 | 28 | 47% | -0.06 | -0.15 | 48% | -0.04 | -0.13 | 49% | +0.07 | -0.03 | 1.15 |
| correction | 339 | 1 | 42% | -0.04 | -0.17 | 70% | +0.33 | +0.20 | 73% | +0.83 | +0.70 | 5.48 |
| healthy_uptrend | 3465 | 148 | 49% | +0.01 | -0.08 | 44% | -0.05 | -0.14 | 38% | -0.09 | -0.18 | 0.83 |
| high_vol_selloff | 2619 | 17 | 55% | +0.09 | -0.01 | 67% | +0.30 | +0.20 | 50% | +0.16 | +0.06 | 1.37 |
| narrow_uptrend | 978 | 22 | 35% | -0.22 | -0.34 | 31% | -0.28 | -0.40 | 30% | -0.24 | -0.36 | 0.63 |
| **all** | 8928 | 216 | 49% | -0.00 | -0.10 | 51% | +0.05 | -0.04 | 45% | +0.04 | -0.06 | 1.08 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 6202 | 68 | 53% | +0.06 | -0.02 | 54% | +0.15 | +0.07 | 52% | +0.27 | +0.19 | 1.63 |
| correction | 2691 | 40 | 67% | +0.27 | +0.20 | 54% | +0.17 | +0.10 | 54% | +0.42 | +0.34 | 2.09 |
| healthy_uptrend | 9679 | 182 | 48% | -0.03 | -0.11 | 45% | -0.04 | -0.13 | 40% | -0.06 | -0.15 | 0.89 |
| high_vol_selloff | 13429 | 362 | 49% | -0.03 | -0.12 | 50% | +0.04 | -0.05 | 48% | +0.09 | +0.00 | 1.21 |
| narrow_uptrend | 4288 | 79 | 49% | +0.00 | -0.08 | 47% | -0.00 | -0.08 | 45% | +0.03 | -0.05 | 1.06 |
| **all** | 36289 | 731 | 51% | +0.01 | -0.07 | 49% | +0.04 | -0.04 | 47% | +0.10 | +0.01 | 1.22 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
