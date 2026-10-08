---
slug: connors_3day_high_low
name: Connors 3-Day High/Low (ETF)
originators: [Larry Connors, Connors Research (High Probability ETF Trading, 2009, strategy 1)]
category: mean_reversion
decision: implement_disabled_for_comparison
holding_period_days: [2, 6]
timeframe: daily
direction: long (short mirror below the 200-day; engine long-only)
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: not_built
---

# Connors 3-Day High/Low

## One-line summary
For an ETF above its 200-day SMA and below its 5-day SMA, after three straight days of lower highs and lower lows, buy
the close and exit on the first close above the 5-day SMA.

## Origin and lineage
This is strategy 1 of Connors' *High Probability ETF Trading* (2009), in the same family as RSI(2) and Double 7s (methods/11). It was tested by
the author on 20 liquid ETFs. EdgeRater replicated it. Quantified Strategies has a write-up, but it is paywalled and was not read.

## Exact rules
- **Universe:** liquid ETFs (Connors' 20: SPY, QQQ, IWM, EEM, GLD, sector SPDRs and others).
- **Setup:** close > SMA(200); close < SMA(5).
- **Trigger:** high[t] < high[t-1] < high[t-2] < high[t-3] AND low[t] < low[t-1] < low[t-2] < low[t-3] (three consecutive
  lower highs and lower lows). EdgeRater's text has a typo comparing today's high with the prior low. Use high vs high.
- **Entry:** market-on-close of the signal day.
- **Aggressive version:** add a second unit if the ETF closes below the entry price during the trade (**unverified**).
- **Stop:** none in the original. **Target:** none. **Exit:** first close > SMA(5).
- **Sizing:** not specified beyond the scale-in variant.

## Why it should work
The same as RSI(2): three days of one-way pressure in an uptrending, diversified ETF is usually flow, not news, and the
liquidity provider earns the bounce. ETFs rarely carry single-name event risk.

## When it works and when it fails
It works in bull markets with shallow pullbacks. It fails when the 200-day filter is still "on" at the start of a bear leg, which is the
first leg of a correction, and the no-stop hold rides it down.

## Parameters and sensitivity
Number of lower-high/low days (2-4), exit MA (5), and the trend MA (200). Requiring 4 days cuts signals sharply. Keep 3 as
taught. Do not sweep.

## Evidence
- EdgeRater (Connors' 20 ETFs, 1 Jan 1993 - 31 Dec 2008): mean 4-day forward return after entry **+0.547%** (SD
  2.87%) vs a baseline of all ETF days **+0.094%** (SD 3.48%). The difference is about 45 bp per 4 days (EdgeRater's page
  mis-states it as 480 bp). Costs are not included, there is no equity curve, and the period overlaps the book's own development window.
- No post-2009 out-of-sample test was verified.

## Common mistakes
Using next-open fills (part of the reversal is lost overnight). Applying it to single stocks with earnings gaps. Leaving out the
200-day filter.

## Discretionary parts and how to make them mechanical
None. It is fully mechanical.

## Implementation spec for swing-engine
- Belongs in the `rsi2_meanrev` family as a variant module (`connors_3day_hl`).
- Features: new `sma_5` (add 5 to `SMA_WINDOWS` in `features/indicators.py`; methods/11 already recommends this).
  `lhll_3 = all(high.diff() < 0 and low.diff() < 0 over the last 3 bars)`.
- Reuses `sma_200`, `atr_14`.
- Entry: the faithful version needs an **MOC / close-fill entry mode** (missing; the backtester fills at next open). Interim: next open,
  reported as a known handicap.
- Stop: catastrophic `entry - 2*atr_14` (engine safety, not in the source). Exit via `should_exit`: `close > sma_5`.
  `max_hold_days` 6. `min_reward_risk` 0.
- Universe: index and sector ETFs only (a config list).

## What the router should know
It is highly correlated with `rsi2_meanrev` signals on the same ETFs. Count them as one mean-reversion bucket. Same regime
map as `rsi2_meanrev`.

## Signs of decay to monitor
Rolling 30-trade mean return under +0.2% per trade. Mean hold rising above 5 days.

## Sources
- https://edgerater.com/blog/connors-etf-three-day-highlow-method
- https://quantifiedstrategies.substack.com/p/larry-connors-3-day-highlow-method (paywalled, not read)
- docs/methods/11-rsi2-connors-mean-reversion.md

## Empirical (replay)
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 4861 | 23 | 52% | +0.04 | -0.05 | 49% | +0.03 | -0.06 | 48% | +0.16 | +0.07 | 1.34 |
| correction | 406 | 0 | 43% | -0.09 | -0.21 | 70% | +0.33 | +0.22 | 71% | +0.87 | +0.75 | 4.77 |
| healthy_uptrend | 12061 | 29 | 52% | +0.09 | -0.01 | 49% | +0.11 | +0.01 | 42% | +0.10 | -0.00 | 1.18 |
| high_vol_selloff | 1736 | 7 | 58% | +0.14 | +0.04 | 58% | +0.30 | +0.19 | 43% | +0.13 | +0.03 | 1.24 |
| narrow_uptrend | 2139 | 4 | 42% | -0.10 | -0.20 | 33% | -0.27 | -0.37 | 33% | -0.20 | -0.30 | 0.70 |
| **all** | 21203 | 63 | 51% | +0.06 | -0.04 | 49% | +0.08 | -0.02 | 43% | +0.10 | +0.01 | 1.20 |

Portfolio replay (net of costs, slots shared with its run): 8 trades, win 38%, avg -0.29R, PF 0.39, P&L $-694 on $100k, avg hold 3.2 bars.

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 10881 | 19 | 58% | +0.13 | +0.04 | 57% | +0.25 | +0.15 | 51% | +0.32 | +0.23 | 1.73 |
| correction | 5136 | 14 | 54% | +0.06 | -0.03 | 50% | +0.06 | -0.03 | 45% | +0.07 | -0.02 | 1.15 |
| healthy_uptrend | 36167 | 84 | 49% | -0.00 | -0.10 | 47% | +0.01 | -0.09 | 42% | +0.06 | -0.04 | 1.11 |
| high_vol_selloff | 8925 | 48 | 43% | -0.14 | -0.23 | 40% | -0.17 | -0.26 | 33% | -0.20 | -0.29 | 0.68 |
| narrow_uptrend | 10393 | 16 | 55% | +0.08 | -0.02 | 52% | +0.10 | -0.00 | 44% | +0.09 | -0.00 | 1.18 |
| **all** | 71502 | 181 | 51% | +0.02 | -0.08 | 49% | +0.04 | -0.05 | 43% | +0.07 | -0.02 | 1.14 |

Portfolio replay (net of costs, slots shared with its run): 90 trades, win 48%, avg -0.20R, PF 0.56, P&L $-4,657 on $100k, avg hold 3.2 bars.
