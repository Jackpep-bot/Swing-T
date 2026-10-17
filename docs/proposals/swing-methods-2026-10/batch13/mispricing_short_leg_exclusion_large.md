---
slug: mispricing_short_leg_exclusion_large
name: Cap-weighted 500 largest minus the worst fifth on a five-signal mispricing score (avoid the anomalies' short leg), quarterly
originators: [Stambaugh, Yu & Yuan (2012, JFE) "The short of it"; Stambaugh & Yuan (2017, RFS) "Mispricing factors"; Cooper, Gulen & Schill (2008, JF); Sloan (1996); Novy-Marx (2013)]
category: strategy
decision: implement
holding_period_days: [63, 63]
timeframe: daily bars; mcap_pit; XBRL fundamentals (fundamental_events, avail_ts); quarterly rebalance
direction: long
universe: the 500 largest by mcap_pit, as-traded close >= $5
regimes_good: [any]
regimes_bad: [speculative_rally]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
weights_card: true
status: draft_card (research thread batch 13, 2026-10-14). WEIGHTS CARD. New family (mispricing short-leg avoidance); trial 1 of 2 in the family (with the mid-cap card).
---

# Avoid the short leg: large caps

## Why this card exists
Every stock-picking book so far tried to find winners and ended up with beta near 1 and negative alpha against a
mega-cap-led SPY. Stambaugh, Yu & Yuan (2012) found that most of the return spread of well-known anomalies comes from
the **short** side: the stocks scored worst underperform, while the best-scored barely beat the market. A long-only
book cannot short them, but it can **leave them out**. This card holds the 500 largest stocks at cap weight, so it
keeps SPY's mega-cap exposure, and drops the worst fifth on a composite of five anomaly signals the store already has.
Its tracking error against SPY should be small, which is what a low-alpha edge needs to reach a usable t.

## Evidence
- Stambaugh, Yu & Yuan (2012): across 11 anomalies, the short leg's alpha is larger than the long leg's, especially
  after high-sentiment periods.
- Stambaugh & Yuan (2017): two composite mispricing factors (management: issuance, accruals, asset growth, investment;
  performance: profitability, distress, momentum) explain returns better than single signals.
- Single signals: asset growth (Cooper, Gulen & Schill 2008), accruals (Sloan 1996), net share issuance, gross
  profitability (Novy-Marx 2013), ROA. Grade B for the anomalies; their size since 2017 in large caps is the open
  question.

## Engine version (pre-register this one)
- Reference date: the last session of February, May, August and November. Orders at the open of the session after
  the third Friday of the next month (the batch-9 timing). Values use filings with `avail_ts` on or before the
  reference date only.
- Universe on the reference date: the 500 largest by `mcap_pit`, as-traded close >= $5, at least one filing with
  total assets in the 400 sessions before. Financials are kept (no SIC filter); a name missing a signal is scored on
  the signals it has, and needs at least 3 of the 5.
- Signals (each turned into a percentile 0-1 within the universe, with 1 = worst):
  1. **Net share issuance:** `net_share_issuance` on the reference date (12-month change in split-adjusted shares);
     higher is worse.
  2. **Asset growth:** latest total assets / total assets four fiscal quarters earlier - 1; higher is worse.
  3. **Accruals:** (TTM net income - TTM operating cash flow) / average of the latest and year-ago total assets, with
     net income = TTM diluted EPS x cover-page shares (the batch-5 proxy); higher is worse.
  4. **Gross profitability:** TTM gross profit / latest total assets; lower is worse (missing for firms that do not
     report gross profit; then scored on the other four).
  5. **ROA:** TTM net income / latest total assets; lower is worse.
- Score: the average of the available percentiles. **Excluded:** the 100 names with the highest score.
- A buffer to limit turnover: a currently excluded name returns only when its score rank falls below 130th worst; a
  held name is excluded only when it enters the worst 100.
- Weights: the remaining names (about 400) at `mcap_pit` weight, renormalised to sum to 1, each capped at 10% (excess
  spread pro rata). Between rebalances the weights drift with prices (no re-weighting).
- **Cash treatment:** fully invested; no cash and no SPY sleeve (before the first rebalance in March 2017, the book
  holds SPY).
- No stops. Delisted holdings exit at the last close x the store's delisting multiplier.
- Expected turnover, from the weighting rule as well as the signal: the cap-weighted core trades only at rebalances;
  about 20-30 names cross the exclusion line each quarter, averaging about 0.1% of weight each, plus index changes in
  the top 500 and the cap re-spreading. Estimate 15-30% a year one-way; costs under 0.1% a year.

## Price-only data note
The store is price-only for both the book and SPY. Excluded names (heavy issuers, fast-growing asset bases,
unprofitable firms) pay fewer dividends than average, so the book probably yields a little more than SPY; price-only
grading slightly understates it. The grade uses the price-only store as registered.

## Grading (docs/gates.md: "Full-period test", "Bill rate")
Daily net returns vs SPY, alpha from (r - BIL) on (SPY - BIL). Windows A 2017-01-01 .. 2024-10-04 and B 2024-10-07 ..
2026-10-05, and the pooled window 2017-01-01 .. 2026-10-05 as one simulation.
PASS on either route: (1) in both A and B, haircut Sharpe > 0 and alpha vs SPY > 0 with alpha t >= the bar; or
(2) in the pooled window the same conditions, with alpha vs SPY above zero in each of A and B.
Trials: family count 2 (this card and the mid-cap card). Bar: `alpha_t_critical(2)` = 2.241.
Beside the verdict: tracking error against SPY; and, descriptive only, the return of the excluded 100 (cap-weighted)
against SPY, which is the effect the card relies on.

## Expectation stated before the run
Small. Tracking error about 2-4% a year; alpha 0 to +1.5% a year; pooled alpha t about 0 to 1.5. The excluded names
include some 2020-21 and 2023-26 winners that issued shares or grew assets fast (a risk the card accepts). Likely
FAIL on the t bar; the descriptive excluded-names return will show whether the short-leg effect exists here at all.
