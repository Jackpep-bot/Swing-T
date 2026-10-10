---
slug: faber_sector_rotation
name: "Faber sector rotation (top-3 sectors by 3-month ROC, 10-month SMA filter)"
originators: ["Mebane Faber, 'Relative Strength Strategies for Investing' (Cambria, 2010; SSRN 1585517)", "StockCharts ChartSchool (implementation)"]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [21, 90]
timeframe: monthly
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff, choppy]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C   # platforms row B, classic row C; C used (in-sample, no costs)
free_data_ok: true
status: not_built
---

# Faber sector rotation

## One-line summary
At each month-end, if the S&P 500 is above its 10-month SMA, hold the 3 sectors with the best 3-month return in equal
weight; otherwise hold cash.

## Origin and lineage
Mebane Faber, "Relative Strength Strategies for Investing" (April 2010), tested on the 10 Fama-French/CRSP industry
portfolios from the 1920s. Builds on industry momentum (Moskowitz & Grinblatt 1999) and Faber's own 10-month SMA
timing model ("A Quantitative Approach to Tactical Asset Allocation", 2007). ChartSchool publishes an ETF version.

## Exact rules
- Universe: 10 sectors. Faber: Fama-French 10 industries (NoDur, Durbl, Manuf, Enrgy, HiTec, Telcm, Shops, Hlth, Utils,
  Other). ETF proxy: the 11 Select Sector SPDRs (XLB, XLC, XLE, XLF, XLI, XLK, XLP, XLRE, XLU, XLV, XLY).
- Rank on month-end closes by total return over the lookback (default 3 months; Faber shows 1, 3, 6, 9, 12 all work).
- Hold top 3, equal weight (33% each). Rebalance monthly, replacing names that leave the top 3.
- Trend filter: invested only while the S&P 500 month-end close > its 10-month SMA (a 12-month SMA variant held trends
  better per ChartSchool); a month-end close below = exit everything to cash/T-bills.
- No stops inside the month, no targets. Orders at the next session after month-end (open or close; unspecified).

## Why it should work
Industry momentum: sectors trend over 3-12 months as information diffuses slowly and flows chase performance; the
trend filter avoids most of the deep bear markets where momentum and equities both suffer. Counterparty: slow
reallocators and mean-reversion value buyers.

## When it works and when it fails
- Works: sustained sector leadership (e.g. tech/energy cycles), long bear markets (filter moves to cash).
- Fails: fast rotations where 3-month leaders reverse; V-bottoms (filter re-enters late); momentum crashes after
  bear-market lows (Daniel-Moskowitz 2016); narrow markets where one sector dominates and the other two picks lag.

## Parameters and sensitivity
| Knob | Default | Range |
|---|---|---|
| lookback | 3 months | 1-12 months |
| top N | 3 | 2-4 |
| filter MA | 10 months | 10-12 months (or 200-day) |
| rebalance | monthly | monthly only (weekly raises turnover, untested) |
Trap: choosing the lookback with the best backtest; Faber's point is that all of 1-12 months worked.

## Evidence
- Faber (2010): relative strength portfolios beat buy-and-hold in about 70% of years over 80+ years, with persistence;
  in-sample, no costs, no taxes. Exact CAGR/drawdown figures not re-verified this run (SSRN PDF not read).
- Industry momentum: Moskowitz & Grinblatt (JF 1999). 10-month SMA filter: Faber 2007 (drawdown reduction);
  Zakamulin finds no significant outperformance in later out-of-sample windows, mainly lower risk.
- methods.md: sector/theme rotation as a stand-alone system rated C; recommended as a ranking input.

## Common mistakes
- Using price instead of total return; using ETFs with short histories (XLC 2018, XLRE 2015) without handling start dates.
- Trading mid-month on partial data; ignoring that the filter can keep you out for a year.

## Discretionary parts and how to make them mechanical
None; fully mechanical.

## Implementation spec for swing-engine
- Data: daily bars for the 11 sector ETFs + SPY (needs `universe.include_etfs: true` or a static sector list; not in
  the stock universe today).
- Features at month-end sessions: `ret_63d` (3-month), `spy_sma_10m = mean of the last 10 month-end SPY closes`;
  `filter_on = spy_month_close > spy_sma_10m`.
- Signal: on the last session of each month, if `filter_on`, target weights 1/3 on the top-3 `ret_63d`; else 0.
  Execute next open.
- Stop: none published; engine needs one for sizing, so run as a weight-based portfolio in replay, not via 1R sizing.
- max_hold_days: 31 per rebalance (positions can be rolled); min_reward_risk: 0.0.
- Reuses: `ret_63d`, market regime (SPY). Missing: ETF universe, month-end scheduler, weight-based (not risk-based)
  portfolio mode.
- Second use (cheaper, more relevant): publish `sector_rank_3m` and `sector_filter_on` as features so stock strategies
  can prefer names in top-3 sectors.

## What the router should know
Monthly allocation strategy, outside the swing horizon. Recommended as a sector-strength feature for the stock
strategies rather than an order-producing module.

## Signs of decay to monitor
Rolling 3-year excess return vs SPY and equal-weight sectors; turnover rising; top-3 picks lagging the next month.

## Sources
- https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/fabers-sector-rotation-trading-strategy
- https://papers.ssrn.com/abstract=1585517 (Faber 2010; abstract per search, PDF not read)
- https://www.cxoadvisory.com/?p=1115 ; https://papers.ssrn.com/abstract=2677212 (10-month SMA evidence, per catalog evidence.json)

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 136 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 18 | 0 | 53% | -0.08 | -0.16 | 47% | -0.14 | -0.21 | 60% | +0.16 | +0.09 | 1.44 |
| healthy_uptrend | 39 | 0 | 51% | +0.08 | +0.01 | 51% | +0.23 | +0.16 | 38% | +0.14 | +0.07 | 1.29 |
| high_vol_selloff | 3 | 0 | 0% | -0.06 | -0.19 | 67% | +0.19 | +0.06 | 100% | +1.12 | +0.99 | inf |
| narrow_uptrend | 3 | 0 | 100% | +1.37 | +1.25 | 100% | +1.64 | +1.51 | 100% | +2.59 | +2.46 | inf |
| **all** | 63 | 0 | 52% | +0.10 | +0.02 | 53% | +0.21 | +0.13 | 50% | +0.32 | +0.24 | 1.77 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 51 | 0 | 71% | +0.22 | +0.16 | 67% | +0.26 | +0.20 | 49% | +0.21 | +0.15 | 1.64 |
| correction | 3 | 0 | 33% | -0.53 | -0.58 | 0% | -0.75 | -0.80 | 0% | -1.00 | -1.05 | 0.00 |
| healthy_uptrend | 126 | 0 | 49% | -0.08 | -0.16 | 50% | -0.06 | -0.14 | 53% | +0.05 | -0.04 | 1.10 |
| high_vol_selloff | 18 | 0 | 61% | +0.21 | +0.14 | 72% | +0.25 | +0.18 | 61% | -0.09 | -0.16 | 0.74 |
| narrow_uptrend | 30 | 0 | 70% | +0.19 | +0.13 | 73% | +0.38 | +0.31 | 57% | +0.12 | +0.05 | 1.29 |
| **all** | 228 | 0 | 57% | +0.04 | -0.03 | 58% | +0.09 | +0.01 | 52% | +0.07 | -0.01 | 1.16 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
