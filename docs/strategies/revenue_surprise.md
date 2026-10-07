---
slug: revenue_surprise
name: Revenue surprise (Jegadeesh-Livnat)
originators: [Narasimhan Jegadeesh and Joshua Livnat (Journal of Accounting and Economics 41, 2006; FAJ 62(2), 2006)]
category: strategy
decision: implement_disabled_for_comparison
holding_period_days: [20, 21]
timeframe: daily bars, quarterly signal
direction: long
regimes_good: [healthy_uptrend, narrow_uptrend]
regimes_bad: [correction, high_vol_selloff]
typical_win_rate: null
typical_payoff_ratio: null
evidence_grade: C
free_data_ok: true
status: not_built
---

# Revenue surprise

## One-line summary
Rank stocks on standardized seasonal change in revenue per share; the top decile earned a marginal premium for
about one month after the report.

## Origin and lineage
Jegadeesh and Livnat, "Revenue surprises and stock returns" (JAE 2006) and "Post-earnings-announcement drift: the role
of revenue surprises" (FAJ 2006). Their finding: drift is stronger when revenue and earnings surprises agree, because
revenue-driven earnings growth persists more than cost-cutting. Replicated as "Rs" in Hou-Xue-Zhang.

## Exact rules (catalog E25)
- Rs = (revenue per share_q - revenue per share_{q-4}) / std of that change over the prior 8 quarters (minimum 6).
- Monthly decile sort on the latest Rs; long the top decile (long-short in the papers); hold one month.

## Why it should work
Investors under-react to the persistence of top-line growth (harder to manage than EPS). Counterparty: slow updaters.
Likely subject to the same post-2006 decay as PEAD (not separately verified).

## When it works and when it fails
Best as a confirmation of an earnings surprise in the same direction; weak alone. Expect concentration in small caps.

## Parameters and sensitivity
Per-share vs total revenue, holding period (1 vs 6 months; only 1 month is reported significant), size filters.

## Evidence
- HXZ (NBER w23394): Rs1 0.31%/month, t about 2.2: marginal and below the t > 3 hurdle for new factors.
- Jegadeesh-Livnat magnitudes not verified this session (paywalled; abstract not available on RePEc). The FAJ version
  reports drift stronger when revenue and earnings surprises have the same sign.

## Common mistakes
Using fiscal period end as the signal date (look-ahead); mixing XBRL revenue tags across years without mapping.

## Implementation spec for swing-engine
- Data: EDGAR companyfacts us-gaap revenue concepts in order `Revenues`, `RevenueFromContractWithCustomerExcludingAssessedTax`,
  `SalesRevenueNet`; shares from `dei:EntityCommonStockSharesOutstanding` (already parsed in `data/float_data.py`) or
  `WeightedAverageNumberOfDilutedSharesOutstanding`. Quarterly Q4 = FY - 9M YTD. Point-in-time on `filed`.
- Feature `rs_ts`; cross-sectional `rs_rank` (0-1) per month.
- Use: minor confirmation feature in the ML ranker and as a tie-breaker for `power_gap` / `episodic_pivot`.
  Replay variant: top decile with `sue_ts > 0`, entry next open after month start, `max_hold_days = 21`, stop
  `entry - 3 * atr_14`, `min_reward_risk = 0.0`.
- Missing: XBRL revenue ingest, tag mapping, monthly cadence.

## What the router should know
Not a standalone strategy; feature only.

## Signs of decay to monitor
Information coefficient of `rs_rank` vs 21-day forward return <= 0 over trailing 24 months.

## Sources
- https://www.nber.org/system/files/working_papers/w23394/w23394.pdf
- https://ideas.repec.org/a/eee/jaecon/v41y2006i1-2p147-171.html
- https://ideas.repec.org/a/taf/ufajxx/v62y2006i2p22-34.html

## Empirical (replay)
_Pending: filled in from swing replay on real data._
