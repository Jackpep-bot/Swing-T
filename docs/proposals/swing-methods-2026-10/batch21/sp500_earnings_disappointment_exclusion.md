---
slug: sp500_earnings_disappointment_exclusion
name: Cap-weighted 500 largest minus the 100 worst earnings surprises (avoid the short leg of post-earnings drift), quarterly after filing season
originators: [Bernard & Thomas (1989); Stambaugh, Yu & Yuan (2012) "The short of it"; batch 19 results (ae4d397)]
category: strategy
decision: implement
holding_period_days: [63, 63]
timeframe: daily bars; mcap_pit; XBRL diluted EPS (avail_ts); quarterly rebalance
direction: long
universe: the 500 largest by mcap_pit, as-traded close >= $5
regimes_good: [any]
regimes_bad: [junk_rally]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
weights_card: true
status: draft_card (research thread batch 21, 2026-10-14). WEIGHTS CARD. Earnings-surprise family, trial 3; chosen AFTER batch 19's results, said plainly below. Bar alpha_t_critical(3).
---

# Avoid the worst earnings surprises: large caps

## Why this card exists, and what was known when it was chosen
Batch 19 failed, but its descriptive bottom-100 book (the worst surprises, cap-weighted) made +8.2% a year against
+11.8% for the top 100 and +13.6% for SPY: the spread exists in large caps, and the bottom side carries it. The top
100 alone had high tracking error, 404% turnover and 1.13% a year of costs. This card keeps SPY-like exposure and only
**leaves out** the bottom 100, the batch-13 construction applied to the one signal whose short leg we have now seen
lag. It was chosen because of that result, so it is counted as the earnings family's third trial and the evidence
grade is C (the motivating number is in-sample).

## Engine version (pre-register this one)
Everything about the signal is batch 19's, unchanged:
- Reference date: the last session of March, May, August and November; orders at the open of the next session.
- Universe: the 500 largest by `mcap_pit`, as-traded close >= $5.
- Latest quarter: the most recent 10-Q or 10-K with `avail_ts` on or before the reference date and within 100
  sessions; Q4 EPS = full-year diluted EPS minus the three 10-Q quarters.
- Surprise: (EPS this quarter - EPS same quarter a year earlier) / as-traded close on the reference date.
What changes is the book:
- **Excluded:** the 100 lowest surprises among eligible names. Buffer: an excluded name returns only when it ranks
  above the 130th lowest; a held name is excluded only when it enters the lowest 100.
- Names with no eligible surprise this round are **kept** (not scored, not excluded).
- Weights: every remaining name at `mcap_pit` weight, each capped at 10% (excess spread pro rata), summing to 1;
  weights drift between rebalances.
- **Cash treatment:** fully invested; no cash, no SPY sleeve. Before the first rebalance (March 2017) the book holds
  SPY.
- No stops. Delisted holdings exit at the last close x the store's delisting multiplier. Costs: `weights_book.simulate`
  with the per-symbol table (DEFAULT_COST_BPS = 10 bp where missing).
- Expected turnover, from the weighting rule: batch 19's ranking churns most of the list each quarter, so about 60-70
  of the 100 excluded names change per rebalance, but they hold only about 10-20% of the cap weight, plus index changes
  and cap re-spreading. **50-120% a year one-way**; costs about 0.05-0.15% a year.

## Grading (docs/gates.md: "Full-period test", "Bill rate")
Daily net returns vs SPY, alpha from (r - BIL) on (SPY - BIL). Windows A 2017-01-01 .. 2024-10-04 and B 2024-10-07 ..
2026-10-05, and the pooled window 2017-01-01 .. 2026-10-05 as one simulation.
PASS on either route: (1) in both A and B, haircut Sharpe > 0 and alpha vs SPY > 0 with alpha t >= the bar; or
(2) in the pooled window the same conditions, with alpha vs SPY above zero in each of A and B.
Trials: earnings-surprise family count 3. Bar: `alpha_t_critical(3)` = 2.394.
Beside the verdict, descriptive only: tracking error, average weight excluded, the excluded names' cap-weighted return
against SPY, and total-return-store figures.

## Expectation stated before the run
If the excluded names lag SPY by about 5% a year and hold about 15% of the weight, the book gains about 0.7% a year
before costs, with tracking error about 2%. Pooled alpha t about 0.5-1.5. Likely FAIL on the bar; the useful read is
whether a low-tracking-error version keeps the spread that batch 19's top book lost to turnover.
