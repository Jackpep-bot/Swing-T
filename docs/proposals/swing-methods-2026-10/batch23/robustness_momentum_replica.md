---
slug: robustness_momentum_replica
name: Robustness pass (not a trial, not a pass route) on sp500_momentum_index_replica - rebalance-timing luck, neighbouring settings, cost stress, block bootstrap
originators: [Hoffstein, Faber & Braun (2020) "Rebalance timing luck"; Harvey & Liu (2015) "Backtesting"; Politis & Romano (1994) stationary bootstrap]
category: robustness_check
decision: implement
holding_period_days: [126, 126]
timeframe: daily bars; mcap_pit; the replica's registered rules
direction: long
universe: as sp500_momentum_index_replica (batch 9)
evidence_grade: B
free_data_ok: true
weights_card: true
status: draft_card (research thread batch 23, 2026-10-14). ROBUSTNESS CHECK on the shadowed replica. Not a trial, cannot pass, cannot change the registered replica or its shadow book. Descriptive only.
---

# Robustness pass: how lucky is the momentum replica?

## Why this exists
The replica is our nearest miss (pooled +19.0% a year vs SPY 13.6%, alpha +4.9%, t 1.51) and the only stock book being
shadow-tracked. It was registered with one set of settings, and a semiannual book's result can depend a lot on which
months it happens to trade in ("rebalance timing luck"). Before anyone leans on its forward test, this pass asks how
much of the +4.9% belongs to the idea and how much to the exact settings. Nothing here re-grades it.

## What to run (all fixed before the run; the registered replica is variant R)
Window: pooled 2017-01-01 .. 2026-10-05, and halves A and B, as the replica's own grading.

1. **Timing luck (the main test).** Six variants that keep every rule and shift the reference months: Jan/Jul,
   Feb/Aug (= R), Mar/Sep, Apr/Oct, May/Nov, Jun/Dec, each trading at the open of the session after the third Friday of
   the following month. Report each one's alpha and t, the median, and the six-tranche average book (each tranche 1/6
   of capital, the "tranched" version that removes timing luck).
2. **Neighbouring settings**, one change at a time from R (no grid search over combinations):
   - holdings 50 or 150 instead of 100 (buffers scaled: 60/40 and 180/120);
   - momentum look-back 6-1 months instead of 12-1;
   - no volatility scaling (raw 12-1 return instead of return / volatility);
   - no score tilt (weight = mcap only, same 100 names);
   - quarterly instead of semiannual rebalancing (Feb/May/Aug/Nov).
3. **Cost stress**: R at 2x and 3x the per-symbol costs.
4. **Block bootstrap**: stationary bootstrap of R's daily excess-of-SPY returns (mean block 21 sessions, 10,000 draws,
   seed 20261014). Report the 5th, 50th and 95th percentiles of annual alpha and the share of draws with alpha <= 0.
5. **Total return**: R and the six-tranche book on the total-return store, beside the price-only figures.

## How to read it (stated before the run)
- **Robust** if the six-tranche book's pooled alpha is at least half of R's (>= +2.45% a year), at least 5 of the 6
  timing variants have pooled alpha > 0, and at least 5 of the 6 neighbouring settings have pooled alpha > 0.
- **Fragile** if the six-tranche alpha is under +1% a year or 3 or more timing variants have alpha <= 0.
- **Mixed** otherwise.
A "fragile" reading is a reason to say plainly in the weekly report that the shadow book's backtest likely overstates
it. A "robust" reading does not make it pass: it still needs the forward test and docs/gates.md. Neither reading
changes the replica's rules or its family's trial count (this is not a trial; no variant here can be carded later as
"the better setting" without counting as a new momentum trial, and its result here would be in-sample).

## Expectation stated before the run
Momentum books usually show large timing luck: I expect timing variants' pooled alpha to range about +1% to +6%, the
six-tranche book about +2.5-4%, 50 names noisier than 150, and cost stress to cost about 0.3-0.6% a year at 3x.
Likely "mixed" or "robust".
