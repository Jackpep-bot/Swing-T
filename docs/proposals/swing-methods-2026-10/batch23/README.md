# Batch 23: robustness pass on the shadowed momentum replica (research thread, 2026-10-14)

| # | Card | Kind | Family (trials) | Expected turnover |
|---|---|---|---|---|
| 1 | [robustness_momentum_replica](robustness_momentum_replica.md) | robustness check (not a trial) | momentum (stays 7) | as the replica (~250%/yr) |

Chosen over another new card: batches 17-22 used up most free-store families (all failed; batch 21's exclusion book
came in at alpha -0.4% with 3.1% tracking error), and the replica is the one book being shadow-tracked. Knowing whether
its +4.9% pooled alpha survives other rebalance months, neighbouring settings, higher costs and a bootstrap is worth more
than a seventh weak family. Descriptive only; it cannot pass or change anything.

## Rejected this sweep
- **Searching the neighbouring settings for a better replica**: that would be a momentum trial per setting and
  in-sample by construction.
- **Walk-forward re-fitting**: the replica has no fitted parameters; timing and neighbouring settings are the
  meaningful robustness axes for a rule-based index.
- **Another free-store family card**: what is left (leverage, sales growth, seasonality variants) is weaker than
  what failed.
