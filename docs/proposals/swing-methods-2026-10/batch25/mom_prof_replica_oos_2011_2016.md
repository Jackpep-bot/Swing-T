---
slug: mom_prof_replica_oos_2011_2016
name: Out-of-sample confirmation of sp500_momentum_profitability_replica (batch 16) on 2011-2016
originators: [batch 16 card sp500_momentum_profitability_replica; Novy-Marx (2013); batch 14 French premise check]
category: confirmation_test
decision: implement
holding_period_days: [126, 126]
timeframe: daily bars 2010-01-04 onward (data/live/replay_2010.duckdb); XBRL gross profit and total assets; semiannual
direction: long
universe: as batch 16 (the 500 largest by mcap_pit)
evidence_grade: B
free_data_ok: true
weights_card: true
status: draft_card (research thread batch 25, 2026-10-15). CONFIRMATION TEST, pre-registered before the 2010 store exists and before anyone has seen a 2011-2016 number. Graded under the 2011-2016 rule only if Jack's "Grade it" (batch 24 card, 18:47Z) is read as covering pre-registered confirmations; otherwise descriptive until he says so.
---

# Momentum + profitability out of sample: 2011-2016

## Why
Batch 16 was the second-best pooled book (2017-26 +16.5% vs SPY 13.6%, alpha +2.4%, t 0.92, alpha positive in both
halves) and is backed by the strongest long-history premise we have (French big-stock momentum + profitability,
1963-2026, t 3.71). Like the replica, all its evidence is from 2017-26. 2011-2016 is untouched.

## What is run (fixed now)
- `research/` code for batch 16 exactly as it produced 2026-10-14-batch16-results.md, including the inert score tilt
  batch 23 found (so in practice the top 100 by the blended z, cap-weighted with batch 9's caps). Not fixed for this run.
- Only change: `DATA_START` = 2010-01-04; first trade March 2011; SPY before that.
- Gross profitability needs a TTM gross profit and total assets with `avail_ts` on or before the reference date; XBRL
  starts 2009 for large accelerated filers, so 2011 coverage is thinner. As registered in batch 16, a name with no
  gross profit scores g = 0. The results report the share of the 500 with g available at each rebalance; if under 60%
  at the March 2011 rebalance, the window starts at the first rebalance where it is at least 60% (stated now).
- Universe size, costs, delistings and store checks: as `replica_oos_2011_2016` (batch 24), including the public-float
  fallback and the step 6(a)/(c) gates.

## Confirmation rule (window O = 2011-01-03 .. 2016-12-30, or the later start above)
- **Confirmed**: alpha vs SPY > 0, alpha t >= 2.241, haircut Sharpe > 0.
- **Consistent, not confirmed**: alpha > 0, t < 2.241. **Not supported**: alpha <= 0.
Bar `alpha_t_critical(2)` = 2.241: two confirmation cards in this batch (this and the gross-profitability card); the
replica's own test (batch 24) is separate and was pre-specified first. Not a new trial: momentum stays at 7.
Beside it, descriptive: the 2011-2026 window as one simulation, and the correlation with the replica on O.

## Expectation stated before the run
Profitability did well in 2011-2016 large caps and momentum was mixed, so the blend may do a little better than the
replica on O: alpha about 0 to +3%, t 0 to 1.3. Most likely "consistent, not confirmed".
