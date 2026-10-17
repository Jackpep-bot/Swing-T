# Batch 17: the low-risk family, plus a long-history premise check (research thread, 2026-10-14)

| # | Card | Kind | Family (trials) | Expected turnover |
|---|---|---|---|---|
| 1 | [sp500_low_volatility_replica](sp500_low_volatility_replica.md) | weights card | low risk (1), bar 2.241 | 80-150%/yr |
| 2 | [premise_check_french_low_variance](premise_check_french_low_variance.md) | premise check (not a trial) | - | - |

Basis: the premise library (746f611). Low risk is the one long-only, large-cap, low-turnover effect not yet tested, and
the only one whose alpha does not need a beta-1 book to out-pick a mega-cap-led SPY. AQR's BAB is strong over 95 years
(t 7.48) but weak since 2017 (t 1.08), so the card expects a likely FAIL; the premise check carries the long record.

## Why no card from the Chen-Zimmermann top list this batch
- **Selection on the test window.** The library ranks predictors by their 2017-2024 results, which is most of our
  half A and pooled window. Picking the best of 208 on that and then grading 2017-26 would count the same years twice;
  an honest bar for that is about `alpha_t_critical(156)` (the buildable set), about 3.6.
- **Wrong size and weighting.** 24 of the top 25 are equal-weighted long-short portfolios driven by small caps; our
  small-cap map (870 cells) found no edge there net of costs.
- **Missing data.** EarningsStreak and EarnSupBig need analyst forecasts (IBES); XFIN needs cash-flow-statement
  financing items; OScore needs current assets and liabilities. The store has none of these.
- **Already tested.** GP (the one strong value-weighted signal) is batch 3's `large_cap_gross_profitability` and a leg
  of batches 14 and 16. MomVol and the momentum variants would be momentum trial 8 (bar 2.73).

A cleaner way to use CZ, proposed for a later batch if the coordinator agrees: the Mac picks predictors by a rule
fixed now and blind to 2017+ (post-publication t >= 2 on data through 2016-12 only, value-weighted, buildable from the
store), and those are carded without anyone looking at their recent results.

## Rejected this sweep
- **Low beta instead of low volatility** (BAB long leg): a second card in the same family on the same names; it would
  double the trials for little new information.
- **Net payout yield, large caps**: shareholder-yield/buyback family already has three trials (batches 2, 5, 14), and
  the price-only store penalises a dividend-heavy book by about its yield gap.
- **Low volatility plus momentum blend**: a combo would add trials to both families before either leg is graded.
