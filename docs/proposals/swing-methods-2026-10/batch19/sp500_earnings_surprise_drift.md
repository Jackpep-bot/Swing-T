---
slug: sp500_earnings_surprise_drift
name: Post-earnings drift in large caps - top 100 of the 500 largest by price-scaled seasonal EPS change from the latest filing, cap-weighted, quarterly after filing season
originators: [Ball & Brown (1968); Bernard & Thomas (1989, JAR); Livnat & Mendenhall (2006, JAR); Chen & Zimmermann EarnSupBig / EarningsStreak (seen in the premise library)]
category: strategy
decision: implement
holding_period_days: [63, 63]
timeframe: daily bars; mcap_pit; XBRL diluted EPS (avail_ts); quarterly rebalance
direction: long
universe: the 500 largest by mcap_pit, as-traded close >= $5
regimes_good: [any]
regimes_bad: [momentum_crash]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
weights_card: true
status: draft_card (research thread batch 19, 2026-10-14). WEIGHTS CARD. Earnings-surprise family, trial 2 (after batch 5's engine card double_surprise_smallmid). Bar alpha_t_critical(2).
---

# Post-earnings drift, large caps, as a weights book

## Why this card exists, and what was known when it was chosen
Earnings-surprise drift is the oldest anomaly with a live post-publication record. In the premise library, CZ's
EarningsStreak (t 3.5) and EarnSupBig (t 2.9) are among the strongest since 2017; those use analyst forecasts we do not
have and were seen on the overlapping window, so this card is **not** a copy of them and does not claim their numbers.
It uses the plain seasonal EPS change from filings, the version needing no analyst data. Our only earlier earnings
card (batch 5, `double_surprise_smallmid`) was a stop-sized engine card in small and mid caps with 351% turnover; this
one follows the scoreboard's profile instead: large caps, fully invested, cap weights, quarterly.

## Evidence
- Bernard & Thomas (1989): stocks with the highest standardised unexpected earnings drift up for about 60 trading days.
- Livnat & Mendenhall (2006): the drift persists for surprises measured from filings and from forecasts, weaker but
  present for large firms. Grade B: decades of evidence, decay after 2000 in large caps is the risk.

## Engine version (pre-register this one)
- Reference date: the last session of March, May, August and November (after 10-K season for December year-ends, and
  after 10-Q deadlines for the other quarters). Orders at the open of the next session.
- Universe: the 500 largest by `mcap_pit`, as-traded close >= $5.
- Latest quarter: the most recent 10-Q or 10-K with `avail_ts` on or before the reference date and within the last 100
  sessions; names without one are not eligible this round.
- Quarterly EPS: diluted EPS for the fiscal quarter. For a 10-K, Q4 EPS = full-year diluted EPS minus the three 10-Q
  quarters of that fiscal year; if any is missing, the name is not eligible this round.
- Surprise: (EPS this quarter - EPS same quarter a year earlier) / as-traded close on the reference date. Needs the
  year-earlier quarter; otherwise not eligible.
- Holdings: the 100 highest surprises, with a buffer: a holding stays while it ranks within the top 150 and is still
  eligible; new names fill from the top until there are 100.
- Weights: `mcap_pit`, each capped at 5% (excess spread pro rata), summing to 1; weights drift between rebalances.
- **Cash treatment:** fully invested. Unused weight (fewer than 100 eligible) is held in SPY. Before the first
  rebalance (March 2017) the book holds SPY.
- No stops. Delisted holdings exit at the last close x the store's delisting multiplier. Costs: `weights_book.simulate`
  with the per-symbol table (DEFAULT_COST_BPS = 10 bp where missing).
- Expected turnover, from the weighting rule and the signal: a fresh quarter's surprise reshuffles the ranking each
  time, unlike sticky signals (volatility, profitability), so about 50-70% of names change per rebalance even with the
  buffer, and cap weights concentrate the trades in large names. **200-300% a year one-way**; costs about 0.2-0.3% a
  year. Just under the scoreboard's 300% line; stated so a higher figure is read as the signal's churn, not a bug.

## Known limit
The signal is dated at the filing (`avail_ts`), usually 2-6 weeks after the earnings release, so the first part of
the drift is gone before the book can act; the reference dates add up to another few weeks. This biases the card
against itself and is the price of using only point-in-time filings.

## Grading (docs/gates.md: "Full-period test", "Bill rate")
Daily net returns vs SPY, alpha from (r - BIL) on (SPY - BIL). Windows A 2017-01-01 .. 2024-10-04 and B 2024-10-07 ..
2026-10-05, and the pooled window 2017-01-01 .. 2026-10-05 as one simulation.
PASS on either route: (1) in both A and B, haircut Sharpe > 0 and alpha vs SPY > 0 with alpha t >= the bar; or
(2) in the pooled window the same conditions, with alpha vs SPY above zero in each of A and B.
Trials: earnings-surprise family count 2. Bar: `alpha_t_critical(2)` = 2.241.
Beside the verdict, descriptive only: tracking error, the bottom-100 book under the same rules (does the spread exist
here at all?), and the correlation of monthly excess-of-SPY returns with `sp500_momentum_index_replica` (surprise and
price momentum overlap; a high correlation means little new).

## Expectation stated before the run
Large-cap drift after filing dates is small. Alpha about 0 to +2% a year, pooled alpha t under 1, correlation with the
replica about 0.4-0.6. Likely FAIL.
