---
slug: earnings_seasonality
name: Earnings seasonality, buy the seasonally strong quarter before it reports (Chang-Hartzmark-Solomon-Soltes)
originators: [Chang, Hartzmark, Solomon & Soltes, "Being Surprised by the Unsurprising", RFS 30(1) 2017]
category: strategy
decision: implement
holding_period_days: [5, 25]
timeframe: daily bars + EDGAR quarterly EPS and earnings dates
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend, choppy]
regimes_bad: [high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
status: built_disabled (pre-registered 2026-10-09)
---

# Earnings seasonality

## One-line summary
Firms whose upcoming fiscal quarter has historically been their best quarter earn abnormal returns in the month they
announce it, because investors anchor on the most recent (seasonally weaker) quarters and are surprised by a
predictable seasonal jump. One position per firm per year, held around a known date.

## Origin and lineage
- Chang, Hartzmark, Solomon & Soltes, RFS 30(1) 2017. Peer-reviewed. Drafts read: NBER 2014
  https://www2.nber.org/conferences/2014/BEf14/Chang_Hartzmark_Solomon_Soltes.pdf and April 2015
  https://cba.lmu.edu/media/lmucollegeofbusinessadministration/responsivesite/2015_CCFC_chang_etal.pdf
  (published RFS tables not checked; numbers below are from the drafts).
- Same authors' family: `dividend_month_premium` (Hartzmark-Solomon). Engine relatives: `earnings_announcement_premium`
  (Frazzini-Lamont, every announcer), `heston_sadka_seasonality` (return seasonality, not earnings).
- No Chen-Zimmermann signal matches (checked SignalDoc.csv); gate-2 CZ check not possible.

## Exact rules (as published)
1. For the quarter t about to be announced, take quarterly EPS excluding extraordinary items, split-adjusted, for the
   20 quarters t-23 .. t-4; all 20 required.
2. Rank those 20 quarters from largest to smallest EPS.
3. EarnRank = average rank of quarters t-4, t-8, t-12, t-16, t-20 (the same fiscal quarter in each of the prior five
   years). A low average rank number = the coming quarter is historically strong (check sign when coding: the paper
   sorts so that the "high seasonality" quintile is the one whose same-quarter EPS ranked highest).
4. Expected announcement month = month of the announcement 12 months earlier. Sort expected announcers into quintiles
   of seasonality each month; buy the top quintile; hold through the announcement month.
5. Filters: common stock, price >= $5, market cap known at prior month-end.

## Engine version (pre-register this one)
- Entry: next open 5 sessions before the expected announcement date (EDGAR 8-K 2.02 date one year earlier, +/- 7
  days); exit at the close 2 sessions after the actual announcement, or 25 sessions after entry if none.
- Universe: price >= $5, 63-day median dollar volume >= $20M.
- Long the top seasonality quintile only (the effect is "driven by the long side").

## Why it should work
Investors weight the latest quarters, which for a seasonal firm are its weak ones, so the strong quarter surprises
even though it is the same as every year. The paper shows analysts make the same error.

## Evidence
- 2014 draft, Table II (1972-2013, monthly four-factor alphas in the announcement month, gross): high quintile
  0.653% EW (t=6.98) / 0.909% VW (t=6.03); low quintile 0.306% / 0.358%; high-minus-low 0.347% EW (t=3.13) / 0.551%
  VW (t=3.14). Raw announcement-month returns: high 1.75% EW / 1.76% VW vs low 1.46% / 1.37%.
- 2015 draft: announcement day about 10 bp (t=3.37); days t-2..t+1 top-minus-bottom quintile about 26 bp, deciles
  about 39 bp; little of it before the announcement. The next quarter's announcement (seasonally weak) has negative
  returns (t=-4.00): a quarterly cycle.
- No independent replication or post-2013 test found. No cost analysis in the paper.
- Grade B (peer-reviewed, gross, not replicated).

## Why it might beat costs where the others failed
One round trip per firm per year, timed to a known date, and the VW alpha (large firms) is larger than the EW one:
the edge sits in the liquid names where the engine's per-stock cost is lowest. The long leg alone carries it.
Risk: most of the window return is a few days around the announcement, so the per-trade edge is tens of bp; it
only clears costs in liquid names.

## Common mistakes
Using restated EPS or fiscal-period-end dates (look-ahead); trading the weak-season short leg (long-only engine,
and the paper says the long side drives it); using the actual announcement date to time entry (unknown in advance).

## Implementation spec for swing-engine
Pre-registered in `docs/preregistration/2026-10-09-three-picks.md` (section 3). Panel columns from `data.fundamentals` via `join_edgar`:
`earn_season` (EarnRank of the upcoming quarter from 23 consecutive XBRL diluted-EPS quarters, cached in
`fundamental_events`; rebuild that table on a store before replaying) and `sessions_to_expected_earnings` (8-K 2.02
reaction session 364 days earlier, rolled to a session). Module `strategies/earnings_seasonality.py`: top quintile of
-earn_season among liquid names expected within 21 sessions, signal 6 sessions before the expected date (fill 5
before), last report >= 25 sessions old; exit next open once `days_since_earnings` >= 2 for an announcement during the
hold, else 25 sessions; stop 3 x ATR(14); `engine_trail = False`. Settings: `earnings_seasonality: {enabled: false}`.
Tests: tests/test_strategy_three_picks.py.

## What the router should know
Event sleeve, small size; not regime-sensitive in the paper.

## Signs of decay to monitor
Trailing 8-quarter average excess return (vs SPY) of the top quintile in the window <= 0.

## Sources
- https://www2.nber.org/conferences/2014/BEf14/Chang_Hartzmark_Solomon_Soltes.pdf
- https://cba.lmu.edu/media/lmucollegeofbusinessadministration/responsivesite/2015_CCFC_chang_etal.pdf
- https://rpc.cfainstitute.org/research/cfa-digest/2017/06/being-surprised-by-the-unsurprising-earnings-seasonality-and-stock-returns-digest-summary

## Empirical (replay)
_Generated 2026-10-09 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 136 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 140 | 0 | 45% | -0.03 | -0.09 | 51% | +0.05 | -0.01 | 48% | +0.03 | -0.03 | 1.07 |
| correction | 5 | 0 | 60% | -0.14 | -0.35 | 80% | +1.16 | +0.95 | 60% | +1.39 | +1.18 | 4.14 |
| healthy_uptrend | 736 | 0 | 43% | -0.06 | -0.13 | 42% | -0.12 | -0.19 | 40% | -0.10 | -0.17 | 0.83 |
| high_vol_selloff | 155 | 0 | 68% | +0.17 | +0.08 | 63% | +0.20 | +0.12 | 63% | +0.33 | +0.24 | 2.36 |
| narrow_uptrend | 26 | 0 | 58% | +0.03 | -0.03 | 52% | +0.29 | +0.22 | 46% | +0.22 | +0.15 | 1.49 |
| **all** | 1062 | 0 | 48% | -0.02 | -0.09 | 47% | -0.04 | -0.11 | 44% | -0.01 | -0.08 | 0.99 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).

### 2017-01-01 .. 2024-10-04 (~4,300 names liquid in 2024 plus ~2,800 delisted names (Alpaca), repaired store)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 499 | 0 | 59% | +0.10 | +0.04 | 58% | +0.19 | +0.12 | 57% | +0.29 | +0.22 | 1.79 |
| correction | 385 | 0 | 60% | +0.09 | +0.02 | 57% | +0.18 | +0.11 | 58% | +0.26 | +0.19 | 1.72 |
| healthy_uptrend | 1798 | 2 | 51% | +0.02 | -0.05 | 50% | +0.05 | -0.02 | 46% | +0.06 | -0.01 | 1.11 |
| high_vol_selloff | 662 | 0 | 55% | +0.03 | -0.05 | 51% | -0.01 | -0.09 | 53% | +0.09 | +0.01 | 1.23 |
| narrow_uptrend | 374 | 0 | 62% | +0.10 | +0.03 | 59% | +0.21 | +0.14 | 56% | +0.26 | +0.19 | 1.71 |
| **all** | 3718 | 2 | 55% | +0.05 | -0.02 | 53% | +0.09 | +0.02 | 51% | +0.13 | +0.06 | 1.31 |

Portfolio replay: no trades taken (every signal lost the slot race or was skipped).
