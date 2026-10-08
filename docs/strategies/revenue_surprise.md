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
_Generated 2026-10-08 by `swing_engine.research.cards` from `swing replay --no-router` on real data._ R per signal from the replay shadow ledger: every signal, entered the next session by its entry type, exited at its own stop or target or at the horizon close. `avg R` is gross; `net R` subtracts a round-trip cost per signal: half the stock's estimated spread (Abdi-Ranaldo, from its own daily bars) a side, at least 10 bp for names trading $50M+ a day and 20 bp otherwise, in R of the signal's stop distance. Regimes are the playbook router's labels on the signal day.
About 125 strategies were replayed together, so a few will look good by chance: judge them with the deflated Sharpe and haircut in docs/gates.md, not by this table alone.

### 2024-10-07 .. 2026-10-05 (survivorship-free, every US ticker)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 375 | 0 | 54% | -0.00 | -0.06 | 40% | -0.16 | -0.22 | 40% | -0.13 | -0.19 | 0.71 |
| healthy_uptrend | 835 | 0 | 52% | +0.04 | -0.02 | 43% | -0.04 | -0.10 | 42% | -0.04 | -0.10 | 0.92 |
| high_vol_selloff | 248 | 0 | 46% | -0.12 | -0.22 | 56% | +0.04 | -0.06 | 53% | +0.17 | +0.07 | 1.45 |
| narrow_uptrend | 67 | 0 | 84% | +0.84 | +0.78 | 73% | +0.85 | +0.79 | 82% | +1.33 | +1.27 | 8.44 |
| **all** | 1525 | 0 | 53% | +0.04 | -0.03 | 46% | -0.01 | -0.08 | 45% | +0.04 | -0.03 | 1.10 |

Portfolio replay (net of costs, slots shared with its run): 9 trades, win 33%, avg -0.26R, PF 0.55, P&L $-2,097 on $100k, avg hold 15.9 bars.

### 2017-01-01 .. 2024-10-04 (survivors only: ~4,300 names liquid in 2024, biased upward)
| regime | signals | skipped | win 5d | avg R 5d | net R 5d | win 10d | avg R 10d | net R 10d | win 20d | avg R 20d | net R 20d | PF 20d |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| choppy | 817 | 0 | 62% | +0.15 | +0.08 | 59% | +0.17 | +0.11 | 47% | +0.00 | -0.06 | 1.00 |
| correction | 475 | 1 | 62% | +0.10 | +0.03 | 60% | +0.17 | +0.09 | 60% | +0.27 | +0.20 | 1.82 |
| healthy_uptrend | 2081 | 6 | 44% | -0.08 | -0.16 | 49% | -0.02 | -0.10 | 50% | +0.07 | +0.00 | 1.19 |
| high_vol_selloff | 642 | 1 | 66% | +0.12 | +0.05 | 52% | -0.05 | -0.12 | 53% | +0.04 | -0.03 | 1.12 |
| narrow_uptrend | 667 | 2 | 52% | -0.02 | -0.09 | 54% | +0.05 | -0.02 | 49% | -0.01 | -0.08 | 0.97 |
| **all** | 4682 | 10 | 53% | +0.02 | -0.06 | 53% | +0.04 | -0.03 | 51% | +0.07 | -0.01 | 1.17 |

Portfolio replay (net of costs, slots shared with its run): 36 trades, win 53%, avg +0.07R, PF 1.15, P&L $2,164 on $100k, avg hold 16.2 bars.
