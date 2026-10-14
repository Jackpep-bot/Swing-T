---
slug: premise_check_french_low_variance
name: Premise check (not a pass route) - Ken French's value-weighted lowest-variance quintile against the market, 1963-07 onward
originators: [Kenneth R. French Data Library (approved data, round 1 "Fama-French"); Ang, Hodrick, Xing & Zhang (2006, JF); Baker, Bradley & Wurgler (2011)]
category: premise_check
decision: implement
holding_period_days: [21, 21]
timeframe: monthly returns from the French library
direction: long
universe: French's "Portfolios Formed on Variance" (CRSP, NYSE breakpoints, delisted stocks included)
evidence_grade: B
free_data_ok: true
weights_card: false
status: draft_card (research thread batch 17, 2026-10-14). PREMISE CHECK for sp500_low_volatility_replica. Not a trial and not a pass route; it cannot enable anything on paper by itself.
---

# Premise check: low-variance stocks, 60+ years

## Why this exists
As in batch 14: the store's 10 years cap the reachable t, so the idea behind the card is checked on the longest free
record we are approved to use. French's library sorts all CRSP stocks on the variance of their daily returns over the
prior 60 days and publishes value-weighted quintile returns from 1963. The lowest-variance quintile, value-weighted, is
dominated by large caps and is the closest long-history version of the card.

## Data (fixed before the run)
From the French library, monthly, as downloaded on the run date (record file names and download date in the results):
- "Portfolios Formed on Variance": **Value Weight Returns, Lo 20** (lowest quintile) and **Hi 20**.
- "Fama/French 3 Factors": Mkt-RF and RF.
If the variance file is not in the approved download already on the Mac, it is the same library and the same approval
(round 1); fetch it and say so in the results. If the Mac treats it as a new download, skip the check and say so.

## Rules
- Window: the first month in the file (expected 1963-07) to the latest month.
- Test: regress (Lo 20 - RF) on Mkt-RF; report alpha per year and t (OLS and Newey-West, 6 lags), and beta.
- Subperiods, each reported: start .. 1989-12, 1990-01 .. 2016-12, 2017-01 .. latest.
- Descriptive: the same for Hi 20, and Lo 20 minus Hi 20.

## What counts as support (stated before the run)
**Supported** if the Lo 20 full-window CAPM alpha t is >= 3.0 and its alpha is above zero in each of the three
subperiods. Otherwise **not supported**. Evidence about the idea only: no costs, monthly data, French's 60-day variance
rather than our 252-day volatility, quintiles rather than 100 names.

## Link to our own implementation (correlation check)
Over 2017-01 .. latest, correlate (Lo 20 - Mkt) monthly with the card's monthly return minus SPY's. "Consistent with"
the premise only if the correlation is >= 0.5 and both means have the same sign.

## Expectation stated before the run
Published work suggests a positive CAPM alpha for low-variance stocks since 1963 with beta about 0.7, so a full-window
t above 3 is plausible; 2017-latest is the subperiod most at risk (AQR's BAB was t 1.08 there). The correlation with
our card should be high (0.7+), since both hold the calmest large caps.
