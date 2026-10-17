---
slug: sp500_quality_index_replica
name: Replica of the S&P 500 Quality index rules (ROE, accruals, leverage) - top 100 of the 500 largest, cap x quality-score weights, semiannual
originators: [S&P Dow Jones Indices, S&P Quality Indices methodology; live ETF SPHQ (index since 2005 on these rules)]
category: strategy
decision: implement
holding_period_days: [126, 126]
timeframe: daily bars; mcap_pit; XBRL fundamentals; semiannual rebalance
direction: long
universe: the 500 largest by mcap_pit, as-traded close >= $10, >= 273 sessions of bars
regimes_good: [late_cycle, drawdowns]
regimes_bad: [junk_rally]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
weights_card: true
status: draft_card (research thread batch 15, 2026-10-14). WEIGHTS CARD. Profitability/quality family, counted as trial 3 (large_cap_gross_profitability in batch 3, the profitability leg of batch 14's composite, this card). Chosen knowing the scoreboard.
---

# S&P 500 Quality index replica

## Why this card exists, and what was known when it was chosen
The scoreboard's two best card-windows were the momentum replica (t 1.30) and large-cap gross profitability (t 1.43),
both in 2017-24, and its advice is fully invested, low-turnover large-cap tilts. The momentum replica worked best when
it copied a commercial index's rules exactly (weights by cap x score, caps, semiannual timing) rather than a homemade
equal-weight screen. This card does the same for quality: it copies the S&P 500 Quality index rules, which have run
live since 2005, onto our store. It was chosen knowing the profitability result, so it is counted as a further trial of
that family, not as a new family.

## Evidence
S&P Dow Jones Indices, "The S&P 500 Quality Index: attributes and performance drivers" (opened 2026-10-14): quality
score from balance-sheet accruals, ROE and financial leverage, z-scored and ranked, semiannual rebalance; the index beat
the S&P 500 by 3.3 points in the Feb-Apr 2020 drawdown. Long-run excess return is not stated on that page; grade C.

## Engine version (pre-register this one)
- Reference dates: the last session of May and November; orders at the open of the session after the third Friday of
  June and December (the index rebalances semiannually in June and December).
- Universe on the reference date: the 500 largest by `mcap_pit`, as-traded close >= $10, at least 273 sessions of
  bars, and the three inputs below available from filings with `avail_ts` on or before the reference date.
- Inputs (store deviations from S&P's definitions are stated):
  1. **ROE:** TTM net income / latest total equity (net income = TTM diluted EPS x cover-page shares, the batch-5
     proxy); names with equity <= 0 are dropped.
  2. **Accruals:** (TTM net income - TTM operating cash flow) / average of latest and year-ago total assets. S&P uses
     balance-sheet accruals (change in net operating assets); the store has no operating-liability detail, so this
     uses the cash-flow form (Hribar & Collins show the two rank firms similarly). Lower is better.
  3. **Leverage:** latest total assets / latest total equity (S&P uses total debt / book equity; the store has no debt
     line). Lower is better.
- Score: z-score each input within the universe (sign so higher = better quality), winsorise at +/-3, average the three,
  z-score again (Q).
- Holdings: the 100 names with the highest Q; buffer: a holding stays while ranked within the top 120; new names enter
  only within the top 80.
- Weights: `mcap_pit` x Q-score map s(Q) = 1 + Q for Q > 0 and 1 / (1 - Q) for Q <= 0 (the S&P factor-index mapping, as
  the momentum replica), normalised; each capped at 5% and at 3 x its cap weight in the universe (excess spread pro
  rata). Weights drift with prices between rebalances.
- **Cash treatment:** fully invested; unused weight and the period before the first rebalance (June 2017) held in SPY.
- No stops. Delisted holdings exit at the last close x the store's delisting multiplier.
- Expected turnover, from selection and weighting: quality scores are slow; about 15-25 names change per rebalance and
  weights reset twice a year: estimate 40-70% a year one-way; costs under 0.1% a year.

## Price-only data note
Price-only for both sides. Quality names pay somewhat more than average (S&P quotes a 2.2% yield in 2020), so
price-only grading slightly understates the book against SPY.

## Grading (docs/gates.md: "Full-period test", "Bill rate")
Daily net returns vs SPY, alpha from (r - BIL) on (SPY - BIL); windows A 2017-01-01 .. 2024-10-04, B 2024-10-07 ..
2026-10-05, and pooled 2017-01-01 .. 2026-10-05 as one simulation. PASS on either route (two halves, or pooled with
alpha above zero in each half). Trials: profitability/quality family count 3; bar `alpha_t_critical(3)` = 2.394.
Beside the verdict, descriptive only: tracking error; the book's correlation of daily excess returns with batch 9's
replica (to see whether the two forward-test candidates diversify each other); and SPHQ's own price return over the
same windows if SPHQ bars are in the store (price-only).

## Expectation stated before the run
Quality lagged in the 2020-21 junk rally and helped in 2022; leverage (assets/equity) penalises banks and buyback-heavy
firms with negative or thin equity. Pooled alpha about -1 to +2% a year, tracking error 4-6%, alpha t under 1. Likely
FAIL; most useful as a second forward-test candidate if it is weakly correlated with the momentum replica.
