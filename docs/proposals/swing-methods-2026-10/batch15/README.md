# Batch 15: copy a second live index's rules (research thread, 2026-10-14)

Drafted while batch 14 runs, after batch 13's results (both FAIL; excluded names lagged by about 2 points a year but
the large-cap book still trailed SPY slightly). Profile per the scoreboard: fully invested, low turnover, large caps.

| # | Card | Kind | Family (trials) | Expected turnover |
|---|---|---|---|---|
| 1 | [sp500_quality_index_replica](sp500_quality_index_replica.md) | weights card | profitability/quality (3), bar 2.394 | 40-70%/yr |

One card only: the other candidates this round either repeat a tested family at a higher bar with no new reason
(momentum variants, now 6 trials), or have already lost in 2017-26 as live products (low-volatility: SPLV; dividend
growth: batch 11).

## Rejected this sweep
- **Low-volatility / minimum-variance large caps**: `beta_low_volatility` is a catalog item, and the live low-vol ETFs
  trailed SPY badly in 2017-26; a weights card would add a trial with little chance.
- **Growth or "GARP" index replicas**: growth's 2017-26 lead is known, so choosing it now is hindsight.
- **More momentum variants (12-7, sector-neutral, concentrated)**: the family is at 6 trials (bar 2.638) with batch 14
  still to report.
- **Mid-cap anything**: batches 10 and 13 show the mid-cap universe itself lagged SPY by several points a year.
