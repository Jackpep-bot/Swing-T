---
slug: heston_sadka_seasonality
name: Same-calendar-month return seasonality (Heston-Sadka)
originators: [Steven L. Heston, Ronnie Sadka]
category: strategy
decision: implement
holding_period_days: [15, 23]
timeframe: monthly (computed from daily bars)
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
status: not_built
---

# Heston-Sadka same-calendar-month seasonality

## One-line summary
Stocks that did well in a given calendar month in past years tend to do well in that same month again; rank stocks by
their average same-month return over prior years and use the rank as a monthly tilt or ranker feature.

## Origin and lineage
- Heston & Sadka, "Seasonality in the cross-section of stock returns", *Journal of Financial Economics* 87(2), 2008.
  NYSE/AMEX stocks, 1963-2002 (catalog).
- Replicated in Hou, Xue & Zhang, "Replicating Anomalies" (NBER w23394; *RFS* 2020) with value-weighting and NYSE
  breakpoints. Follow-ups (Keloharju, Linnainmaa & Nyberg, JF 2016, "Return seasonalities") extend it to factors and
  countries (named from memory, not fetched this run).

## Exact rules
- For the coming month m and stock i, compute the average of i's returns in calendar month m over a set of past years.
  HXZ's variants: lag 12 only (year 1), years 2-5, years 6-10, years 11-15, years 16-20.
- Sort into deciles at month end; go long the top decile (paper's long-short also shorts the bottom); hold one month;
  rebalance monthly.
- No stop, no target, no sizing beyond equal or value weights. Those are engine additions.

## Why it should work
Debated. Candidates: recurring firm-specific events (earnings announcement months, dividend months, fiscal-year
effects), persistent seasonal demand by investors (tax, window dressing), and seasonal exposure to priced risks.
Heston-Sadka argue it is not explained by size, industry, earnings-month or standard factors. The other side is
whoever trades on non-seasonal information in that month; the edge is small per stock and only shows in large
cross-sections.

## When it works and when it fails
- It is a cross-sectional effect: it ranks stocks relative to each other; it does not say the market goes up.
- Fails as a timing signal for individual trades (per-stock noise swamps a ~0.6%/month spread).
- In crashes, cross-sectional spreads are dominated by beta and liquidity, not seasonality.

## Parameters and sensitivity
| Knob | Published | Engine range | Notes |
|---|---|---|---|
| Lag set | 1; 2-5; 6-10; 11-15; 16-20 years | years 1-5 or 1-10 | Store holds 2016-01-04..2026-10-06 (~10.75 years), so years 11-20 are impossible. |
| Min years present | not stated here | >= 3 of the lag years | Rule needed to avoid one-observation averages. |
| Use | decile sort | ranker feature / tie-breaker | Catalog use: cheap tie-breaker. |
Overfitting trap: choosing the lag set by its in-sample IC on 10 years of data.

## Evidence
- Catalog (from HXZ, VW, NYSE breakpoints; not re-verified this run): high-minus-low monthly returns
  year-1 lag 0.65% (t=3.23), years 2-5 0.69% (t=4.0), 6-10 0.83% (t=4.91), 11-15 0.67% (t=4.66), 16-20 0.56% (t=3.29).
  Listed as an anomaly the q-factor model does not explain.
- Heston-Sadka: the annual-lag autocorrelation persists up to 20 years and survives size, industry and factor
  controls (catalog).
- Post-publication: no independent post-2008 decay estimate was located in this batch; treat as unknown.

## Common mistakes
- Using the current month's return in the average (look-ahead): only months strictly before as_of count.
- Survivorship: the 2016-2024 extension covers 4,770 names that were liquid in 2024 (docs/STATUS.md), which biases the
  early years. Report it.
- Treating a decile spread (long-short) as a long-only return.

## Discretionary parts and how to make them mechanical
None; fully mechanical.

## Implementation spec for swing-engine
- Feature `seas_same_month_y1_5` (new, `features/cross_section.py` or a new seasonality module): per symbol, monthly
  return r(y, m) = last adj_close of month / last adj_close of prior month - 1. For as_of in month M (or the last
  session of month M-1 when forecasting M), value = mean of r(Y-k, M) for k in 1..5 with >= 3 non-NaN, else NaN.
  Optional `seas_same_month_y6_10`.
- Cross-sectional rank `seas_rank` = percentile within the as-of session's universe.
- Use: add to `research/ranker.py::RANKER_FEATURES` (not there today) and as a score tie-breaker; no standalone
  strategy module. If replayed standalone: entry at the first session's open of the month for the top decile with
  `trend_state >= 0`, stop 2 x `atr_14`, no target, `max_hold_days` = sessions in the month (about 21), min
  reward:risk not applicable (time exit; set `min_reward_risk: 0`).
- Reuses: `adj_close`, the store's daily bars, `atr_14`, `trend_state`.
- Missing: monthly return aggregation, the feature itself, ranker inclusion.

## What the router should know
It is a tilt, not a setup. Never allow it to open trades in correction or high_vol_selloff on its own; let it reorder
candidates from setups the regime already allows.

## Signs of decay to monitor
- Monthly rank IC of `seas_rank` vs next-month return; rolling 36-month mean near zero or negative.
- Top-minus-bottom decile spread on the engine's universe falling below costs.

## Sources
- https://www.nber.org/system/files/working_papers/w23394/w23394.pdf
- https://www.rhsmith.umd.edu/news/seasonality-stock-market-returns

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 128 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| narrow_uptrend | 84 | 0 | - | - | - | - | - | - | - | - | - | - |
| **all** | 84 | 0 | - | - | - | - | - | - | - | - | - | - |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 1365 | 6 | 48% | +0.01 | -0.09 | 48% | +0.03 | -0.07 | 41% | +0.05 | -0.05 | 1.09 |
| correction | 777 | 2 | 71% | +0.42 | +0.31 | 68% | +0.54 | +0.43 | 57% | +0.51 | +0.40 | 2.33 |
| healthy_uptrend | 3205 | 20 | 48% | +0.01 | -0.09 | 44% | +0.03 | -0.07 | 38% | +0.03 | -0.07 | 1.05 |
| high_vol_selloff | 546 | 7 | 36% | -0.26 | -0.34 | 40% | -0.17 | -0.25 | 33% | -0.27 | -0.35 | 0.61 |
| narrow_uptrend | 862 | 3 | 50% | +0.03 | -0.06 | 54% | +0.21 | +0.12 | 35% | -0.13 | -0.22 | 0.79 |
| **all** | 6755 | 38 | 50% | +0.04 | -0.06 | 49% | +0.10 | -0.00 | 40% | +0.04 | -0.06 | 1.08 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
