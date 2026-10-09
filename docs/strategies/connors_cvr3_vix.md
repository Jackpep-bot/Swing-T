---
slug: connors_cvr3_vix
name: CVR3 VIX market timing
originators: [Larry Connors, Dave Landry (per StockCharts ChartSchool)]
category: market_timing_mean_reversion
decision: implement_disabled_for_comparison
holding_period_days: [2, 5]
timeframe: daily (VIX signal, trade SPY)
direction: long SPY on fear spikes (short on complacency in the original; engine long-only)
regimes_good: [choppy, narrow_uptrend, healthy_uptrend]
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: built_disabled
---

# CVR3 VIX market timing

## One-line summary
Buy SPY when the VIX is stretched at least 10% above its 10-day SMA (its whole bar above the average) but closes below
its open. Exit when the VIX falls back under the prior day's 10-day SMA, or after 2-4 days.

## Origin and lineage
ChartSchool credits the method to Larry Connors and Dave Landry. It belongs to the Connors "use the VIX, buy the fear" rule (*Short Term
Trading Strategies That Work*, 2008, rule 4 by chapter title). The catalog says the book has backtests for VIX
strategies. ChartSchool itself cites **no statistics and no book reference**, and which book table (if any) covers CVR3 specifically is
**unverified**.

## Exact rules (ChartSchool)
- **Buy SPY (all three, same day):** VIX low > VIX SMA(10); VIX close >= 1.10 * SMA(10) (PPO(1,10) >= 10); VIX
  close < VIX open (a black candle, so fear is fading intraday).
- **3-day window option:** the three conditions may occur within a 3-day window rather than on one bar (more signals).
- **Sell or short SPY:** VIX high < SMA(10); VIX close <= 0.90 * SMA(10); VIX close > VIX open.
- **Exit long:** VIX closes below the *prior day's* 10-day SMA, or a 2-4 day time exit. A Parabolic SAR on the S&P is
  optional.
- **Entry price:** not specified. Use the SPY close of the signal day, or the next open.
- **Stop:** none apart from the VIX-based exit. **Sizing:** not taught.

## Why it should work
VIX spikes mark forced de-risking: put buyers and liquidity demanders pay a premium. Nagel (RFS 2012) shows short-term
reversal returns rise with the VIX, so liquidity provision is paid most in turmoil. The close-below-open filter waits
for the first sign that the panic is easing.

## When it works and when it fails
It works on sharp, short pullbacks inside bull markets (one- to three-day VIX pops). It fails in sustained bear markets
(2008, early 2020, Apr 2025): the VIX stays more than 10% above its 10-day SMA for days, so signals repeat while SPY keeps falling.
The 10-day SMA then rises behind the spike, and a stop-free long is exposed to gap risk.

## Parameters and sensitivity
SMA length (10), stretch (10%), window (1 or 3 days), and exit (VIX < prior SMA vs N days). A 5% stretch roughly
doubles frequency (not measured here). Do not optimise the stretch on 2008 and 2020 alone; those two episodes dominate any fit.

## Evidence
- No numeric results were verified for CVR3 itself. The catalog grade C rests on Connors' backtests of VIX strategies in general and on broad
  documentation of VIX-spike mean reversion.
- Mechanism support: Nagel, "Evaporating Liquidity", RFS 25(7), 2012. Alpha Algo Trading Research (Mar 2026) found
  that adding a VIX filter to an E-mini RSI(2) system raised profit factor from 2.15 to 2.99 (in-sample, see methods/11).

## Common mistakes
- Using VIX close vs SMA only and forgetting the "low above SMA" and "close < open" filters.
- Using today's SMA in the exit instead of the prior day's.
- Trading the short side in a secular bull market without testing it separately.

## Discretionary parts and how to make them mechanical
Everything is mechanical. The only choice is the entry fill (SPY close vs next open). Test both.

## Implementation spec for swing-engine
- Data: VIX daily OHLC (CBOE publishes a free history CSV). It is **not in the store yet** and needs a reference series loader
  (shared with catalog item `vix_level_regime`). Point-in-time: VIX daily bars are final at 16:15 ET, so a signal is known at the
  SPY close only approximately. For backtesting, use the next SPY open, or SPY's 16:00 close if VIX bars are taken from 16:00.
- Features: `vix_sma_10`, `vix_ppo_10 = vix_close/vix_sma_10 - 1`, `cvr3_buy = vix_low > vix_sma_10 and vix_ppo_10 >= 0.10
  and vix_close < vix_open` (window variant: all three true at least once in the last 3 bars).
- Universe: SPY only (optionally QQQ/IWM). Entry: next open. Stop: catastrophic `entry - 3*atr_14` (not in the source).
- Exit: `vix_close < vix_sma_10[t-1]` or `bars_held >= 4`. `max_hold_days` 4. `min_reward_risk` 0.
- Built (2026-10-08): `swing_engine/strategies/connors_cvr3_vix.py`, `enabled: false` in config/settings.yaml. VIX data
  from `swing ingest-vix` (Cboe CSVs, `vix` table); `data.market_series.join_market_series` puts vix_open/high/low/close on
  every panel row; extras `vix_sma_10` / `prev_vix_sma_10`. `window` param 1 (default) or 3; long side only.

## What the router should know
It fires mostly when the regime classifier says `high_vol_selloff` or `correction`, where the playbook blocks most longs.
That is the point of the strategy, and the conflict should be resolved explicitly: shadow-run it in all regimes, then decide. Use tiny
size and SPY only.

## Signs of decay to monitor
Average 4-day SPY return after a signal near 0 over a rolling 20 signals. Signals clustering on consecutive days in
trends. Rising VIX-ETP flows that compress spikes (structural change in VIX dynamics).

## Sources
- https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/cvr3-vix-market-timing
- https://ideas.repec.org/a/oup/rfinst/v25y2012i7p2005-2039.html
- https://algotr.substack.com/p/this-simple-mean-reversion-strategy
- https://www.cboe.com/tradable_products/vix/vix_historical_data/ (CBOE VIX history page; URL not fetched this run)

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 8 | 0 | 38% | -0.11 | -0.20 | 62% | +0.02 | -0.06 | 50% | -0.08 | -0.17 | 0.82 |
| healthy_uptrend | 4 | 0 | 100% | +0.45 | +0.27 | 75% | +0.64 | +0.46 | 100% | +0.58 | +0.40 | inf |
| high_vol_selloff | 5 | 0 | 40% | -0.25 | -0.35 | 60% | +0.03 | -0.07 | 40% | -0.06 | -0.15 | 0.92 |
| narrow_uptrend | 2 | 0 | 100% | +0.35 | +0.22 | 50% | -0.05 | -0.18 | 0% | -1.00 | -1.12 | 0.00 |
| **all** | 19 | 0 | 58% | +0.02 | -0.09 | 63% | +0.15 | +0.03 | 53% | -0.03 | -0.14 | 0.94 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 20 | 0 | 55% | +0.20 | +0.11 | 75% | +0.43 | +0.34 | 75% | +0.60 | +0.51 | 3.86 |
| correction | 7 | 0 | 71% | +0.37 | +0.29 | 71% | +0.36 | +0.27 | 57% | +0.29 | +0.21 | 1.72 |
| healthy_uptrend | 16 | 1 | 57% | +0.07 | -0.02 | 64% | +0.18 | +0.09 | 57% | +0.14 | +0.05 | 1.34 |
| high_vol_selloff | 25 | 0 | 44% | -0.19 | -0.26 | 36% | -0.32 | -0.39 | 36% | -0.27 | -0.34 | 0.52 |
| narrow_uptrend | 10 | 0 | 70% | +0.12 | -0.01 | 60% | +0.24 | +0.11 | 50% | -0.03 | -0.16 | 0.93 |
| **all** | 78 | 1 | 55% | +0.05 | -0.04 | 58% | +0.10 | +0.02 | 54% | +0.12 | +0.03 | 1.28 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
