---
slug: mispricing_short_leg_exclusion_mid
name: Cap-weighted mcap ranks 501-1,500 minus the worst 30% on the same five-signal mispricing score, quarterly
originators: [Stambaugh, Yu & Yuan (2012, JFE); Stambaugh & Yuan (2017, RFS)]
category: strategy
decision: implement
holding_period_days: [63, 63]
timeframe: daily bars; mcap_pit; XBRL fundamentals; quarterly rebalance
direction: long
universe: mcap_pit ranks 501-1,500, as-traded close >= $5, median 63-session dollar volume >= $1M
regimes_good: [any]
regimes_bad: [speculative_rally]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: B
free_data_ok: true
weights_card: true
status: draft_card (research thread batch 13, 2026-10-14). WEIGHTS CARD. Mispricing short-leg avoidance family, trial 2 of 2. Universe does not overlap the large-cap card.
---

# Avoid the short leg: mid caps

## Why this card exists
Same idea as [mispricing_short_leg_exclusion_large](mispricing_short_leg_exclusion_large.md), on 1,000 smaller stocks
that do not overlap with it. Anomaly short legs are documented as stronger in smaller, less-followed stocks, so the
effect, if present, should be larger here; the price is a higher tracking error against SPY, because mid caps as a
group lagged SPY in 2017-26. Run together, the two cards show whether the effect exists in both size groups.

## Engine version (pre-register this one)
Every rule of the large-cap card applies (reference dates and timing, five signals, percentile scoring with at least 3
of 5, cap weighting with price drift between rebalances, SPY before March 2017, no stops, delisting rule), except:
- Universe: `mcap_pit` ranks 501-1,500 on the reference date, as-traded close >= $5, median 63-session dollar volume
  >= $1M.
- Excluded: the 300 names with the highest score (30%); buffer: an excluded name returns below the 360th worst; a
  held name is excluded when it enters the worst 300.
- Weight cap: 2% per name.
- **Cash treatment:** fully invested; no cash, no SPY sleeve after the first rebalance.
- Expected turnover: the universe's own membership changes (ranks 501-1,500 move more than the top 500) plus about 60-90
  names crossing the exclusion line per quarter; estimate 40-70% a year one-way; costs about 0.1-0.3% a year at mid-cap
  spreads.

## Price-only data note
As the large-cap card: price-only for both sides, slightly against the book.

## Grading (docs/gates.md: "Full-period test", "Bill rate")
Daily net returns vs SPY, alpha from (r - BIL) on (SPY - BIL); windows A, B and pooled 2017-01-01 .. 2026-10-05 as
one simulation. PASS on either route as the large-cap card. Trials: family count 2; bar `alpha_t_critical(2)` = 2.241.
Beside the verdict, descriptive only: the same book without exclusions (the cap-weighted 1,000), to separate the
exclusion effect from the mid-cap size effect; and the excluded names' return.

## Expectation stated before the run
The book will probably lag SPY because mid caps did (batch 10's mid-cap universe lagged by several points a year);
the descriptive comparison with the unscreened 1,000 is where an exclusion effect would show (perhaps +1-3% a year).
Alpha vs SPY likely negative. Likely FAIL.
