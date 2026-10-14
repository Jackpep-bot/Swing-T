# Batch 21: keep the market, drop the worst earnings surprises (research thread, 2026-10-14)

| # | Card | Kind | Family (trials) | Expected turnover |
|---|---|---|---|---|
| 1 | [sp500_earnings_disappointment_exclusion](sp500_earnings_disappointment_exclusion.md) | weights card | earnings surprise (3), bar 2.394 | 50-120%/yr |

Follows batch 19 (top-100 surprise book: pooled alpha -1.1%, t -0.49; bottom-100 book +8.2% vs top +11.8%; turnover
404%, costs 1.13%/yr). The spread was there; the top-100 book's tracking error and costs ate it. This card uses the
batch-13 exclusion construction on batch 19's unchanged signal. Chosen after the result, so counted as trial 3, grade C.

## Rejected this sweep
- **Top 100 with a wider buffer or semiannual rebalance**: tuning batch 19's own book after seeing it fail.
- **Revenue surprise or combined EPS+revenue**: revenue_surprise and double_surprise are already in the catalog.
- **Long top / avoid bottom tilt (130/30-style weights)**: the book cannot short or lever.
