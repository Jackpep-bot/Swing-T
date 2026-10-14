# Batch 11: two new families, graded with the full-period test (research thread, 2026-10-14)

First batch written after the owner's "Add full-period test" decision (docs/gates.md, 2026-10-14 16:14 UTC). Each card
states the pooled 2017-01-01 .. 2026-10-05 window in its pass rule, alongside the two halves. Results that existed
when these were chosen: batches 5-10 all FAIL; batch 8 closed the takeover-target family at 2 trials.

| # | Card | Kind | Family | Data |
|---|---|---|---|---|
| 1 | [dividend_increase_drift](dividend_increase_drift.md) | weights card | dividend-change drift (new) | bars, mcap_pit, dividends |
| 2 | [russell_recon_migrant_drift](russell_recon_migrant_drift.md) | weights card | index-membership price pressure (new) | bars, mcap_pit |

Both cards hold SPY with any weight they do not use, so neither can lose to SPY just by sitting in cash. Trials: 2
(one per card, both new families); bar `alpha_t_critical(2)` = 2.241.

## Note for the grader (not a card change)
`prereg_eval._vs_benchmark` regresses raw daily returns on SPY's raw returns, with no T-bill rate taken off either
side. A book holding BIL or cash therefore shows a positive alpha equal to the bill rate (about 2% a year on average
2017-26) with a very small residual, so a mostly-in-bills book can show a large alpha t without any skill. The usual
fix is to regress returns minus the bill rate (BIL's return is in the store) on SPY minus the bill rate. Neither card
here holds bills, so this does not affect them; it matters for part-invested engine cards.

## Rejected this sweep
- **SPAC trust-value floor** (buy blank-check shares under trust value): needs point-in-time SIC 6770 or IPO type;
  the store's SIC is current only and changes after the merger. Revisit if a PIT blank-check list is approved.
- **Stock-split drift** (Ikenberry): needs split announcement dates; not in the approved data.
- **S&P 500 / SmallCap 600 additions**: the published effect reverses within about 60 sessions and is front-run.
- **BAB, lottery (MAX), Heston-Sadka seasonality, persistence momentum**: already in the catalog, and Quantpedia's
  2026 replication of nine anomalies found none significant out of sample in 2023-25
  (https://quantpedia.com/guardrails-make-the-researcher-what-an-ai-agent-got-right-and-wrong-replicating-nine-equity-anomalies/).
- **Any change to the momentum replicas**: tested in batches 9-10; not re-graded and not resubmitted.
