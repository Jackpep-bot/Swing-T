---
slug: premise_check_french_momentum_profitability
name: Premise check (not a pass route) - 50/50 blend of Ken French's Big/High-momentum and Big/Robust-profitability portfolios, 1963-07 onward
originators: [Kenneth R. French Data Library (approved data, round 1 "Fama-French"); Fama & French (2015); Carhart (1997)]
category: premise_check
decision: implement
holding_period_days: [21, 21]
timeframe: monthly returns from the French library
direction: long
universe: French's value-weighted 2x3 portfolios (NYSE breakpoints, CRSP, delisted stocks included)
evidence_grade: B
free_data_ok: true
weights_card: false
status: draft_card (research thread batch 14, 2026-10-14). PREMISE CHECK for sp500_four_signal_composite. Not a trial and not a pass route; it cannot enable anything on paper by itself.
---

# Premise check: momentum + profitability in large caps, 60+ years

## Why this exists
With the store starting in 2016, even a large edge reaches only about t 1.5 pooled (scoreboard). t grows with the
square root of the years, so 60 years instead of 10 raises the reachable t by about 2.5x. Ken French's library
(already approved) has monthly returns of long-only large-cap portfolios sorted on momentum (from 1927) and on
operating profitability (from 1963). A blend of the two is the closest long-history version of the core of
`sp500_four_signal_composite`. If the premise fails over 60 years, the composite's 10-year result should be read
with that in mind; if it holds, the forward test of our own book has a long record behind it.

## Data (fixed before the run)
From the French library, monthly, value-weighted, as downloaded on the run date (record the file names and the
download date in the results):
- "6 Portfolios Formed on Size and Momentum (2 x 3)": the **BIG HiPRIOR** column (prior 2-12 month return, top 30%
  by NYSE breakpoints, big stocks).
- "6 Portfolios Formed on Size and Operating Profitability (2 x 3)": the **BIG HiOP** column (robust operating
  profitability, big stocks). Note: French uses operating profitability, not our gross profitability.
- "Fama/French 3 Factors": Mkt-RF and RF.

## Rules
- Blend: 0.5 x BIG HiPRIOR + 0.5 x BIG HiOP, rebalanced monthly (returns averaged each month).
- Window: 1963-07 (first profitability month) to the latest month in the files.
- Test: regress (blend - RF) on Mkt-RF (CAPM, the same form as our bill-rate grading); report alpha per year and its
  t (OLS standard errors, and Newey-West with 6 lags beside it).
- Subperiods, each reported: 1963-07 .. 1989-12, 1990-01 .. 2016-12, 2017-01 .. latest.
- Also reported, descriptive: each leg alone, the market, and the correlation of the two legs' CAPM residuals.

## What counts as support (stated before the run)
The premise is **supported** if the blend's full-window CAPM alpha t is >= 3.0 (Harvey-Liu-Zhu's bar for a new
factor) and its alpha is above zero in each of the three subperiods. Otherwise it is **not supported**. Either way this
is evidence about the idea, not a verdict on any card: no trading costs, monthly data only, and French's construction
rather than ours.

## Link to our own implementation (correlation check)
Over the overlapping months (2017-01 .. latest), correlate the blend's monthly excess-of-market return with the
monthly excess-of-SPY return of a 50/50 blend of two descriptive books the composite card already asks for (its
momentum-only and profitability-only single-signal books). Report the correlation and the sign of each series' mean.
The 10-year implementation is "consistent with" the premise only if the correlation is clearly positive (stated here:
>= 0.5) and both means have the same sign.

## Expectation stated before the run
The published record suggests both legs carried positive CAPM alpha since 1963 in big stocks (momentum's smaller in
big stocks, profitability's steadier), so a full-window alpha t above 3 is plausible; the 2017-latest subperiod is the
one most at risk. The correlation with our own books should be positive but below 1 (different signal details, gross
vs operating profitability, cap weighting choices).
