# Batch 20: a popular trader method, dual momentum (research thread, 2026-10-14)

| # | Card | Kind | Family (trials) | Expected turnover |
|---|---|---|---|---|
| 1 | [global_equities_dual_momentum](global_equities_dual_momentum.md) | weights card | cross-asset trend (2), bar 2.241 | 100-300%/yr |

Written after batch 18 failed (blind CZ composite: DivYieldST + VolumeTrend, alpha -1.7%, t -0.86) and while batch 19
runs. The catalog already covers the classic stock-level anomalies the store can build; this batch tests one of the
most widely followed retail methods (Jack's "online traders" ask). It costs the Mac little: three ETFs, no fundamentals.

## Rejected this sweep
- **Turn-of-month, pre-holiday, FOMC, Santa, sector rotation, VRP on SVXY**: already in the catalog.
- **Keller's defensive or vigilant asset allocation**: same family as dual momentum with more tuned settings; one trial
  of the plainest version first.
- **Blending low-volatility or the CZ composite with the replica for lower correlation**: both had negative alpha, so a
  blend would only dilute the replica, and it would add trials to both families.
