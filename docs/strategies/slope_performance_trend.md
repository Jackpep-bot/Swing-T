---
slug: slope_performance_trend
name: "Slope Performance Trend (price and relative slopes)"
originators: ["StockCharts ChartSchool (no named originator)"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [60, 750]
timeframe: monthly (alternatives weekly 13-bar, daily 20-bar)
direction: long_short   # engine long side only
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [choppy, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: not_built
---

# Slope Performance Trend

## One-line summary
Be long while both the 12-month regression slope of price and the 12-month slope of its price relative (vs SPY) are
positive; be out when both are negative; hold the prior state when they disagree.

## Origin and lineage
ChartSchool trading-strategy article; no originator is named. It is a two-condition version of absolute (time-series)
plus relative (cross-sectional) momentum, the same idea as Antonacci's dual momentum, expressed with regression slopes.

## Exact rules (ChartSchool)
- Universe in the article: sector SPDRs, relative to SPY (e.g. XLK:SPY). Works on any symbol with a benchmark.
- Slope = slope of a linear regression of the series over the lookback (the article's worked example uses the simple
  rise-over-run (end - start) / periods to illustrate).
- Long-term: 12-month slope on monthly bars. Alternatives: 13-week slope (weekly), 20-day slope (daily).
- Buy: slope(price, 12m) > 0 AND slope(price/benchmark, 12m) > 0.
- Sell: both < 0. Mixed readings: no new signal (state persists).
- No stops, targets, sizing or time exits published. Signals evaluated on completed monthly bars.

## Why it should work
Requires both absolute uptrend and outperformance. Time-series momentum (Moskowitz-Ooi-Pedersen 2012) and
cross-sectional/industry momentum (Jegadeesh-Titman 1993; Moskowitz-Grinblatt 1999) are documented premia; the other
side is underreaction by slow investors and benchmark-hugging flows. The slope adds nothing proven beyond 12-month return.

## When it works and when it fails
- Works: multi-quarter sector trends; exits before long bear markets (article: XLY would have exited before 2008).
- Fails: sharp V reversals (monthly signals lag months), momentum crashes after bear-market bottoms (Daniel-Moskowitz
  2016), range years.

## Parameters and sensitivity
| Knob | Default | Range | Note |
|---|---|---|---|
| lookback | 12 months | 6-12 months; 13 weeks; 20 days | shorter = more whipsaw |
| benchmark | SPY | SPY / sector ETF | |
| slope type | OLS slope | OLS or normalized (slope / mean price) | normalize to compare across symbols |
Trap: swapping lookback per symbol; selecting the 20-day version for a "swing" fit then calling it the same system.

## Evidence
- ChartSchool: XLY over ~10 years (c. 2000s-2012): 5 signals, 1 whipsaw (2005). Illustrative, single example.
- Indirect: time-series and relative momentum literature above. No independent test of this exact rule found. Grade C
  because the underlying effects are well documented; the specific rule is not.

## Common mistakes
- Using unfinished monthly bars; using split-unadjusted prices for slopes.
- Treating "mixed" readings as exits (the article only exits when both are negative).

## Discretionary parts and how to make them mechanical
None material; it is fully mechanical. Only the "hold state when mixed" rule needs to be coded explicitly.

## Implementation spec for swing-engine
- Features (daily panel, no look-ahead): `rs_line = adj_close / spy_adj_close` (relative_strength_line, missing today);
  `slope_252 = OLS slope of adj_close over 252 sessions / mean(adj_close, 252)` (normalized);
  `rs_slope_252` same on rs_line. Swing variant: 63-day (13-week) and 20-day versions.
- Long entry: first session where both slopes > 0 after a state of "both < 0" (or flat start). Entry = next open.
- Stop: not published. Engine choice: 2.5 x atr_14 below entry (only as a catastrophic stop for sizing).
- Exit: both slopes < 0 (state flip). No target -> `min_reward_risk: 0.0`.
- max_hold_days: 252 for the 12-month version, 40 for the 20-day version.
- Reuses: `ret_252d`, `ret_63d`, `mom_12_1` as sanity checks. Missing: rolling OLS slope feature, SPY-relative line in
  the per-symbol panel, ETF universe (`universe.include_etfs: false` today).

## What the router should know
Too slow to be a swing entry on its own; the 20-day variant is the only swing-horizon form and is untested. Most
useful as a trend/RS state feature (filter for other long setups).

## Signs of decay to monitor
Whipsaw count per symbol-year, lag of exits vs 20% drawdowns, correlation with plain `ret_252d > 0` (if ~1, drop it).

## Sources
- https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/slope-performance-trend
- Moskowitz, Ooi & Pedersen (2012), JFE; Moskowitz & Grinblatt (1999), JF; Daniel & Moskowitz (2016), JFE (background)

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 136 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 181 | 0 | 53% | +0.03 | -0.06 | 51% | +0.01 | -0.08 | 47% | +0.09 | -0.01 | 1.20 |
| correction | 30 | 0 | 67% | +0.26 | +0.16 | 63% | +0.15 | +0.05 | 40% | -0.08 | -0.18 | 0.83 |
| healthy_uptrend | 709 | 2 | 44% | -0.08 | -0.16 | 43% | -0.11 | -0.20 | 39% | -0.12 | -0.20 | 0.79 |
| high_vol_selloff | 131 | 0 | 50% | -0.06 | -0.14 | 53% | -0.05 | -0.13 | 45% | -0.00 | -0.08 | 0.99 |
| narrow_uptrend | 65 | 0 | 35% | -0.19 | -0.29 | 40% | -0.23 | -0.34 | 26% | -0.32 | -0.43 | 0.46 |
| **all** | 1116 | 2 | 46% | -0.05 | -0.14 | 46% | -0.08 | -0.17 | 41% | -0.08 | -0.17 | 0.85 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 693 | 3 | 57% | +0.05 | -0.04 | 56% | +0.08 | -0.01 | 51% | +0.13 | +0.03 | 1.30 |
| correction | 391 | 3 | 57% | +0.06 | -0.03 | 58% | +0.09 | -0.01 | 52% | +0.10 | +0.00 | 1.26 |
| healthy_uptrend | 2242 | 6 | 49% | -0.01 | -0.09 | 49% | +0.02 | -0.07 | 46% | +0.05 | -0.04 | 1.10 |
| high_vol_selloff | 583 | 3 | 50% | -0.06 | -0.16 | 50% | -0.06 | -0.15 | 46% | -0.01 | -0.11 | 0.97 |
| narrow_uptrend | 450 | 1 | 50% | -0.05 | -0.13 | 48% | -0.02 | -0.10 | 47% | +0.04 | -0.04 | 1.10 |
| **all** | 4359 | 16 | 51% | -0.00 | -0.09 | 51% | +0.02 | -0.07 | 48% | +0.06 | -0.03 | 1.13 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
