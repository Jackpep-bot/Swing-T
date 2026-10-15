# Batch 12: a low-beta diversifier and a lower-noise momentum signal (research thread, 2026-10-14)

Written after batch 11's results (both FAIL, pooled alpha -5.0% and -6.6% a year). Those results, and batches 5-10,
existed when these cards were chosen. Pass rule per docs/gates.md: two halves or the pooled 2017-26 window, alpha from
(r - BIL) on (SPY - BIL).

| # | Card | Kind | Family (trials) | New data |
|---|---|---|---|---|
| 1 | [multi_asset_trend_long_flat](multi_asset_trend_long_flat.md) | weights card | cross-asset trend (1) | daily bars for SPY, EFA, EEM, VNQ, IEF, TLT, GLD, DBC, UUP from 2016-01 |
| 2 | [industry_neutral_momentum_sp500](industry_neutral_momentum_sp500.md) | weights card | momentum (4) | none (bars, mcap_pit, sic2) |

Both cards state their cash treatment and the turnover their rules imply, after the Mac's batch-11 note (the dividend
card's weekly re-equalising turned over about 1,050% a year).

## What eleven batches say, and why these two
Every long-only US stock book so far had a beta near 1 and a negative alpha against 2017-26 SPY. Two ways out that do
not loosen the test: (1) a book whose returns do not come from SPY at all, so its alpha is not fighting the mega-cap
run (card 1); (2) a stock signal with less noise per unit of edge, so the same edge gives a higher t (card 2). Card 2 is
counted as the fourth momentum trial and graded at the higher bar (2.498).

## Rejected this sweep
- **Dividend initiations only**: did better than increases in batch 11 (pooled alpha -2.3%), but that was seen after
  the fact and the alpha is still negative; a card would be a new trial on a hindsight subset.
- **Promoted side of the Russell line**: +21.2% in 2024-26 was seen after the fact and looks like the 2024-26
  large-cap run.
- **Hedging a stock book with an inverse-SPY ETF**: the alpha regression already takes beta out, so hedging changes
  the return but not the alpha t.
- **Bond, covered-call and REIT income books**: price-only bars leave out their distributions, so they would be graded
  on a fraction of their return.
- **Sector rotation by relative strength**: `faber_sector_rotation` is already in the catalog.
