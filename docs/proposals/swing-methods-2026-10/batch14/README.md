# Batch 14: blend the signals, and scale the nearest miss (research thread, 2026-10-14)

Both ideas come from the survey thread "What winning trading programs do"
(claude/trading-systems-review @ c265e64, docs/proposals/trading-systems-review-2026-10-14.md), deduped against
batches 1-13 and shaped to the research scoreboard's profile: fully invested or explicitly scaled, turnover under
300% a year, large caps, weights cards.

| # | Card | What is new | Expected turnover |
|---|---|---|---|
| 1 | [sp500_four_signal_composite](sp500_four_signal_composite.md) | One book from momentum, gross profitability, net repurchases and value, equally weighted z-scores | 80-150%/yr |
| 2 | [vol_scaled_momentum_replica](vol_scaled_momentum_replica.md) | Batch 9's replica unchanged, with exposure = min(1, 15% / its 126-day vol), rest in BIL | 150-250%/yr |

Premise check (coordinator's request, after the survey addendum): [premise_check_french_momentum_profitability](premise_check_french_momentum_profitability.md)
tests the core of card 1 on Ken French's long-only big-stock momentum and profitability portfolios from 1963. It is
evidence for the idea, not a trial and not a pass route.

Both cards were chosen knowing the earlier results (stated in each card). Trial counting: both are momentum-family trials
(the family becomes 6: replica, mid, small, industry-neutral, these two), so both are graded at `alpha_t_critical(6)`
= 2.638. Card 1 also reuses the profitability and repurchase signals; it is counted once, against the largest family.

## Not taken from the survey
- **Book-level volatility target on the composite**: left out of card 1 so that blending and scaling are tested
  separately (card 2 tests scaling on the replica).
- **PEAD outside microcaps, intraday/SMC, short-term reversal**: the survey and the scoreboard both say no more trials.
