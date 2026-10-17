---
slug: premise_check_french_early_read_2011_2016
name: Premise check (not a pass route) - early read on batches 24 and 25 from Ken French's 5x5 size-by-momentum and size-by-profitability portfolios, 2011-2016
originators: [Kenneth R. French Data Library (approved data, round 1 "Fama-French"); Jegadeesh & Titman (1993); Novy-Marx (2013)]
category: premise_check
decision: implement
holding_period_days: [21, 21]
timeframe: monthly returns from the French library
direction: long
universe: French's value-weighted 5x5 portfolios (NYSE breakpoints, CRSP, delisted stocks included)
evidence_grade: B
free_data_ok: true
weights_card: false
status: draft_card (research thread batch 26, 2026-10-15). PREMISE CHECK / EARLY READ for replica_oos_2011_2016 (batch 24) and the two batch 25 confirmations. Not a trial and not a pass route; it cannot grade, replace or change batch 24 or 25.
---

# Early read: does the replica's idea show up in 2011-2016 in French's data?

## Why this exists
Batches 24 and 25 test our books on 2011-2016, but they wait on the 2010 store, which the free Tiingo quota puts about
two months out once Jack adds the key. French's library (already approved) has monthly returns, from 1927, for
value-weighted portfolios sorted on size and prior return. The **biggest-size, highest-momentum cell of the 5x5 sort**
(ME5 x PRIOR5) is roughly the top fifth by momentum among stocks above the NYSE 80th size percentile, value-weighted:
about 80-120 large caps, cap-weighted, which is close to what the Mac found the replica really is (top-100 momentum
among the 500 largest, cap-weighted, tilt inert). Its 2011-2016 record is a free early read on what batch 24 is
likely to find.

## What this cannot do (stated first)
- It does not grade, pass, or substitute for batch 24 or 25. Their rules are frozen in
  `docs/preregistration/2026-10-15-batch24-25.md` (claude/project-thread-fesglg) and nothing here changes them.
- It adds no trial to any family and enables nothing on paper.
- It has no costs, monthly data only, and French's construction (NYSE breakpoints, monthly rebalancing) rather than ours.

## Data (fixed before the run)
From the French library, monthly, value-weighted, as downloaded on the run date (record file names and download date):
- "25 Portfolios Formed on Size and Momentum (2-12)": the **BIG HiPRIOR** cell (ME5 PRIOR5), and ME5 PRIOR1 for the spread.
- "25 Portfolios Formed on Size and Operating Profitability": the **BIG HiOP** cell (ME5 OP5).
- "6 Portfolios Formed on Size and Momentum (2 x 3)": BIG HiPRIOR, for comparison with batch 14's premise check.
- "Fama/French 3 Factors": Mkt-RF and RF.
If a file is not already on the Mac, it is the same library and the same round-1 approval; fetch it and say so in the
results. If the Mac treats it as a new download, skip that file and say so.

## Rules
1. **Calibration window, 2017-01 .. latest month.** Correlate monthly (ME5 PRIOR5 - Mkt) with the replica's monthly
   (return - SPY) from the batch 9 record (price-only store; also the TR store, beside it). Do the same for
   (ME5 OP5 - Mkt) against the batch 16 book's (return - SPY). Report correlations and both sides' CAPM alpha.
2. **Read window, 2011-01 .. 2016-12 (72 months).** Regress (portfolio - RF) on Mkt-RF for ME5 PRIOR5, for a
   0.5/0.5 blend of ME5 PRIOR5 and ME5 OP5 (the batch 25 momentum+profitability analogue), and for ME5 OP5 alone.
   Report alpha per year, OLS t and Newey-West t (6 lags), and beta.
3. Descriptive: the same regressions for 2x3 BIG HiPRIOR, and ME5 PRIOR5 minus ME5 PRIOR1, each in both windows.

## How the read is labelled (stated before the run)
For each of the three portfolios in rule 2, against its own calibration correlation from rule 1:
- **Points toward confirmation**: calibration correlation >= 0.6, read-window alpha > 0 and OLS t >= 1.0.
- **Points against**: calibration correlation >= 0.6 and read-window alpha <= 0.
- **Uninformative**: anything else, including a calibration correlation below 0.6 (the proxy then does not track our book
  well enough to say anything).
These labels are a forecast of batch 24/25 only. The batch 24/25 readings (Confirmed / Consistent / Not supported) come
from those runs alone.

## Expectation stated before the run
Momentum had a weak first half of the 2010s in big stocks (the 2009 crash rebound and the 2016 reversal) and a better
middle stretch, so I expect ME5 PRIOR5 alpha near zero to modestly positive (about 0..+3%/yr, t 0..1.0), which would
most likely read Uninformative or a weak Points toward. I expect the calibration correlation with the replica around
0.6-0.8 (same idea, different breakpoints and rebalancing). Profitability in big stocks was steadier in that window; I
expect ME5 OP5 alpha small and positive. If all three Point against, waiting two months for batch 24/25 still costs
nothing, but Jack should hear that the odds of a confirmation are lower.

## Cost to run
Three or four small CSVs and a dozen regressions on the Mac; no store, no replay lanes, no network beyond the French files.
