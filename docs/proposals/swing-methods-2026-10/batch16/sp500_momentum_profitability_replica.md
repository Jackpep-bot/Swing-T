---
slug: sp500_momentum_profitability_replica
name: Batch 9's S&P 500 momentum-index rules with the score replaced by the average of momentum and gross-profitability z-scores (the premise-checked blend), semiannual
originators: [S&P Momentum Indices methodology (batch 9 rules); Novy-Marx (2013, JFE) "The other side of value"; Asness, Frazzini & Pedersen (2019) "Quality minus junk"; Ken French library premise check (batch 14)]
category: strategy
decision: implement
holding_period_days: [126, 126]
timeframe: daily bars; mcap_pit; XBRL gross profit and total assets; semiannual rebalance
direction: long
universe: as sp500_momentum_index_replica (the 500 largest by mcap_pit on the reference date)
regimes_good: [trend, late_cycle]
regimes_bad: [junk_rally, momentum_crash]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
weights_card: true
status: draft_card (research thread batch 16, 2026-10-14). WEIGHTS CARD. Momentum family trial 7 (bar 2.690); also profitability family. Chosen AFTER batch 14's results, including the descriptive single-signal books; stated below.
---

# Momentum + profitability, replica construction

## Why this card exists, and exactly what was known
- Batch 14's premise check (registered before it ran) found a 50/50 blend of French's big-stock high-momentum and
  robust-profitability portfolios earned CAPM alpha +1.92% a year with t 3.71 over 1963-2026, positive in every
  subperiod (t 2.46, 2.86, 1.14 from 2017), and our own books correlate 0.62 with it. That is the strongest long-run
  evidence any idea in this project has had.
- Batch 14's four-signal composite failed (pooled alpha t -0.35); its descriptive single-signal books showed value
  (-4.0% alpha) and repurchases (-0.4%) dragging it, gp_assets alone +2.3% (t 1.11), momentum alone +1.3% (t 0.34),
  and monthly re-weighting ran turnover to 310% a year.
- The batch 9 replica (semiannual, cap x score weights) remains the best implementation of momentum here (+4.9%,
  t 1.51 pooled, descriptive).

This card therefore uses the **two-signal blend the premise check tested** inside the **replica's construction**. Both
choices were made after seeing those results, so this is not independent evidence: it is counted as momentum-family
trial 7 with a higher bar, and if it does well its main use is as a forward-test candidate beside the shadowed replica.

## Engine version (pre-register this one)
Every rule of `docs/proposals/swing-methods-2026-10/batch9/sp500_momentum_index_replica.md` applies unchanged
(universe, reference dates end of February and August, rebalance after the third Friday of March and September,
100 names with the 80/120 buffer, weights mcap x s(score) with s = 1 + z for z > 0 and 1 / (1 - z) otherwise, caps of
9% and 3 x cap weight, next-open fills, no stops, history rule, delisting rule), except the score:
- m = the replica's momentum z-score (12-1 return over 12-month daily volatility, z-scored and winsorised at +/-3).
- g = gross profitability z-score: TTM gross profit / latest total assets from filings with `avail_ts` on or before
  the reference date, z-scored across the universe and winsorised at +/-3. Names without reported gross profit
  (mostly banks and insurers) get g = 0 (neutral), not excluded, so the universe matches the replica's.
- score z = z-score of (m + g) / 2 across the universe.
- **Cash treatment:** fully invested; before the first rebalance (March 2017) and for any unused weight, SPY.
- Expected turnover: the replica's semiannual turnover plus the slower-moving profitability leg, which should lower
  it. Estimate 60-120% a year one-way (half-yearly resets only, weights drift between); costs about 0.1% a year.

## Grading (docs/gates.md: "Full-period test", "Bill rate")
Daily net returns vs SPY, alpha from (r - BIL) on (SPY - BIL); windows A, B and pooled 2017-01-01 .. 2026-10-05 as one
simulation; PASS on either route. Trials: momentum family count 7; bar `alpha_t_critical(7)` = 2.690.
Beside the verdict, descriptive only: the correlation of daily excess returns with the batch 9 replica, tracking error,
and the monthly correlation with the French BIG HiPRIOR + BIG HiOP blend over 2017 onward (as the premise check).

## Expectation stated before the run
Between the replica and the gp-only book: pooled return about 16-19% a year, alpha +2 to +5%, tracking error lower
than the replica's because the two legs are only 0.20 correlated. Pooled alpha t about 1.2-2.0. Likely FAIL on the
2.690 bar; if alpha is above zero in both halves, it is the second forward-test candidate.
