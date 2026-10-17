# Batch 13: avoid the anomalies' short leg instead of picking winners (research thread, 2026-10-14)

Written after batches 5-12 (32 methods, none passed). Pass rule per docs/gates.md: two halves or pooled 2017-26 with
alpha above zero in each half; alpha from (r - BIL) on (SPY - BIL).

| # | Card | Kind | Universe | Excluded | Expected turnover |
|---|---|---|---|---|---|
| 1 | [mispricing_short_leg_exclusion_large](mispricing_short_leg_exclusion_large.md) | weights card | 500 largest, cap weight | worst 100 | 15-30%/yr |
| 2 | [mispricing_short_leg_exclusion_mid](mispricing_short_leg_exclusion_mid.md) | weights card | ranks 501-1,500, cap weight | worst 300 | 40-70%/yr |

New family (2 trials, bar 2.241). Data: bars, mcap_pit, net_share_issuance and the XBRL concepts already in the store
(total assets, operating cash flow, gross profit, diluted EPS, shares). No new data.

## Why this family
Every stock-picking card so far had beta near 1 and lost to a mega-cap-led SPY. Academic work (Stambaugh, Yu & Yuan
2012) puts most anomaly returns in the short leg. A cap-weighted book that only drops the worst-scored names keeps the
mega-cap exposure, has a small tracking error, and tests the one place long-only books can still use these anomalies.
Asset growth and accruals are not in the catalog; issuance and profitability appear only as separate signals or
nightly no-order trackers (net repurchasers, gross profitability), never as an exclusion from a cap-weighted index.

## Rejected this sweep
- **Intermediate momentum (12-7, Novy-Marx echo)**: momentum family (would be trial 5, bar 2.576), and later work
  ("Echo disappears", arXiv 2304.03437) finds the echo gone in recent data.
- **Lazy Prices (10-K text changes)**: needs unapproved data, and the long side's alpha fades quickly (CXO summary).
- **Tactical asset-allocation rotations (Allocate Smartly style)**: same cash-heavy profile as batch 12's trend book
  (+2.2%/yr); several are catalog items (Faber, dual momentum).
- **Value composites in large caps**: value lagged badly in 2017-26 and Piotroski/value cards failed in batch 5.
