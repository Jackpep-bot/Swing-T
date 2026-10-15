---
slug: replica_oos_2011_2016
name: Out-of-sample confirmation of sp500_momentum_index_replica on 2011-2016 (years never used to design, choose or grade it)
originators: [batch 9 card sp500_momentum_index_replica; S&P Momentum Indices methodology; Harvey & Liu (2015) on out-of-sample confirmation]
category: confirmation_test
decision: implement
holding_period_days: [126, 126]
timeframe: daily bars 2010-01-04 onward (Tiingo-extended store, data/live/replay_2010.duckdb); semiannual rebalance
direction: long
universe: as the replica (the 500 largest by mcap_pit)
evidence_grade: B
free_data_ok: true
weights_card: true
status: draft_card (research thread batch 24, 2026-10-15). CONFIRMATION TEST of the one shadowed book. PRE-REGISTERED NOW; GRADING ON 2011-2016 IS PENDING JACK'S EXPLICIT APPROVAL (a docs/gates.md change). Until he says yes, the run is descriptive only and nothing changes for the replica or its shadow book.
---

# Replica out of sample: 2011-2016

## Why this exists
The replica is the only book still standing (pooled 2017-26 alpha +4.9%, t 1.51; batch 23 robustness MIXED, six-tranche
alpha +2.2%). Every number we have comes from 2017-2026, the same years used to choose it. The Tiingo extension adds
2010-2015, which no card, result or decision has ever touched. Running the replica, unchanged, on those years is the
cleanest test available: one pre-specified book, one window, no choices left.

## What is run (fixed now; nothing may change after the store lands)
- **The code as it ran in batch 9**: `research/b9_books.py` replica path at the commit that produced
  2026-10-14-batch9-results.md, unchanged, including the inert score tilt batch 23 found (so in practice: the top 100 of
  the 500 largest by risk-adjusted 12-1 momentum, cap-weighted with batch 9's caps, buffer 120/80, Feb/Aug reference,
  trades after the third Friday of March and September). The tilt is **not** fixed for this run; fixing it would be a
  different book.
- Only change: `DATA_START` = 2010-01-04 (the store's first session), so the first reference date is 2011-02 (needs
  273 sessions) and the first trade is March 2011. Before that the book holds SPY.
- Universe size measure: `mcap_pit` as the 2010 build extends it (filed shares x as-traded close). If the build has no
  `mcap_pit` before 2016 for some names, they rank by their latest `dei:EntityPublicFloat` with `avail_ts` on or before
  the reference date, and the results say how many names used the fallback at each rebalance.
- Costs: `weights_book.simulate` with the per-symbol table (DEFAULT_COST_BPS = 10 bp where missing). Delisted names
  exit at their last close x the store's delisting multiplier (the 2010 build keys them `TICKER~YYYYMMDD`).
- Store checks first (docs/plan-store-2010.md step 6): if (a) the seam check fails or (c) fewer than 480 of the 500
  largest are present in any year 2010-2015, the test is not run and the results say why.

## Windows
- **O (the test):** 2011-01-03 .. 2016-12-30, net daily returns, alpha from (r - BIL) on (SPY - BIL).
- Descriptive beside it: the full 2011-01-03 .. 2026-10-05 window as one simulation, and the six-tranche version
  (batch 23's timing variants averaged) on O.

## Confirmation rule (stated now; applies only if Jack approves grading on 2011-2016)
- **Confirmed** if, in O, alpha vs SPY > 0 **and** alpha t >= 1.96 (`alpha_t_critical(1)`: one pre-specified book, one
  window, no search), and haircut Sharpe > 0.
- **Consistent, not confirmed** if alpha > 0 but t < 1.96.
- **Not supported** if alpha <= 0.
Trials: this is a confirmation of an existing card, not a new trial; the momentum family stays at 7. A "confirmed"
reading would make the replica the first book to clear a pre-registered out-of-sample bar; it still goes through
docs/gates.md and Jack before any paper risk. A "not supported" reading means the weekly report says the 2017-26 edge
did not carry back and the shadow book is watched as a likely beta-plus-noise book.

## Expectation stated before the run
2011-2016 had two momentum drawdowns (2009's crash is before the window; the 2016 reversal is in it) and a weaker
mega-cap lead than 2017-26. Expect alpha about 0 to +3% a year, t about 0 to 1.2 over six years. Most likely reading:
"consistent, not confirmed" or "not supported". Over 2011-2026 together, expect alpha t about 1.2-1.8.
