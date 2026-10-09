---
slug: ma_crossover_family
name: Moving-average crossover family (price/MA, 2-line, 3-line, golden cross, VWMA/SMA, MHL MA, Breen bands, Webull 5/10/20)
originators: [Ken Calhoun (golden cross / VWMA breakouts), James Breen (TrendFollowingStrat), Vitali Apirine (MHL MA), thinkorswim / TradeStation / Webull / StockCharts built-ins, Brock-Lakonishok-LeBaron 1992 (academic test)]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [3, 120]
timeframe: daily
direction: long_only_in_engine (originals are stop-and-reverse long/short)
regimes_good: [healthy_uptrend]
regimes_bad: [choppy, correction, high_vol_selloff]
typical_win_rate: null   # no vendor publishes one; trend-following crossovers are usually below 45% winners (not verified for this family)
typical_payoff_ratio: null
evidence_grade: Neg
free_data_ok: true
status: not_built
---

# Moving-average crossover family

## One-line summary
Buy when a faster average (or price) crosses above a slower average and sell on the reverse cross; kept in swing-engine
only as a **negative-control baseline** for replay, never as a live trigger.

## Origin and lineage
- Classic technical-analysis rule; tested academically by Brock, Lakonishok and LeBaron (J. Finance 1992) on the DJIA
  1897-1986 with variable-length MA rules (short 1-5 days vs long 50-200 days, 0% or 1% band).
- Sullivan, Timmermann and White (J. Finance 1999) re-tested a 7,846-rule universe with White's Reality Check.
- Broker built-ins: thinkorswim GoldenCrossBreakouts and VWMABreakouts (Calhoun, S&C Mar/Feb 2017), TrendFollowingStrat
  (Breen, S&C Nov 2016), MovAvgStrat, MovAvgTwoLines, MiddleHighLowMA (Apirine); TradeStation MovAvg Cross/2Line/3Line;
  Webull Learn 5/10/20 MA swing course; StockCharts ChartSchool MA strategies (incl. Guppy ribbons).

## Exact rules (variants, as documented by vendors)
| Variant | Entry (long) | Exit (long) |
|---|---|---|
| `golden_cross` (Calhoun) | SMA(close,50) crosses above SMA(close,200) | close breaks below SMA(50) (or a trailing stop) |
| `vwma_sma` (Calhoun) | VWMA(close,50) crosses above SMA(close,70) | VWMA crosses back below SMA |
| `breen_band` | close >= 1.03 x MA | close <= 0.96 x MA (MA length/type user-set; not given) |
| `price_ma` (TOS MovAvgStrat / TS MovAvg Cross) | close crosses above SMA(9) (TS: stays above `ConfirmBars`=1) | close crosses below SMA(9) |
| `two_line` (TS MovAvg2Line) | SMA(9) crosses above SMA(18) | reverse cross |
| `three_line` (TS MovAvg3Line) | first bar with SMA(4) > SMA(9) > SMA(18) | order breaks (engine choice; TS reverses on 4<9<18) |
| `mhl_ma` (Apirine) | MA(close,n) crosses above MA((HH(m)+LL(m))/2, n); m = 3-15 for n<=50, 15-50 for n 50-200 | reverse cross |
| `webull_5_10_20` | MA5 crosses above MA10; conservative: wait until MA5 and MA10 both > MA20 | Sell1 MA5<MA10; Sell2 MA5<MA20; Sell3 MA5 and MA10 < MA20 = exit immediately |
- Entry order: all vendor versions act at next bar open (market). No initial stop or target in the originals; sizing not taught.
- Holding: until the reverse cross (days for 9/18, months for 50/200).

## Why it should work
Time-series momentum: trends persist because of under-reaction and herding, so a lagged average captures part of a
trend. Who is on the other side: mean-reversion traders and liquidity providers. In practice the lag gives back the
first and last part of every move and the rule whipsaws in ranges.

## When it works and when it fails
Works in long, low-volatility trends (2013-2014, 2017, 2021 style). Fails in ranges and V-shaped reversals
(2015-2016, 2018 Q4, 2022, Apr 2025) where every cross is late and reverses.

## Parameters and sensitivity
Fast 1-50, slow 9-200, band 0-4%, MA type (SMA/EMA/WMA/Hull). Thousands of combinations: the classic data-snooping trap.
Pick the published defaults above and do **not** tune; the variant exists to be beaten.

## Evidence
- BLL 1992: buy signals beat sell signals on the DJIA 1897-1986 in-sample (numbers in the paper; not re-checked here).
- STW 1999: BLL's in-sample result survives the snooping adjustment, but the best rule is insignificant out of sample
  1987-1996 (catalog: about 8.63%/yr before costs). No net edge after 1986.
- Bajgrowicz & Scaillet (JFE 2012): with false-discovery control and costs, technical rules on the DJIA show no
  persistent outperformance out of sample.
- Han, Yang & Zhou (JFQA 2013): MA timing adds value on high-volatility portfolios; a filter use, not a stock-entry use.
- Vendor S&C articles (Calhoun, Breen, Apirine): in-sample illustrations only (grade D). docs/methods.md 1a #16 and 1b:
  "Avoid as entries; use long MAs only as filters".

## Common mistakes
Optimising lengths on one index; ignoring costs on fast pairs (9/18 trades often); comparing to cash instead of buy-and-hold;
treating the golden cross as a timing signal (it fires weeks after the low).

## Discretionary parts and how to make them mechanical
Webull "wider post-cross separation = stronger" -> score = (MA5-MA10)/ATR14. "Confirm with RSI" -> rsi_14 > 50.
Breen MA length unspecified -> use 50-day SMA.

## Implementation spec for swing-engine
- Module `strategies/ma_crossover.py`, `@register("strategy")`, param `variant` in the table above; default `two_line`.
- Features reused: sma_10/20/50/200, ema_9/21, rsi_14, atr_14, trend_state. Missing: SMA(4/5/9/18/70), VWMA(50),
  MHL MA; compute inside the module from bars (or add `sma(n)` helper columns).
- Cross at bar t: `fast[t] > slow[t] and fast[t-1] <= slow[t-1]`, evaluated on the close; entry at next open (backtester default).
- Stop (engine-required, not in originals): entry - 2 x atr_14. Target: none (`target=None`), exit via `should_exit`
  on the reverse cross. `max_hold_days`: 60 for fast variants, 120 for golden_cross. `min_reward_risk`: not applied (no target).
- Long only (build_signal rejects shorts).
- settings.yaml: `ma_crossover: {enabled: false, shadow_only: true, variant: two_line}`.

## What the router should know
Negative control. Any strategy that cannot beat this baseline net of costs in replay is not adding value. Never route live orders.

## Signs of decay to monitor
Not applicable as an edge; monitor its replay Sharpe as the noise floor for the period.

## Sources
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/E-K/GoldenCrossBreakouts
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/T-Z/VWMABreakouts
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/T-Z/TrendFollowingStrat
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/L-P/MovAvgStrat
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/L-P/MovAvgTwoLinesStrat
- https://toslc.thinkorswim.com/center/reference/Tech-Indicators/strategies/L-P/MiddleHighLowMAStrat
- https://www.webullapp.com/learn/courseware/iNja32/Swing-Trade-with-MA?courseId=553Fb2
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/movavg_cross_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/movavg2line_cross_le_signal_.htm
- https://help.tradestation.com/10_00/eng/tradestationhelp/elanalysis/signal/movavg3line_cross_le_signal_.htm
- https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/moving-average-trading-strategies
- https://www.fmg.ac.uk/sites/default/files/2020-11/dp303.pdf
- https://researchonline.lse.ac.uk/id/eprint/119144
- https://ideas.repec.org:443/a/eee/jfinec/v106y2012i3p473-491.html

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 3345 | 10 | 56% | +0.12 | +0.01 | 51% | +0.11 | -0.00 | 46% | +0.19 | +0.08 | 1.41 |
| correction | 267 | 0 | 49% | -0.01 | -0.20 | 58% | +0.18 | -0.01 | 56% | +0.40 | +0.21 | 2.10 |
| healthy_uptrend | 12367 | 70 | 46% | -0.04 | -0.16 | 43% | -0.05 | -0.17 | 37% | -0.03 | -0.15 | 0.95 |
| high_vol_selloff | 2930 | 10 | 56% | +0.07 | -0.07 | 54% | +0.14 | -0.00 | 46% | +0.12 | -0.03 | 1.23 |
| narrow_uptrend | 1085 | 3 | 44% | -0.04 | -0.15 | 40% | -0.06 | -0.18 | 30% | -0.19 | -0.31 | 0.71 |
| **all** | 19994 | 93 | 49% | +0.01 | -0.12 | 46% | +0.01 | -0.11 | 40% | +0.03 | -0.09 | 1.05 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 10891 | 21 | 53% | +0.05 | -0.05 | 52% | +0.09 | -0.01 | 46% | +0.15 | +0.05 | 1.31 |
| correction | 6305 | 23 | 56% | +0.08 | -0.02 | 56% | +0.20 | +0.10 | 52% | +0.28 | +0.17 | 1.66 |
| healthy_uptrend | 43099 | 149 | 49% | +0.00 | -0.11 | 47% | +0.01 | -0.10 | 41% | +0.03 | -0.08 | 1.06 |
| high_vol_selloff | 14804 | 45 | 53% | +0.03 | -0.09 | 51% | +0.04 | -0.08 | 48% | +0.12 | -0.00 | 1.25 |
| narrow_uptrend | 10269 | 18 | 51% | +0.03 | -0.08 | 53% | +0.10 | -0.00 | 47% | +0.14 | +0.04 | 1.30 |
| **all** | 85368 | 256 | 51% | +0.02 | -0.09 | 49% | +0.05 | -0.06 | 44% | +0.10 | -0.02 | 1.18 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
