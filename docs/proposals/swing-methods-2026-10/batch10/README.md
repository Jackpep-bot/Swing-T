# Batch 10: independent tests of the one family that came close (research thread, 2026-10-14)

Batch 9's `sp500_momentum_index_replica` beat SPY in both windows with drawdowns no deeper than SPY's, but missed the
alpha-t bar (1.30 and 0.73 vs 2.24). The coordinator asked for cards that could clear the bar without tuning that card.
This batch runs the **same rules, unchanged,** on two stock universes that do not overlap with it.

| # | Card | Universe | Names | Live record of the index it copies |
|---|---|---|---|---|
| 1 | [midcap_momentum_index_replica](midcap_momentum_index_replica.md) | mcap ranks 501-900 | 80 | XMMO 10-yr CAGR 17.8% |
| 2 | [smallcap_momentum_index_replica](smallcap_momentum_index_replica.md) | mcap ranks 901-1,500 | 120 | XSMO 10-yr CAGR 13.2% |

Both are weights cards and use only bars and `mcap_pit`. Family trial count: 3 (batch 9 card + these two).

## Why the t-bar is so hard here, stated once
A fully invested book that tracks SPY closely has a small tracking error. Batch 9's card earned about +10% a year
over SPY in 2024-26 and still had alpha t 0.73, because 2 years of daily data cannot separate that from luck at
tracking errors of 10% or more. With the store starting in 2016, no card of this kind can reach t 2.24 in the 2-year
window unless its edge is very large. Options that would make the test able to detect a real edge without loosening
it after the fact are the owner's call, not this thread's: (a) grade one pooled 2017-2026 window as well as the two
halves; (b) extend price history before 2016 (needs a data source decision). Until then, cards like these can at best
earn a forward test.

## Rejected this sweep
- **Retuning batch 9's card** (different lookback, count or caps): would be choosing settings after seeing results.
- **MSCI-style momentum (MTUM rules)**: rejected in batch 9 (live alpha +0.63% a year).
