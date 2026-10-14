---
slug: sp500_four_signal_composite
name: One S&P 500-style book blending momentum, gross profitability, net repurchases and value - top 100 by composite z, cap x score weights, monthly with a rank band
originators: [Asness, Moskowitz & Pedersen (2013, JF) "Value and Momentum Everywhere"; Novy-Marx (2013); Ikenberry-style repurchase evidence; research-thread survey "What winning trading programs do" (2026-10-14)]
category: strategy
decision: implement
holding_period_days: [21, 252]
timeframe: daily bars; mcap_pit; XBRL fundamentals; net_share_issuance; monthly rebalance
direction: long
universe: the 500 largest by mcap_pit, as-traded close >= $10, >= 273 sessions of bars
regimes_good: [any]
regimes_bad: [junk_rally]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
weights_card: true
status: draft_card (research thread batch 14, 2026-10-14). WEIGHTS CARD. A combination of four signals that were each tested alone before; counted against the largest family it uses (momentum, trial 5) and noted in the profitability and repurchase families.
---

# Four-signal composite, S&P 500-style

## Why this card exists, and what was known when it was chosen
The research scoreboard (42 cards) says every batch tested one signal at a time, the only card-windows with alpha t
above 1 were the momentum replica (1.30, 2017-24) and large-cap gross profitability (1.43, 2017-24), and the
profile that does least badly is a fully invested, low-turnover, large-cap weights book. The survey thread notes that
large quant firms earn their Sharpe by blending weak, partly unrelated signals: value and momentum are negatively
correlated, profitability is a quality tilt, repurchases a management signal. A blend can have a higher information
ratio than any part. This card was chosen **knowing** those results; the four signals are fixed from earlier cards,
weighted equally (no weights chosen from results), so the only new choice is the blend itself.

## Engine version (pre-register this one)
- Signal day: the last session of each month; orders at the next session's open.
- Universe: the 500 largest by `mcap_pit`, as-traded close >= $10, at least 273 sessions of bars.
- Four raw signals (point-in-time; fundamentals from filings with `avail_ts` on or before the signal day):
  1. **Momentum:** the batch-9 replica's score input: 12-1 return (close 21 sessions before over close 273 sessions
     before, minus 1) divided by the standard deviation of daily returns over the 252 sessions ending 21 sessions
     before.
  2. **Gross profitability:** TTM gross profit / latest total assets (missing where gross profit is not reported).
  3. **Net repurchases:** minus `net_share_issuance` (so a shrinking share count scores high).
  4. **Value:** `b5_book_to_market` (latest total equity / `mcap_pit`; missing when equity <= 0).
- Each signal is z-scored across the universe, winsorised at +/-3, then re-z-scored. Composite = the mean of the
  available z-scores; a name needs at least 3 of the 4. The composite is z-scored once more (Z).
- Holdings with a rank band: a name enters when its composite rank is 1-90; a holding stays while its rank is 1-120;
  the book holds 100 names, filling from the top.
- Weights: `mcap_pit` x s(Z), with s(Z) = 1 + Z for Z > 0 and 1 / (1 - Z) for Z <= 0 (the replica's mapping),
  normalised to 1, each capped at 9% and at 3 x the name's cap weight within the universe (excess spread pro rata).
  Weights are reset to target only when a name enters or leaves or when any weight is more than 25% away from its
  target, to keep turnover down.
- **Cash treatment:** fully invested; unused weight (fewer than 100 names) and the whole book before the first signal
  day (2017-01-31) are held in SPY.
- No book volatility target here (the second card in this batch tests scaling separately).
- No stops. Delisted holdings exit at the last close x the store's delisting multiplier.
- Expected turnover, from the weighting rule as well as the signals: the composite moves slower than momentum alone;
  with the 90/120 band about 4-6 names change a month (about 50-70% of names a year), plus partial re-weights.
  Estimate 80-150% a year one-way; costs about 0.1-0.2% a year.

## Price-only data note
Price-only for both sides. The value and repurchase tilts lean to above-average payers, so price-only grading slightly
understates this book against SPY.

## Grading (docs/gates.md: "Full-period test", "Bill rate")
Daily net returns vs SPY, alpha from (r - BIL) on (SPY - BIL); windows A 2017-01-01 .. 2024-10-04, B 2024-10-07 ..
2026-10-05, and the pooled window 2017-01-01 .. 2026-10-05 as one simulation.
PASS on either route: (1) in both A and B, haircut Sharpe > 0 and alpha vs SPY > 0 with alpha t >= the bar; or
(2) in the pooled window the same conditions, with alpha vs SPY above zero in each of A and B.
Trials: momentum family count 6 after this batch (replica, mid, small, industry-neutral, this card, the scaled
replica). Bar for both cards in this batch: `alpha_t_critical(6)` = 2.638.
Beside the verdict, descriptive only: the same rules with each single signal (four one-signal books), and the
pairwise correlations of the four signals' monthly top-minus-universe returns, to show whether the blend helped.

## Expectation stated before the run
Between the replica and SPY: value and repurchases dilute momentum's 2023-26 run. Tracking error 5-8% a year, pooled
alpha 0 to +3% a year, alpha t about 0.5-1.5. Likely FAIL on the 2.638 bar; the descriptive single-signal books will
say whether blending raised the information ratio, which matters for the forward test.
